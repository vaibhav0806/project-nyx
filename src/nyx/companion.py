"""Companion API: shared agent tools, owned visual evidence and memory."""

import base64
import hashlib
import json
import time
import traceback
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, Request
from PIL import Image, UnidentifiedImageError
from pydantic import AwareDatetime, BaseModel, Field

from nyx.agent import _model_tool_result, native_agent_steps
from nyx.answers import history_steps
from nyx.memory import aware_time
from nyx.voice import Conversations, local_now, spoken_answer


class ConfirmMatchRequest(BaseModel):
    frame_id: int = Field(ge=0)
    object_query: str = Field(min_length=1, max_length=240, pattern=r"\S")
    request_id: UUID


class TurnFrame(BaseModel):
    snapshot: str = Field(min_length=1, max_length=400_000)
    captured_at: AwareDatetime


class AgentRequest(BaseModel):
    visual_frames: list[TurnFrame] = Field(default_factory=list, max_length=6)
    context_at: AwareDatetime | None = None
    initial_action: dict | None = None
    timezone: str | None = Field(default=None, max_length=100)
    message: str = Field(min_length=1, max_length=1500, pattern=r"\S")
    request_id: str = Field(min_length=1, max_length=100)
    snapshot: str | None = Field(default=None, max_length=2_800_000)
    captured_at: AwareDatetime | None = None
    voice_turn_id: str | None = None
    presented_frame_id: int | None = Field(default=None, ge=0)
    presented_query: str | None = Field(default=None, min_length=1, max_length=240)


class ObservationRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    captured_at: AwareDatetime
    image: str = Field(min_length=1, max_length=400_000)


def decode_image(value, max_pixels=1920 * 1080):
    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) > 2 * 1024**2:
            raise ValueError("Image must be at most 2 MiB")
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"JPEG", "PNG"} or source.width * source.height > max_pixels:
                raise ValueError("Use a bounded JPEG/PNG image")
            image = source.convert("RGB")
            image.info["nyx_mime"] = "image/png" if source.format == "PNG" else "image/jpeg"
            return image
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Image is not readable") from exc


def fresh(captured_at, limit=15):
    age = (datetime.now(UTC) - aware_time(captured_at)).total_seconds()
    if age < -2 or age > limit:
        raise ValueError("Current evidence is stale; capture a fresh view")
    return age


