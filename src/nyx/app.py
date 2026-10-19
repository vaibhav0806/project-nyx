import base64
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from io import BytesIO
from itertools import count
from pathlib import Path
from queue import PriorityQueue
from threading import Lock, Thread
from types import GeneratorType
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import AwareDatetime, BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from nyx.answers import history_steps
from nyx.memory import Store
from nyx.recording import CaptureJournal
from nyx.retrieval import index_video_batches, search

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
WEB = Path(__file__).with_name("web")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    video_id: str | None = None
    limit: int = Field(default=5, ge=1, le=100)
    seen_after: AwareDatetime | None = None
    seen_before: AwareDatetime | None = None
    order: Literal["relevance", "latest"] = "relevance"


class AnswerRequest(BaseModel):
    object_query: str = Field(min_length=1, max_length=200, pattern=r"\S")
    mode: Literal["latest", "relevance"] = "latest"
    video_id: str | None = None
    seen_after: AwareDatetime | None = None
    seen_before: AwareDatetime | None = None


class CaptureStart(BaseModel):
    at: AwareDatetime


class CaptureState(CaptureStart):
    state: Literal["recording", "paused", "stopped", "interrupted"]
    reason: str = Field(min_length=1, max_length=300)


class Workspace:
    def __init__(self, root, encoder_factory, video_budget_bytes, verifier_factory):
        self.root = Path(root).resolve()
        self.encoder_factory = encoder_factory
        self.encoder = None
        self.verifier_factory = verifier_factory
        self.verifier = None
        self.queue = PriorityQueue()
        self.order = count()
        self.thread = Thread(target=self.run, name="nyx-inference", daemon=True)
        self.lock = Lock()
        self.store_lock = Lock()
        self.upload_lock = Lock()
        self.jobs = {}
        self.scheduled = set()
        self.capture = CaptureJournal(self.root, video_budget_bytes)
        self.conversations = None

    def store(self):
        with self.store_lock:
            path = self.root / "index.sqlite3"
            if not path.exists():
                return None
            with sqlite3.connect(path) as db:
                row = db.execute("SELECT value FROM meta WHERE key='encoder'").fetchone()
            identity = json.loads(row[0])
            return Store(self.root, identity["encoder"], identity["dimensions"])

    def model_store(self):
        if self.encoder is None:
            self.encoder = self.encoder_factory()
        with self.store_lock:
            return Store(self.root, self.encoder.fingerprint, self.encoder.dimensions)

    def visual_verifier(self):
        if self.verifier is None:
            self.verifier = self.verifier_factory()
        return self.verifier

    def reserve(self, kind, job_id=None):
        with self.lock:
            if kind != "capture" and any(
                job["kind"] == kind and job["status"] not in {"succeeded", "failed"}
                for job in self.jobs.values()
            ):
                raise HTTPException(409, "Nyx is busy. Wait for the current task to finish.")
            job_id = job_id or uuid.uuid4().hex
            self.jobs[job_id] = {
                "id": job_id,
                "kind": kind,
                "created_at": datetime.now(UTC).isoformat(),
                "status": "uploading" if kind == "index" else "queued",
            }
            for old_id, old in list(self.jobs.items()):
                if len(self.jobs) <= 20:
                    break
                if old["status"] in {"succeeded", "failed"}:
                    del self.jobs[old_id]
            return job_id

    def update(self, job_id, **changes):
        with self.lock:
            self.jobs[job_id].update(changes)
            if changes.get("status") in {"succeeded", "failed"}:
                self.scheduled.discard(job_id)

    def submit(self, job_id, action):
        priority = 0 if self.jobs[job_id]["kind"] in {"search", "answer", "agent", "observe"} else 1
        self.queue.put((priority, next(self.order), job_id, action))

    def run(self):
        while True:
            _, _, job_id, work = self.queue.get()
            if job_id is None:
                return
            self.update(job_id, status="running")
            try:
                result = work() if callable(work) else work
                if isinstance(result, GeneratorType):
                    progress = next(result)
                    self.update(job_id, progress=progress)
                    self.queue.put((1, next(self.order), job_id, result))
                else:
                    self.update(job_id, status="succeeded", result=result)
            except StopIteration as done:
                self.update(job_id, status="succeeded", result=done.value)
            except Exception as exc:  # noqa: BLE001 — worker failures must reach the task UI
                self.update(job_id, status="failed", error=str(exc))

    def submit_segment(self, segment):
        with self.lock:
            if segment["id"] in self.scheduled or segment["state"] != "queued":
                return
            self.scheduled.add(segment["id"])
        job_id = self.reserve("capture", segment["id"])

        def index():
            self.capture.mark(segment["id"], "indexing")
            try:
                result = yield from index_video_batches(
                    self.root / segment["path"],
                    self.model_store(),
                    self.encoder,
                    recorded_at=None if segment["timing_uncertain"] else segment["recorded_at"],
                    video_id=segment["id"],
                    name=f"Recording {segment['recorded_at']} · part {segment['sequence'] + 1}",
                    adaptive=True,
                )
            except Exception as exc:
                self.capture.mark(segment["id"], "failed", str(exc))
                raise
            self.capture.mark(
                segment["id"], "ready", last_sample_seconds=result["last_sample_seconds"]
            )
            return result

        self.submit(job_id, index)

    @contextmanager
    def upload_slot(self):
        if not self.upload_lock.acquire(blocking=False):
            raise HTTPException(409, "Another upload is in progress. Try again shortly.")
        try:
            yield
        finally:
            self.upload_lock.release()

    def close(self):
        self.queue.put((99, next(self.order), None, None))
        self.thread.join()

    def delete_video(self, video_id):
        deletion = self.capture.deletion(video_id)
        if deletion and deletion["state"] == "deleted":
            return
        store = self.store()
        video = store.video(video_id) if store else None
        try:
            segment = self.capture.segment(video_id)
        except ValueError:
            segment = None
        record = deletion or video or segment
        if record is None:
            raise HTTPException(404, "Source not found")
        source = (self.root / record["path"]).resolve()
        frames = (self.root / "frames" / video_id).resolve()
        if (
            len(video_id) != 32
            or any(c not in "0123456789abcdef" for c in video_id)
            or source.parent != self.root / "recordings"
            or source.stem != video_id
            or frames.parent != self.root / "frames"
        ):
            raise ValueError(
                "Source paths must stay in their managed recording and frame locations"
            )
        if self.conversations:
            self.conversations.invalidate(video_id)
        self.capture.request_deletion(video_id, record["path"])
        if store:
            store.hide_video(video_id)
        source.unlink(missing_ok=True)
        if frames.exists():
            shutil.rmtree(frames)
        self.capture.partial_path(video_id).unlink(missing_ok=True)
        if store:
            store.delete_video(video_id)
        self.capture.finish_deletion(video_id)
        for job in self.jobs.values():
            result = job.get("result", {})
            if any(row["video_id"] == video_id for row in result.get("checked", [])):
                job.update(
                    status="failed", error="Source deleted; ask again using the remaining history."
                )
                job.pop("result", None)
            if "results" in result:
                result["results"] = [
                    row for row in result["results"] if row["video_id"] != video_id
                ]

    def recover_deletions(self):
        for deletion in self.capture.deletions():
            try:
                self.delete_video(deletion["id"])
            except OSError:
                # Keep evidence hidden and cleanup pending for an explicit retry.
                continue


