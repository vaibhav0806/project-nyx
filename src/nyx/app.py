import json
import shutil
import sqlite3
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from queue import PriorityQueue
from threading import Lock, Thread
from types import GeneratorType
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import AwareDatetime, BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from nyx.memory import Store
from nyx.recording import CaptureJournal
from nyx.retrieval import index_video_batches, search

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
WEB = Path(__file__).with_name("web")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    video_id: str | None = None
    limit: int = Field(default=5, ge=1, le=100)


class CaptureStart(BaseModel):
    at: AwareDatetime


class CaptureState(CaptureStart):
    state: Literal["recording", "paused", "stopped", "interrupted"]
    reason: str = Field(min_length=1, max_length=300)


class Workspace:
    def __init__(self, root, encoder_factory, video_budget_bytes):
        self.root = Path(root).resolve()
        self.encoder_factory = encoder_factory
        self.encoder = None
        self.queue = PriorityQueue()
        self.order = count()
        self.thread = Thread(target=self.run, name="nyx-inference", daemon=True)
        self.lock = Lock()
        self.store_lock = Lock()
        self.upload_lock = Lock()
        self.jobs = {}
        self.scheduled = set()
        self.capture = CaptureJournal(self.root, video_budget_bytes)

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
        priority = 0 if self.jobs[job_id]["kind"] == "search" else 1
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


def create_app(
    root=Path("data"),
    device="auto",
    encoder_factory=None,
    max_upload_bytes=MAX_UPLOAD_BYTES,
    video_budget_bytes=1024**3,
):
    if encoder_factory is None:

        def encoder_factory():
            from nyx.perception import SiglipEncoder

            return SiglipEncoder(device)

    workspace = Workspace(root, encoder_factory, video_budget_bytes)

    @asynccontextmanager
    async def lifespan(app):
        workspace.capture.recover()
        for segment in workspace.capture.pending():
            workspace.submit_segment(segment)
        workspace.thread.start()
        yield
        workspace.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

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

    @app.get("/style.css")
    def stylesheet():
        return FileResponse(WEB / "style.css", media_type="text/css")

    @app.get("/api/videos")
    def videos():
        store = workspace.store()
        return store.list_videos() if store else []

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
        if not segment["size"] or not path.is_file():
            raise HTTPException(404, "Segment upload did not complete")
        return FileResponse(path)

    @app.post("/api/capture/start")
    def capture_start(body: CaptureStart):
        return workspace.capture.start(body.at.isoformat())

    @app.post("/api/capture/{session_id}/state")
    def capture_state(session_id: str, body: CaptureState):
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
        job_id = workspace.reserve("search")

        def find():
            if workspace.store() is None:
                raise ValueError("Record or import a clip before searching.")
            store = workspace.model_store()
            results = search(
                body.query, store, workspace.encoder, limit=body.limit, video_id=body.video_id
            )
            for result in results:
                result["thumbnail_url"] = f"/api/frames/{result['id']}"
                result["media_url"] = f"/api/videos/{result['video_id']}/media"
            return {"query": body.query, "verified": False, "results": results}

        workspace.submit(job_id, find)
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