def install_companion(app, workspace, voice):
    conversations = workspace.conversations or Conversations(workspace.root)
    workspace.conversations = conversations
    requests = {}
    references = {}
    reference_checks = {}
    last_observation = {"state": "inactive", "note": "Proactive reminders are not enabled"}

    @app.get("/companion.js")
    def companion_javascript():
        from fastapi.responses import FileResponse

        return FileResponse(
            Path(__file__).with_name("web") / "companion.js", media_type="text/javascript"
        )

    @app.post("/api/companion/warmup", status_code=202)
    def warmup():
        with workspace.lock:
            for identifier, job in workspace.jobs.items():
                if job["kind"] == "warmup" and job["status"] not in {"failed"}:
                    return {"id": identifier}
        job_id = workspace.reserve("warmup")
        workspace.submit(job_id, lambda: {"ready": workspace.visual_verifier() is not None})
        return {"id": job_id}

    @app.get("/api/companion")
    def status():
        return {
            "conversations": conversations.recent(),
            "reminders": [],
            "observation": last_observation,
            "pending": [],
        }

    @app.post("/api/matches/confirm")
    def confirm_match(body: ConfirmMatchRequest):
        # Confirmation belongs to the user, never to the visual model or agent.
        with workspace.lock:
            identifier = body.request_id.hex
            with conversations.connect() as db:
                existing = db.execute(
                    "SELECT plan, sources_available FROM turns WHERE id = ?", (identifier,)
                ).fetchone()
            if existing:
                plan = json.loads(existing["plan"])
                if (
                    plan.get("mode") != "user_confirmation"
                    or plan.get("frame_id") != body.frame_id
                    or plan.get("object_query") != body.object_query
                ):
                    raise HTTPException(409, "Confirmation ID belongs to a different choice")
                if not existing["sources_available"]:
                    raise HTTPException(404, "That source has been deleted")
                return {**plan["result"], "identity_verified": True}
            store = workspace.store()
            rows = store.frame_context(body.frame_id) if store else []
            evidence = next((row for row in rows if row["id"] == body.frame_id), None)
            if evidence is None:
                raise HTTPException(404, "That saved frame is no longer available")
            when = (
                evidence["observed_at"]
                or f"clip offset {evidence['offset_seconds']:.2f}s (capture time unknown)"
            )
            result = {
                "kind": "history",
                "status": "confirmed",
                "confirmation": "user",
                "identity_verified": True,
                "object_query": body.object_query,
                "turn_id": identifier,
                "answer": f"You confirmed this item in the recorded frame at {when}. This does not establish its current location or a later sighting.",
                "evidence": evidence,
                "checked": [],
                "scope": {
                    "checked_count": 0,
                    "known_time_only": bool(evidence["observed_at"]),
                    "note": "Item identity confirmed by you in this saved frame, not independently verified by Nyx. Capture time comes from the saved recording metadata.",
                },
            }
            conversations.begin(
                f"I confirmed the item for my request, {body.object_query}, in saved frame {body.frame_id}.",
                {
                    "mode": "user_confirmation",
                    "frame_id": body.frame_id,
                    "object_query": body.object_query,
                    "result": result,
                },
                identifier=identifier,
                input_sources=[evidence["video_id"]],
            )
            conversations.finish(identifier, result["answer"], [evidence["video_id"]])
            return result

    @app.post("/api/agent", status_code=202)
    def ask(body: AgentRequest, request: Request):
        if body.voice_turn_id:
            if voice is None:
                raise HTTPException(409, "Voice session is unavailable")
            with voice.lock:
                voice.check(request.headers.get("x-nyx-voice"))
                if (
                    not voice.turn
                    or voice.turn["id"] != body.voice_turn_id
                    or voice.turn["transcript"] != body.message
                ):
                    raise HTTPException(409, "Voice question is no longer active")
        if body.request_id in requests:
            old_message, job_id = requests[body.request_id]
            if old_message != body.message:
                raise ValueError("Request ID belongs to a different question")
            if job_id in workspace.jobs:
                return {"id": job_id}
        image = decode_image(body.snapshot) if body.snapshot else None
        if image is not None and body.captured_at is None:
            raise ValueError("Current view needs a capture time")
        if image is not None:
            fresh(body.captured_at.isoformat(), limit=90)
        turn_frames = []
        owned_times = None
        if body.visual_frames:
            if body.context_at is None:
                raise ValueError("Visual window requires a turn timestamp")
            fresh(body.context_at.isoformat(), limit=90)
            if body.voice_turn_id:
                with conversations.connect() as db:
                    owned = db.execute(
                        "SELECT at,plan FROM turns WHERE id=?", (body.voice_turn_id,)
                    ).fetchone()
                    owned_plan = json.loads(owned["plan"])
                    at = owned_plan.get("turn_context_at") or owned["at"]
                    if owned_plan.get("voice_visual_context") == "raw-final-v1":
                        owned_times = set(owned_plan.get("turn_frame_times", []))
                if abs((body.context_at - aware_time(at)).total_seconds()) > 3:
                    raise ValueError("Visual window belongs to a different turn")
            for frame in body.visual_frames:
                delta = (body.context_at - frame.captured_at).total_seconds()
                if (
                    frame.captured_at.isoformat() not in owned_times
                    if owned_times is not None
                    else not -2 <= delta <= 15
                ):
                    raise ValueError("Frame is outside the utterance window")
                turn_frames.append(
                    {
                        "image": decode_image(frame.snapshot),
                        "captured_at": frame.captured_at.isoformat(),
                    }
                )
        elif image is not None:
            turn_frames = [{"image": image, "captured_at": body.captured_at.isoformat()}]
        job_id = workspace.reserve("agent")
        requests[body.request_id] = (body.message, job_id)
        for key in list(requests):
            if len(requests) > 30:
                del requests[key]
        context = [row for row in conversations.recent() if row["status"] == "complete"][-12:]
        store = workspace.store()
        library = [row for row in store.list_videos() if row["status"] == "ready"] if store else []
        presented_candidate = None
        if body.presented_frame_id is not None and store:
            frame = next(
                (
                    row
                    for row in store.frame_context(body.presented_frame_id)
                    if row["id"] == body.presented_frame_id
                ),
                None,
            )
            if frame:
                presented_candidate = {
                    "frame_id": frame["id"],
                    "object_query": body.presented_query,
                    "observed_at": frame["observed_at"],
                    "video_id": frame["video_id"],
                }
        identifier = body.voice_turn_id or conversations.begin(body.message, {"mode": "agent"})
        available_context = {
            "presented_candidate": presented_candidate,
            "current_view": image is not None,
            "current_view_captured_at": body.captured_at.isoformat() if image is not None else None,
            "turn_visual_context": bool(turn_frames),
            "turn_visual_frame_count": len(turn_frames),
            "history": bool(library),
            "dated_history": any(row["recorded_at"] for row in library),
            "undated_history": any(not row["recorded_at"] for row in library),
            "scheduled_reminders": False,
            "proactive_notifications": False,
        }

        def cancelled():
            if workspace.jobs[job_id].get("cancelled"):
                return True
            if body.voice_turn_id:
                with voice.lock:
                    return voice.turn is None or voice.turn["id"] != body.voice_turn_id
            return False

        def observe_reference():
            from nyx.reference import resolve_reference

            def validate_owner():
                if cancelled():
                    raise ValueError("Request cancelled")
                if body.context_at:
                    fresh(body.context_at.isoformat(), limit=90)
                with conversations.connect() as db:
                    owner = db.execute(
                        "SELECT sources_available AND input_available FROM turns WHERE id=?",
                        (identifier,),
                    ).fetchone()
                if not owner or not owner[0]:
                    raise ValueError("Visual input is no longer available")

            validate_owner()
            key = (
                identifier,
                body.message,
                tuple(
                    (
                        frame["captured_at"],
                        frame["image"].size,
                        hashlib.sha256(frame["image"].tobytes()).digest(),
                    )
                    for frame in turn_frames
                ),
            )
            with workspace.lock:
                result = reference_checks.get(key)
            if result is None:
                reference = resolve_reference(
                    workspace.visual_verifier(), body.message, turn_frames
                )
                validate_owner()
                conversations.event("reference_resolved", turn_id=identifier, reference=reference)
                result = {"kind": "reference", **reference}
                if reference["status"] == "resolved":
                    result.update(
                        image=turn_frames[reference["frame_index"]]["image"],
                        answer="Shown object: "
                        + reference["object_description"]
                        + ". This identifies the demonstrated object, not its current location.",
                    )
            else:
                validate_owner()
                conversations.event("reference_reused", turn_id=identifier)
            with workspace.lock:
                reference_checks[key] = result
                while len(reference_checks) > 8:
                    del reference_checks[next(iter(reference_checks))]
                if result["status"] == "resolved":
                    references[identifier] = result["image"]
                else:
                    references.pop(identifier, None)
                while len(references) > 8:
                    del references[next(iter(references))]
            return result.copy()

        def prepare_memory():
            memory = workspace.personal_memory()
            memory.process(
                identifier,
                active=lambda: not cancelled(),
                observe=observe_reference if turn_frames else None,
            )
            return memory.turn_context(conversations, identifier)

        def tool(action):
            conversations.event("tool_started", turn_id=identifier, action=action)
            name = action["action"]
            if name == "process_memory":
                return prepare_memory()
            if name == "recall_memory":
                return workspace.personal_memory().recall(
                    action["query"],
                    as_of=action.get("as_of"),
                    select=True,
                    active=lambda: not cancelled(),
                )
            if name in {"inspect_current", "identify_shown_object"}:
                if name == "identify_shown_object":
                    return {k: v for k, v in observe_reference().items() if k != "image"}
                if image is None:
                    return {
                        "kind": "unavailable",
                        "status": "uncertain",
                        "answer": "No current camera view is available. Search dated history or ask to enable the camera.",
                    }
                fresh(body.captured_at.isoformat())
                verifier = workspace.visual_verifier()
                fresh(body.captured_at.isoformat())
                judgment = verifier.inspect(image, action["query"])
                result = {
                    "kind": "snapshot",
                    "identity_verified": False,
                    "object_query": action["query"],
                    "status": "clarify"
                    if judgment.get("ambiguous")
                    else "seen"
                    if judgment["visibility"] == "visible"
                    else "uncertain",
                    "judgment": judgment,
                    "captured_at": body.captured_at.isoformat(),
                    "age_seconds": fresh(body.captured_at.isoformat()),
                    "verifier": verifier.fingerprint,
                    "checked": [],
                    "scope": {
                        "note": "One fresh model-checked snapshot; the scene may change and the model can be wrong."
                    },
                    "snapshot_url": f"data:{image.info['nyx_mime']};base64,{body.snapshot}",
                }
                result["answer"] = spoken_answer(result)
                return result
            if name in {"search_history", "search_matches"}:
                if workspace.store() is None:
                    return {
                        "kind": "history",
                        "status": "uncertain",
                        "answer": "No indexed recording history is available.",
                        "checked": [],
                    }
                store = workspace.model_store()
                search_at = datetime.now(UTC)
                lower = (
                    (search_at - timedelta(hours=action["hours"])).isoformat()
                    if name == "search_history" and action["hours"]
                    else None
                )
                upper = search_at.isoformat() if name == "search_history" else None
                if "before_frame_id" in action:
                    anchor = next(
                        (
                            row
                            for row in store.frame_context(action["before_frame_id"])
                            if row["id"] == action["before_frame_id"]
                        ),
                        None,
                    )
                    if not anchor or not anchor.get("observed_at"):
                        raise ValueError(
                            "That frame has no available recording timestamp. Ask which dated moment to search before."
                        )
                    upper = min(
                        search_at,
                        datetime.fromisoformat(anchor["observed_at"]) - timedelta(microseconds=1),
                    ).isoformat()
                    if lower and datetime.fromisoformat(lower) >= datetime.fromisoformat(upper):
                        raise ValueError(
                            "The selected frame predates this search window. Choose hours=0 for all dated history before it, or a window reaching its recording time."
                        )
                result = yield from history_steps(
                    action["query"],
                    store,
                    workspace.encoder,
                    workspace.visual_verifier,
                    seen_after=lower,
                    seen_before=upper,
                    mode="latest" if name == "search_history" else "relevance",
                    semantic_latest=name == "search_history",
                    excluded_frame_ids=action.get("excluded_frame_ids", []),
                    reference_image=references.get(identifier),
                )
                result["scope"]["note"] = (
                    (
                        "Up to 64 semantic candidates within the selected window nominate up to 12 frames, spreading nearby frames within each clip before checking newest first. This is bounded sampled evidence, not an exhaustive last sighting. Unknown recording dates are excluded."
                    )
                    if name == "search_history"
                    else "Best matching sampled candidates, including unknown recording dates. This establishes neither the latest sighting nor the current location."
                )
                result["scope"]["hours"] = action.get("hours")
                result["scope"]["before_frame_id"] = action.get("before_frame_id")
                result["answer"] = spoken_answer(result)
                conversations.event(
                    "history_timing",
                    turn_id=identifier,
                    job_id=job_id,
                    timings=result.get("timings", {}),
                    checked=len(result.get("checked", [])),
                )
                return result
            raise ValueError("Unsupported tool")

        def run():
            try:
                now = local_now(body.timezone)
                availability = conversations.source_availability(row["id"] for row in context)
                input_availability = conversations.source_availability(
                    (row["id"] for row in context), input_only=True
                )
                current_context = [
                    {
                        **row,
                        "sources_available": availability.get(row["id"], False),
                        "input_available": input_availability.get(row["id"], False),
                    }
                    for row in context
                ]
                from nyx.conversation_context import recent_context

                current_context = recent_context(current_context)
                conversations.attach_context(identifier, current_context)
                context_sources = ["transcript:" + identifier] + [
                    "transcript:" + row["id"] for row in current_context if row["input_available"]
                ]

                def validate_sources(sources):
                    for source in set(context_sources + sources):
                        if source.startswith("transcript:"):
                            with conversations.connect() as db:
                                row = db.execute(
                                    "SELECT input_available FROM turns WHERE id=?", (source[11:],)
                                ).fetchone()
                            if not row or not row[0]:
                                raise ValueError("Conversation evidence changed; ask again")
                        else:
                            store = workspace.store()
                            if not store or store.video(source)["status"] != "ready":
                                raise ValueError("Recording evidence changed; ask again")
                    required = [row["id"] for row in current_context if row["sources_available"]]
                    if not all(conversations.source_availability(required).values()):
                        raise ValueError("Conversation evidence changed; ask again")

                memory_context = None
                if body.initial_action is None:
                    memory_context = prepare_memory()

                def generate(messages, tools):
                    generation_started = time.perf_counter()
                    verifier = workspace.visual_verifier()
                    reply = verifier.agent_reply(messages, tools)
                    conversations.event(
                        "agent_generation",
                        turn_id=identifier,
                        elapsed_ms=round((time.perf_counter() - generation_started) * 1000),
                        model=verifier.fingerprint,
                    )
                    return reply

                result = yield from native_agent_steps(
                    body.message,
                    current_context,
                    generate,
                    tool,
                    cancelled=cancelled,
                    initial_action=body.initial_action,
                    now=now.isoformat(),
                    user_timezone=body.timezone,
                    memory_context=memory_context,
                    validate_sources=validate_sources,
                    available=available_context,
                )
                result["turn_id"] = identifier
                result["voice_turn_id"] = body.voice_turn_id
                if (result.get("visual") or {}).get("kind") == "snapshot":
                    result["visual"]["age_seconds"] = fresh(result["visual"]["captured_at"])
                previous = {}
                if body.voice_turn_id:
                    with conversations.connect() as db:
                        previous = json.loads(
                            db.execute(
                                "SELECT plan FROM turns WHERE id=?", (identifier,)
                            ).fetchone()[0]
                        )
                plan = {
                    **previous,
                    "mode": "agent",
                    "available": available_context,
                    "steps": previous.get("steps", []) + result["steps"],
                    "presented_candidate": presented_candidate,
                    "candidate": {
                        "frame_id": result["visual"]["evidence"]["id"],
                        "object_query": result["visual"]["object_query"],
                        "observed_at": result["visual"]["evidence"]["observed_at"],
                        "excluded_frame_ids": result["visual"]["scope"].get(
                            "excluded_frame_ids", []
                        ),
                    }
                    if (result.get("visual") or {}).get("status") == "candidate"
                    else previous.get("candidate")
                    if not result.get("visual")
                    else None,
                    "decision_errors": previous.get("decision_errors", [])
                    + result["decision_errors"],
                    "policy_adjustments": previous.get("policy_adjustments", [])
                    + result["policy_adjustments"],
                    "model": workspace.verifier.fingerprint if workspace.verifier else None,
                    "turn_context_at": body.context_at.isoformat() if body.context_at else None,
                    "turn_frame_times": [frame["captured_at"] for frame in turn_frames],
                    "current_snapshot_at": body.captured_at.isoformat()
                    if body.captured_at
                    else None,
                }
                if result["steps"]:
                    plan["last_tool"] = {
                        "action": result["steps"][-1],
                        "result": _model_tool_result(result["observations"][-1]),
                    }
                statement_observations = [
                    r for r in result.get("observations", []) if r.get("kind") == "statements"
                ]
                plan["statement_refs"] = (
                    [
                        {
                            key: match.get(key)
                            for key in ["turn_id", "at", "object_description", "kind"]
                        }
                        for observation in statement_observations
                        for match in observation.get("matches", [])
                    ][-3:]
                    if statement_observations
                    else previous.get("statement_refs", [])
                )
                conversations.update_plan(
                    identifier,
                    plan,
                    sources=result["sources"],
                )
                validate_sources(result["sources"])
                review = dict(plan["candidate"] or {})
                if plan["statement_refs"]:
                    review["statement_refs"] = plan["statement_refs"]
                result["review_context"] = review or None
                conversations.event(
                    "agent_completed",
                    turn_id=identifier,
                    status=result["status"],
                    steps=result["steps"],
                    sources=result["sources"],
                    answer=result["answer"],
                )
                if not body.voice_turn_id:
                    conversations.finish(identifier, result["answer"], result["sources"])
                if (body.initial_action or {}).get("action") == "process_memory":
                    result["steps"] = []
                return result
            except Exception as exc:
                conversations.event(
                    "agent_failed",
                    turn_id=identifier,
                    job_id=job_id,
                    error_type=type(exc).__name__,
                    cancelled=cancelled(),
                    failure_site=[
                        f"{frame.name}:{frame.lineno}"
                        for frame in traceback.extract_tb(exc.__traceback__)
                    ][-8:],
                )
                conversations.finish(identifier, status="interrupted")
                raise

        workspace.submit(job_id, run)
        return {"id": job_id}

    @app.post("/api/agent/{job_id}/cancel")
    def cancel(job_id: str):
        with workspace.lock:
            job = workspace.jobs.get(job_id)
            if job is None or job["kind"] != "agent":
                raise HTTPException(404, "Companion request not found")
            job["cancelled"] = True
        conversations.event("agent_cancel_requested", job_id=job_id, reason="agent_cancel_endpoint")
        return {"cancelled": True}

    @app.delete("/api/reminders/{identifier}")
    @app.post("/api/reminders/{identifier}/cancel")
    @app.post("/api/reminders/{identifier}/acknowledge")
    @app.post("/api/deliveries/{identifier}/claim")
    @app.post("/api/deliveries/{identifier}/outcome")
    def retired_reminder_action(identifier: str):
        raise HTTPException(410, "Proactive reminders are not enabled")

    @app.post("/api/observe")
    def observe(body: ObservationRequest):
        # The preserved UI may poll this endpoint; no inference or scheduling is performed.
        return {"state": "inactive"}