def create_app(
    root=Path("data"),
    device="auto",
    encoder_factory=None,
    max_upload_bytes=MAX_UPLOAD_BYTES,
    video_budget_bytes=1024**3,
    verifier_factory=None,
    voice_factory=None,
):
    if encoder_factory is None:

        def encoder_factory():
            from nyx.perception import SiglipEncoder

            return SiglipEncoder(device)

    if verifier_factory is None:

        def verifier_factory():
            from nyx.verification import LocalVerifier

            return LocalVerifier(device)

    workspace = Workspace(root, encoder_factory, video_budget_bytes, verifier_factory)
    from nyx.voice import MAX_PCM, Conversations, Sarvam, Voice, VoiceError

    key = os.environ.get("SARVAM_API_KEY")
    voice = (
        voice_factory(root)
        if voice_factory
        else Voice(root, Sarvam(key), agent_mode=True)
        if key
        else None
    )
    workspace.conversations = (
        voice.conversations
        if voice
        else (Conversations(root) if (Path(root) / "conversations.sqlite3").exists() else None)
    )

    @asynccontextmanager
    async def lifespan(app):
        workspace.recover_deletions()
        workspace.capture.recover()
        for segment in workspace.capture.pending():
            workspace.submit_segment(segment)
        workspace.thread.start()
        if voice:
            job_id = workspace.reserve("warmup")

            def warmup():
                workspace.visual_verifier()
                return {"ready": True}

            workspace.queue.put((2, next(workspace.order), job_id, warmup))
        yield
        workspace.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )
    from nyx.companion import install_companion

    install_companion(app, workspace, voice)

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    async def receive_video(request, path):
        remaining = workspace.capture.budget_bytes - workspace.capture.video_bytes()
        if shutil.disk_usage(workspace.root).free < 256 * 1024**2:
            raise HTTPException(507, "Disk space is low. Recording stopped; saved clips are kept.")
        size = 0
        with path.open("wb") as file:
            async for chunk in request.stream():
                size += len(chunk)
                if size > min(max_upload_bytes, remaining):
                    raise HTTPException(
                        413,
                        "Video size or saved-video budget limit reached; existing clips are kept.",
                    )
                file.write(chunk)
        if not size:
            raise HTTPException(400, "The clip is empty; choose or record another video.")
        return size

    @app.middleware("http")
    async def local_requests(request, call_next):
        origin = request.headers.get("origin")
        if request.method != "GET" and origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse(
                {"detail": "Use the local Nyx page to send requests."}, status_code=403
            )
        response = await call_next(request)
        response.headers["cache-control"] = "no-store"
        return response

    @app.get("/")
    def home():
        return FileResponse(WEB / "index.html")

    @app.get("/app.js")
    def javascript():
        return FileResponse(WEB / "app.js", media_type="text/javascript")

    @app.get("/voice.js")
    def voice_javascript():
        return FileResponse(WEB / "voice.js", media_type="text/javascript")

    @app.get("/audio-worklet.js")
    def audio_worklet():
        return FileResponse(WEB / "audio-worklet.js", media_type="text/javascript")

    @app.get("/api/voice")
    def voice_status():
        return {
            "configured": voice is not None,
            "visual_ready": workspace.verifier is not None,
            "conversations": voice.conversations.recent() if voice else [],
        }

    def voice_token(request):
        if voice is None:
            raise HTTPException(
                503, "Configure Sarvam and install the voice extra to enable listening."
            )
        return request.headers.get("x-nyx-voice")

    @app.post("/api/voice/session")
    def voice_start(request: Request):
        voice_token(request)
        return voice.start()

    @app.delete("/api/voice/session")
    def voice_stop(request: Request):
        voice.stop(voice_token(request))
        return {"state": "muted"}

    @app.post("/api/voice/heartbeat")
    def voice_heartbeat(request: Request):
        return voice.heartbeat(voice_token(request))

    @app.post("/api/voice/cancel")
    def voice_cancel(request: Request):
        voice.cancel(voice_token(request))
        return {"state": "listening"}

    @app.post("/api/voice/listen")
    def voice_listen(request: Request, body: dict):
        return voice.listen(voice_token(request), body.get("turn_id"))

    @app.post("/api/voice/probe")
    async def voice_probe(request: Request):
        token = voice_token(request)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 96000:
                raise HTTPException(413, "Wake samples must be at most 3 seconds.")
        return await run_in_threadpool(voice.probe, token, bytes(raw))

    @app.post("/api/voice/utterance")
    async def voice_utterance(request: Request):
        token = voice_token(request)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_PCM:
                raise HTTPException(413, "Spoken questions must be at most 25 seconds.")
        return await run_in_threadpool(voice.utterance, token, bytes(raw))

    @app.post("/api/voice/reply")
    def voice_reply(request: Request, body: dict):
        token = voice_token(request)
        with voice.lock:
            voice.check(token)
            turn = voice.turn
            if not turn or turn["id"] != body.get("turn_id"):
                raise VoiceError("That voice response is no longer active.")
            plan = turn["plan"]
        if plan["mode"] in {"chat", "clarify"}:
            result = {"answer": plan.get("reply") or "Which object would you like me to look for?"}
        else:
            with workspace.lock:
                job = workspace.jobs.get(body.get("job_id"), {})
                if job.get("kind") not in {"answer", "agent"} or job.get("status") != "succeeded":
                    raise VoiceError("The visual check has not completed. Try again.")
                if job["created_at"] < turn["at"]:
                    raise VoiceError("Capture new evidence for this voice question.")
                result = job["result"]
                if job["kind"] == "agent":
                    if result.get("voice_turn_id") != turn["id"] or job.get("cancelled"):
                        raise VoiceError(
                            "That companion result belongs to another or cancelled turn"
                        )
                elif result.get("object_query") != plan["object_query"]:
                    raise VoiceError("That visual check belongs to a different question.")
                elif (plan["mode"] == "current") != (result["kind"] == "snapshot"):
                    raise VoiceError("The visual check has the wrong evidence type.")
                if result["kind"] == "history" and any(
                    result["scope"].get(field) != plan.get(field)
                    for field in ["seen_after", "seen_before"]
                ):
                    raise VoiceError("The visual check has a different time range.")
                if result["kind"] == "history" and result["scope"]["mode"] != plan["mode"]:
                    raise VoiceError("The history check has a different ordering.")
        return voice.reply(token, body["turn_id"], result)

    @app.get("/style.css")
    def stylesheet():
        return FileResponse(WEB / "style.css", media_type="text/css")

    @app.get("/api/videos")
    def videos():
        store = workspace.store()
        return store.list_videos() if store else []

    @app.delete("/api/videos/{video_id}")
    def delete_video(video_id: str):
        with workspace.upload_slot(), workspace.lock:
            if any(job["status"] not in {"succeeded", "failed"} for job in workspace.jobs.values()):
                raise HTTPException(409, "Wait for indexing and search to finish before deleting.")
            session = workspace.capture.snapshot()["session"]
            if session and session["state"] in {"recording", "paused"}:
                raise HTTPException(409, "Stop recording before deleting a clip.")
            if voice and voice.turn:
                raise HTTPException(409, "Stop the voice response before deleting a clip.")
            try:
                workspace.delete_video(video_id)
            except OSError as exc:
                raise HTTPException(
                    503, "Deletion is incomplete. Retry deletion or restart Nyx to finish cleanup."
                ) from exc
            return {"id": video_id, "deleted": True}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str):
        with workspace.lock:
            if job_id not in workspace.jobs:
                raise HTTPException(404, "Task not found; refresh the clip library.")
            return dict(workspace.jobs[job_id])

    @app.get("/api/capture")
    def capture_status():
        return workspace.capture.snapshot()

    @app.get("/api/capture/segments/{segment_id}/media")
    def saved_segment(segment_id: str):
        try:
            segment = workspace.capture.segment(segment_id)
        except ValueError as exc:
            raise HTTPException(404, "Saved segment not found") from exc
        path = workspace.root / segment["path"]
        if segment["state"] in {"deleting", "deleted"} or not segment["size"] or not path.is_file():
            raise HTTPException(404, "Segment upload did not complete")
        return FileResponse(path)

    @app.post("/api/capture/start")
    def capture_start(body: CaptureStart):
        return workspace.capture.start(body.at.isoformat())

    @app.post("/api/capture/{session_id}/state")
    def capture_state(session_id: str, body: CaptureState):
        if body.state != "recording":
            workspace.observer.reset()
        return workspace.capture.transition(
            session_id, body.state, body.at.isoformat(), body.reason
        )

    @app.post("/api/capture/{session_id}/heartbeat")
    def capture_heartbeat(session_id: str):
        return workspace.capture.heartbeat(session_id)

    @app.post("/api/capture/{session_id}/segments/{sequence}", status_code=202)
    async def capture_segment(
        session_id: str,
        sequence: int,
        request: Request,
        recorded_at: AwareDatetime,
        ended_at: AwareDatetime,
        format: Literal["webm", "mp4"] = "webm",
        timing_uncertain: bool = False,
    ):
        with workspace.upload_slot():
            segment = workspace.capture.begin_segment(
                session_id,
                sequence,
                recorded_at.isoformat(),
                ended_at.isoformat(),
                f".{format}",
                timing_uncertain,
            )
            if segment["state"] == "uploading":
                try:
                    size = await receive_video(
                        request, workspace.capture.partial_path(segment["id"])
                    )
                    segment = workspace.capture.finish_upload(segment["id"], size)
                except BaseException as exc:
                    if workspace.capture.segment(segment["id"])["state"] == "uploading":
                        workspace.capture.partial_path(segment["id"]).unlink(missing_ok=True)
                        workspace.capture.mark(
                            segment["id"], "failed", "Upload failed; segment is not searchable"
                        )
                    if isinstance(exc, HTTPException) and exc.status_code in {413, 507}:
                        workspace.capture.transition(
                            session_id, "interrupted", datetime.now(UTC).isoformat(), exc.detail
                        )
                    raise
            workspace.submit_segment(segment)
            return {"id": segment["id"], "state": segment["state"]}

    @app.post("/api/import", status_code=202)
    async def import_clip(
        request: Request,
        name: str = Query(min_length=1, max_length=200),
        recorded_at: AwareDatetime | None = None,
    ):
        name = Path(name.replace("\\", "/")).name
        if Path(name).suffix.lower() not in {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}:
            raise HTTPException(400, "Choose a video file (MP4, MOV, WebM, MKV or AVI).")
        job_id = workspace.reserve("index")
        incoming = workspace.root / "incoming" / job_id
        path = incoming / name
        try:
            incoming.mkdir(parents=True)
            with workspace.upload_slot():
                await receive_video(request, path)
        except BaseException:
            shutil.rmtree(incoming, ignore_errors=True)
            workspace.update(job_id, status="failed", error="Upload did not complete.")
            raise

        def index():
            try:
                store = workspace.model_store()
                capture_time = recorded_at.astimezone(UTC).isoformat() if recorded_at else None
                return (
                    yield from index_video_batches(
                        path, store, workspace.encoder, recorded_at=capture_time
                    )
                )
            finally:
                shutil.rmtree(incoming, ignore_errors=True)

        workspace.submit(job_id, index)
        return {"id": job_id}

    @app.post("/api/search", status_code=202)
    def query(body: SearchRequest):
        validate_bounds(body)
        job_id = workspace.reserve("search")

        def find():
            if workspace.store() is None:
                raise ValueError("Record or import a clip before searching.")
            store = workspace.model_store()
            results = search(
                body.query,
                store,
                workspace.encoder,
                limit=body.limit,
                video_id=body.video_id,
                seen_after=body.seen_after.isoformat() if body.seen_after else None,
                seen_before=body.seen_before.isoformat() if body.seen_before else None,
                order=body.order,
            )
            for result in results:
                result["thumbnail_url"] = f"/api/frames/{result['id']}"
                result["media_url"] = f"/api/videos/{result['video_id']}/media"
            return {"query": body.query, "verified": False, "results": results}

        workspace.submit(job_id, find)
        return {"id": job_id}

    def validate_bounds(body):
        if body.seen_after and body.seen_before and body.seen_after > body.seen_before:
            raise ValueError("Observation start must not exceed end time")

    @app.post("/api/answer", status_code=202)
    def answer(body: AnswerRequest):
        validate_bounds(body)
        job_id = workspace.reserve("answer")

        def inspect_history():
            if workspace.store() is None:
                raise ValueError("Record or import a clip before checking history.")
            store = workspace.model_store()
            result = yield from history_steps(
                body.object_query,
                store,
                workspace.encoder,
                workspace.visual_verifier,
                mode=body.mode,
                video_id=body.video_id,
                seen_after=body.seen_after.isoformat() if body.seen_after else None,
                seen_before=body.seen_before.isoformat() if body.seen_before else None,
            )
            coverage = workspace.capture.snapshot()
            result["coverage"] = {
                key: coverage[key]
                for key in ["recorded_through", "searchable_through", "counts", "events"]
            }
            return result

        workspace.submit(job_id, inspect_history)
        return {"id": job_id}

    def snapshot_age(captured_at):
        age = (datetime.now(UTC) - captured_at).total_seconds()
        if age < -2 or age > 15:
            raise ValueError(
                "Snapshot is stale or its clock is ahead; capture a fresh view and try again."
            )
        return age

    @app.post("/api/inspect", status_code=202)
    async def inspect_snapshot(
        request: Request,
        captured_at: AwareDatetime,
        object_query: str = Query(min_length=1, max_length=200, pattern=r"\S"),
    ):
        snapshot_age(captured_at)
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 2 * 1024**2:
                raise HTTPException(413, "Snapshot must be at most 2 MiB")
        try:
            with Image.open(BytesIO(raw)) as source:
                if (
                    source.format not in {"JPEG", "PNG"}
                    or source.width * source.height > 1920 * 1080
                ):
                    raise ValueError("Use a JPEG/PNG snapshot of at most two megapixels")
                mime = "image/jpeg" if source.format == "JPEG" else "image/png"
                image = source.convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("Snapshot is not a readable image") from exc
        job_id = workspace.reserve("answer")

        def inspect():
            snapshot_age(captured_at)
            verifier = workspace.visual_verifier()
            snapshot_age(captured_at)
            judgment = verifier.inspect(image, object_query)
            seen = judgment["visibility"] == "visible"
            description = (
                f"The model identified {object_query} {judgment['location'] or 'in the image'}."
                if seen
                else f"I couldn't clearly confirm {object_query}. This does not prove it is absent."
            )
            return {
                "kind": "snapshot",
                "object_query": object_query,
                "status": "seen" if seen else "uncertain",
                "answer": f"In the snapshot captured at {captured_at.astimezone(UTC).isoformat()}: {description} The scene may have changed since capture.",
                "captured_at": captured_at.astimezone(UTC).isoformat(),
                "age_seconds": (datetime.now(UTC) - captured_at).total_seconds(),
                "judgment": judgment,
                "verifier": verifier.fingerprint,
                "snapshot_url": f"data:{mime};base64,{base64.b64encode(raw).decode()}",
                "scope": {
                    "note": "One explicitly captured snapshot; it is not continuous current evidence and is not permanently saved. Model judgments can be wrong."
                },
            }

        workspace.submit(job_id, inspect)
        return {"id": job_id}

    def media_file(sql, identifier):
        store = workspace.store()
        if store is None:
            raise HTTPException(404, "Source not found.")
        with store.connection() as db:
            record = db.execute(sql, (identifier,)).fetchone()
        if record is None:
            raise HTTPException(404, "Source not found.")
        path = (store.root / record[0]).resolve()
        if not path.is_relative_to(store.root) or not path.is_file():
            raise HTTPException(404, "Source file is unavailable.")
        return FileResponse(path)

    @app.get("/api/videos/{video_id}/media")
    def source(video_id: str):
        return media_file("SELECT path FROM videos WHERE id = ? AND status = 'ready'", video_id)

    @app.get("/api/frames/{frame_id}")
    def thumbnail(frame_id: int):
        return media_file(
            """SELECT f.thumbnail FROM frames f JOIN videos v ON v.id = f.video_id
            WHERE f.id = ? AND v.status = 'ready'""",
            frame_id,
        )

    return app
