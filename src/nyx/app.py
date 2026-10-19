import json
import shutil
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import AwareDatetime, BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from nyx.memory import Store
from nyx.retrieval import index_video, search

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
WEB = Path(__file__).with_name("web")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    video_id: str | None = None
    limit: int = Field(default=5, ge=1, le=100)


class Workspace:
    def __init__(self, root, encoder_factory):
        self.root = Path(root).resolve()
        self.encoder_factory = encoder_factory
        self.encoder = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nyx-inference")
        self.lock = Lock()
        self.store_lock = Lock()
        self.jobs = {}
        self.active = None

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

    def reserve(self, kind):
        with self.lock:
            if self.active:
                raise HTTPException(409, "Nyx is busy. Wait for the current task to finish.")
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = {
                "id": job_id,
                "kind": kind,
                "status": "uploading" if kind == "index" else "queued",
            }
            self.active = job_id
            if len(self.jobs) > 20:
                del self.jobs[next(iter(self.jobs))]
            return job_id

    def update(self, job_id, **changes):
        with self.lock:
            self.jobs[job_id].update(changes)
            if changes.get("status") in {"succeeded", "failed"}:
                self.active = None

    def submit(self, job_id, action):
        def run():
            self.update(job_id, status="running")
            try:
                result = action()
            except Exception as exc:  # noqa: BLE001 — worker failures must reach the task UI
                self.update(job_id, status="failed", error=str(exc))
            else:
                self.update(job_id, status="succeeded", result=result)

        self.pool.submit(run)


def create_app(
    root=Path("data"), device="auto", encoder_factory=None, max_upload_bytes=MAX_UPLOAD_BYTES
):
    if encoder_factory is None:

        def encoder_factory():
            from nyx.perception import SiglipEncoder

            return SiglipEncoder(device)

    workspace = Workspace(root, encoder_factory)

    @asynccontextmanager
    async def lifespan(app):
        yield
        workspace.pool.shutdown(wait=True)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

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
            size = 0
            with path.open("wb") as file:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > max_upload_bytes:
                        raise HTTPException(
                            413, "Clip exceeds the upload limit; use a shorter video."
                        )
                    file.write(chunk)
            if not size:
                raise HTTPException(400, "The clip is empty; choose or record another video.")
        except BaseException:
            shutil.rmtree(incoming, ignore_errors=True)
            workspace.update(job_id, status="failed", error="Upload did not complete.")
            raise

        def index():
            try:
                store = workspace.model_store()
                capture_time = recorded_at.astimezone(UTC).isoformat() if recorded_at else None
                return index_video(path, store, workspace.encoder, recorded_at=capture_time)
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
