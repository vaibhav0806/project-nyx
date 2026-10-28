"""Companion API: local agent tools, live observation, and event-delivery lifecycle."""

import base64
import json
import re
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, Request
from PIL import Image, UnidentifiedImageError
from pydantic import AwareDatetime, BaseModel, Field

from nyx.agent import agent_steps
from nyx.answers import history_steps
from nyx.intentions import Intentions
from nyx.memory import aware_time
from nyx.observation import Observer, departure_action
from nyx.voice import Conversations, spoken_answer


class ConfirmMatchRequest(BaseModel):
    frame_id: int = Field(ge=0)
    object_query: str = Field(min_length=1, max_length=240, pattern=r"\S")
    request_id: UUID


class AgentRequest(BaseModel):
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
    tasks = Intentions(workspace.root)
    observer = Observer()
    conversations = workspace.conversations or Conversations(workspace.root)
    workspace.conversations = conversations
    workspace.observer = observer
    requests = {}
    last_observation = {"state": "idle", "note": "Camera off; no departure monitoring"}

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
        with workspace.lock:
            job = workspace.jobs.get(last_observation.get("job_id"), {})
            if job.get("status") == "failed":
                last_observation.update(state="interrupted", error=job.get("error"))
            elif job.get("status") == "succeeded" and last_observation["state"] == "checking":
                last_observation["state"] = job.get("result", {}).get("state", "watching")
        return {
            "conversations": conversations.recent(),
            "reminders": tasks.recent(),
            "observation": last_observation,
            "pending": tasks.pending(),
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
                return plan["result"]
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

        def cancelled():
            if workspace.jobs[job_id].get("cancelled"):
                return True
            if body.voice_turn_id:
                with voice.lock:
                    return voice.turn is None or voice.turn["id"] != body.voice_turn_id
            return False

        def authorize(action):
            name = action["action"]
            if name == "remind_on_departure":
                # The model may not turn content in observed footage into an instruction.
                if re.search(
                    r"\b(?:do not|don't|dont|never|cancel|stop)\b.{0,35}\bremind(?:er)?\b",
                    body.message,
                    re.IGNORECASE,
                ):
                    raise ValueError(
                        "I won't create a reminder from a negated or cancellation request"
                    )
                if not re.search(r"\bremind\b", body.message, re.IGNORECASE) or not re.search(
                    r"\b(leave|leaving|out|outside|depart|departing|exit|exiting)\b",
                    body.message,
                    re.IGNORECASE,
                ):
                    raise ValueError("Please explicitly ask for a reminder when you leave")
                if re.search(r"\b(every|whenever|always|daily)\b", body.message, re.IGNORECASE):
                    raise ValueError(
                        "This demo supports the next departure only; ask for a next-departure reminder"
                    )
            if name == "cancel_reminder":
                text = body.message
                if (
                    not re.search(
                        r"^\s*(?:(?:please|can you|could you|would you|will you|i want you to)\s+)*(?:cancel|forget|remove|stop)\b",
                        text,
                        re.IGNORECASE,
                    )
                    or re.search(
                        r"\b(?:do not|don't|dont|never)\b.{0,35}\b(?:cancel|forget|remove|stop)\b",
                        text,
                        re.IGNORECASE,
                    )
                    or re.search(r"\bremind me\b", text, re.IGNORECASE)
                ):
                    raise ValueError(
                        "Please explicitly ask to cancel a departure reminder; the current request does not authorize cancellation"
                    )
                active = tasks.active()
                selected = next((row for row in active if row["id"] == action["id"]), None)
                if selected is None:
                    raise ValueError(
                        "Choose an exact active reminder ID, or clarify which reminder"
                    )
                if not (
                    re.search(r"\breminders?\b", text, re.IGNORECASE)
                    or selected["message"].casefold() in text.casefold()
                    or re.search(
                        r"\b(?:cancel|forget|remove|stop)\s+(?:it|that|this)(?:\s+one)?[.!?]*$",
                        text.strip(),
                        re.IGNORECASE,
                    )
                ):
                    raise ValueError("The cancellation must identify a departure reminder")
                matches = [row for row in active if row["message"].casefold() in text.casefold()]
                if len(active) > 1 and (len(matches) != 1 or matches[0]["id"] != selected["id"]):
                    raise ValueError(
                        "Multiple reminders are active; clarify the exact reminder message before cancelling"
                    )

        def tool(action):
            conversations.event("tool_started", turn_id=identifier, action=action)
            authorize(action)
            name = action["action"]
            if name == "inspect_current":
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
                lower = (
                    (datetime.now(UTC) - timedelta(hours=action["hours"])).isoformat()
                    if name == "search_history" and action["hours"]
                    else None
                )
                upper = None
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
                    upper = (
                        datetime.fromisoformat(anchor["observed_at"]) - timedelta(microseconds=1)
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
                )
                result["scope"]["note"] = (
                    (
                        "Semantic candidates within the selected recent window, checked newest first. This is bounded sampled evidence, not an exhaustive last sighting. Unknown recording dates are excluded."
                    )
                    if name == "search_history"
                    else "Best matching sampled candidates, including unknown recording dates. This establishes neither the latest sighting nor the current location."
                )
                result["scope"]["hours"] = action.get("hours")
                result["scope"]["before_frame_id"] = action.get("before_frame_id")
                result["answer"] = spoken_answer(result)
                if result.get("evidence") and hasattr(workspace.visual_verifier(), "generate_json"):
                    from nyx.capture import frame_image
                    from nyx.cloud import CloudError
                    from nyx.context import attach_statements

                    try:
                        evidence_image = frame_image(
                            store.root / result["evidence"]["video_path"],
                            result["evidence"]["offset_seconds"],
                        )
                        attach_statements(
                            result,
                            conversations,
                            workspace.visual_verifier(),
                            evidence_image,
                            identifier,
                        )
                    except CloudError:
                        result["answer"] += " Spoken context could not be checked right now."
                return result
            if name == "remind_on_departure":
                item = tasks.create(body.request_id, action["message"])
                return {
                    "kind": "reminder",
                    "status": item["state"],
                    "reminder": item,
                    "answer": f"For your next departure: {item['message']}. Keep the camera running with the main door visible; departure detection is experimental."
                    if item["state"] == "armed"
                    else f"That departure request already exists and is {item['state']}.",
                }
            if name == "list_reminders":
                rows = tasks.recent()
                return {
                    "kind": "reminder",
                    "status": "complete",
                    "answer": "; ".join(f"{row['message']} ({row['state']})" for row in rows)
                    or "You have no departure reminders.",
                    "reminders": rows,
                }
            if name == "cancel_reminder":
                if not re.search(r"\b(cancel|forget|remove|stop)\b", body.message, re.IGNORECASE):
                    raise ValueError("Please explicitly ask to cancel a departure reminder")
                tasks.cancel(action["id"])
                return {
                    "kind": "reminder",
                    "status": "cancelled",
                    "answer": "That departure reminder is cancelled.",
                }
            raise ValueError("Unsupported companion tool")

        def run():
            try:
                if re.search(r"\bremind\b", body.message, re.IGNORECASE) and (
                    re.search(
                        r"\b(?:at|by)\s+(?:\d|one\b|two\b|three\b|four\b|five\b|six\b|seven\b|eight\b|nine\b|ten\b|eleven\b|twelve\b|noon\b|midnight\b)",
                        body.message,
                        re.IGNORECASE,
                    )
                    or re.search(
                        r"\b(?:tomorrow|tonight|next week|on monday|on tuesday|on wednesday|on thursday|on friday|on saturday|on sunday|in \d+ (?:minutes?|hours?|days?))\b",
                        body.message,
                        re.IGNORECASE,
                    )
                ):
                    result = {
                        "kind": "agent",
                        "status": "clarify",
                        "answer": "Timed reminders aren't available in this demo yet. I can remind you on your next departure, without a clock-time condition.",
                        "steps": [],
                        "sources": [],
                        "checked": [],
                        "turn_id": identifier,
                        "voice_turn_id": body.voice_turn_id,
                    }
                    if not body.voice_turn_id:
                        conversations.finish(identifier, result["answer"])
                    return result

                def decide(state):
                    verifier = workspace.visual_verifier()
                    action = verifier.decide({**state, "reminders": tasks.active()})
                    conversations.event(
                        "agent_decision",
                        turn_id=identifier,
                        action=action,
                        context_turns=len(context),
                        model=verifier.fingerprint,
                    )
                    return action

                result = yield from agent_steps(
                    body.message,
                    context,
                    decide,
                    tool,
                    cancelled=cancelled,
                    validate_tool=authorize,
                    available={
                        "presented_candidate": presented_candidate,
                        "current_view": image is not None,
                        "history": bool(library),
                        "dated_history": any(row["recorded_at"] for row in library),
                        "undated_history": any(not row["recorded_at"] for row in library),
                    },
                )
                result["turn_id"] = identifier
                result["voice_turn_id"] = body.voice_turn_id
                if (result.get("visual") or {}).get("kind") == "snapshot":
                    result["visual"]["age_seconds"] = fresh(result["visual"]["captured_at"])
                conversations.update_plan(
                    identifier,
                    {
                        "mode": "agent",
                        "steps": result["steps"],
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
                        else None,
                        "decision_errors": result["decision_errors"],
                        "policy_adjustments": result["policy_adjustments"],
                        "model": workspace.verifier.fingerprint if workspace.verifier else None,
                        "current_snapshot_at": body.captured_at.isoformat()
                        if body.captured_at
                        else None,
                    },
                )
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
                return result
            except Exception as exc:
                conversations.event(
                    "agent_failed", turn_id=identifier, error_type=type(exc).__name__
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
        return {"cancelled": True}

    @app.delete("/api/reminders/{identifier}")
    def cancel_reminder(identifier: str):
        tasks.cancel(identifier)
        return {"cancelled": True}

    @app.post("/api/reminders/{identifier}/acknowledge")
    def acknowledge(identifier: str):
        tasks.acknowledge(identifier)
        return tasks.get(identifier)

    @app.post("/api/observe")
    def observe(body: ObservationRequest):
        session = workspace.capture.snapshot()["session"]
        if not session or session["id"] != body.session_id or session["state"] != "recording":
            observer.reset()
            raise HTTPException(409, "Live observation needs the active recording session")
        image = decode_image(body.image, 640 * 360)
        if not any(row["state"] == "armed" for row in tasks.active()):
            observer.reset()
            last_observation.update(
                state="quiet", phase="quiet", note="Camera active; no armed departure reminder"
            )
            return {"state": "quiet"}
        burst = observer.feed(body.session_id, image, body.captured_at.isoformat())
        last_observation.update(
            state="watching",
            phase=observer.phase,
            at=body.captured_at.isoformat(),
            note="Checking local visual changes for an active departure request",
        )
        if burst is None:
            return {"state": "watching", "phase": observer.phase}
        with workspace.lock:
            if any(
                job["kind"] == "observe" and job["status"] not in {"succeeded", "failed"}
                for job in workspace.jobs.values()
            ):
                return {"state": "busy"}
        job_id = workspace.reserve("observe")
        observer.accept(burst)
        last_observation.pop("error", None)
        last_observation["job_id"] = job_id
        last_observation["state"] = "checking"

        def check():
            if not observer.valid(burst):
                return {"state": "interrupted", "deliveries": []}
            fresh(burst["times"][-1], 8)
            model = workspace.visual_verifier()
            fresh(burst["times"][-1], 8)
            started = time.perf_counter()
            judgment = model.inspect_departure(
                burst["tracking_images"],
                times=burst["tracking_times"],
                view_id=(burst["session"], burst["epoch"]),
            )
            checked = burst
            selected = judgment.get("frame_indices")
            if selected:
                if (
                    len(selected) != 3
                    or any(
                        type(i) is not int or not 0 <= i < len(burst["tracking_times"])
                        for i in selected
                    )
                    or selected != sorted(set(selected))
                ):
                    raise ValueError(
                        "Semantic inspection needs three distinct ordered image indices"
                    )
                checked = {**burst, "times": [burst["tracking_times"][i] for i in selected]}
            elif selected is not None and judgment.get("semantic_checked") is not False:
                raise ValueError("Missing inspected image indices")
            session = workspace.capture.snapshot()["session"]
            if (
                not observer.valid(burst)
                or not session
                or session["id"] != burst["session"]
                or session["state"] != "recording"
            ):
                return {"state": "interrupted", "deliveries": []}
            fresh(checked["times"][-1])
            decision = departure_action(checked, judgment, tasks.active())
            continuity = None
            if decision["act"]:
                continuity = observer.delivery_continuity(burst, checked["times"][-1])
                if not continuity["supported"]:
                    decision = {
                        "act": False,
                        "request_ids": [],
                        "reason": "superseded_evidence",
                    }
            semantic_times = (
                checked["times"] if judgment.get("semantic_checked") is not False else []
            )
            evidence = {
                "judgment": judgment,
                "model": model.fingerprint,
                "frame_times": checked["times"],
                "semantic_frame_times": semantic_times,
                "inference_seconds": time.perf_counter() - started,
                "kind": "model_inference" if semantic_times else "detector_observation",
                "event_id": burst["event_id"],
                "activity": burst["activity"],
                "decision": decision,
                "delivery_continuity": continuity,
            }
            deliveries = (
                tasks.trigger(
                    burst["event_id"],
                    checked["times"][-1],
                    evidence,
                    request_ids=decision["request_ids"],
                )
                if decision["act"]
                else []
            )
            last_observation.update(
                state="triggered" if deliveries else "watching",
                judgment=judgment,
                decision=decision,
                delivery_continuity=continuity,
                seconds=evidence["inference_seconds"],
            )
            return {
                "state": last_observation["state"],
                "judgment": judgment,
                "deliveries": deliveries,
                "decision": decision,
                "event_id": burst["event_id"],
                "activity": burst["activity"],
                "frame_times": checked["times"],
                "semantic_frame_times": semantic_times,
                "delivery_continuity": continuity,
            }

        workspace.submit(job_id, check)
        from fastapi.responses import JSONResponse

        return JSONResponse({"id": job_id}, status_code=202)

    @app.post("/api/deliveries/{identifier}/claim")
    def claim_delivery(identifier: str):
        item = tasks.deliver(identifier)
        if item is None:
            raise HTTPException(409, "Reminder expired, cancelled, or already claimed")
        session = workspace.capture.snapshot()["session"]
        if not session or session["state"] != "recording":
            tasks.finish(identifier, "interrupted")
            raise HTTPException(409, "Camera stopped; this departure reminder was interrupted")
        audio = None
        warning = None
        if voice:
            try:
                audio = voice.provider.speak(item["message"])
            except ValueError as exc:
                warning = str(exc)
        try:
            fresh(item["observed_at"])
        except ValueError as exc:
            tasks.finish(identifier, "interrupted")
            raise HTTPException(409, "Departure evidence expired before speech was ready") from exc
        # Cancellation during a provider request must prevent late speech.
        if tasks.get(item["intention_id"])["state"] != "delivering":
            raise HTTPException(409, "Reminder cancelled")
        return {**item, "audio": audio, "warning": warning}

    @app.post("/api/deliveries/{identifier}/outcome")
    def delivery_outcome(identifier: str, body: dict):
        tasks.finish(identifier, body.get("outcome"))
        return {"recorded": True}
