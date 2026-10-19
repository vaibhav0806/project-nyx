import time
from threading import Event

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from test_nyx import ColorEncoder

from nyx.app import create_app

pytest_plugins = ["test_nyx"]


def wait_for_job(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.01)
    pytest.fail("Job did not finish")


def test_web_import_search_playback_and_reopen_preserve_evidence(tmp_path, video):
    root = tmp_path / "data"
    with TestClient(create_app(root, encoder_factory=ColorEncoder)) as client:
        assert client.get("/api/videos").json() == []
        response = client.post(
            "/api/import", params={"name": "desk.mp4"}, content=video.read_bytes()
        )
        assert response.status_code == 202
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded"
        assert job["result"]["frame_count"] == 2
        records = client.get("/api/videos").json()
        assert records[0]["name"] == "desk.mp4"
        assert records[0]["recorded_at"] is None
        query = client.post("/api/search", json={"query": "green"})
        matches = wait_for_job(client, query.json()["id"])["result"]["results"]
        assert matches[0]["offset_seconds"] == 2
        assert matches[0]["verified"] is False
        assert client.get(matches[0]["thumbnail_url"]).headers["content-type"] == "image/jpeg"
        source = client.get(matches[0]["media_url"], headers={"range": "bytes=0-7"})
        assert source.status_code == 206
        assert source.content == video.read_bytes()[:8]
        assert source.headers["content-range"].startswith("bytes 0-7/")
    with TestClient(create_app(root, encoder_factory=ColorEncoder)) as client:
        assert client.get("/api/videos").json()[0]["frame_count"] == 2
        query = client.post("/api/search", json={"query": "green"})
        assert wait_for_job(client, query.json()["id"])["status"] == "succeeded"


def test_web_index_failure_cleans_upload_and_excludes_evidence(tmp_path):
    root = tmp_path / "data"
    with TestClient(create_app(root, encoder_factory=ColorEncoder)) as client:
        response = client.post("/api/import", params={"name": "bad.mp4"}, content=b"invalid video")
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "failed"
        assert "video" in job["error"].lower()
        record = client.get("/api/videos").json()[0]
        assert record["status"] == "failed"
        assert record["frame_count"] == 0
        assert client.get(f"/api/videos/{record['id']}/media").status_code == 404
        assert list((root / "incoming").iterdir()) == []


def test_web_rejects_empty_large_or_invalid_uploads_without_loading_model(tmp_path):
    def no_model():
        pytest.fail("Invalid input must not load a model")

    root = tmp_path / "data"
    with TestClient(create_app(root, encoder_factory=no_model, max_upload_bytes=8)) as client:
        assert client.get("/").status_code == 200
        assert client.post("/api/import?name=empty.mp4", content=b"").status_code == 400
        assert client.post("/api/import?name=large.mp4", content=b"x" * 9).status_code == 413
        streamed = client.post("/api/import?name=large.mp4", content=iter([b"1234", b"56789"]))
        assert streamed.status_code == 413
        assert client.post("/api/import?name=bad.txt", content=b"data").status_code == 400
        assert (
            client.post(
                "/api/import?name=clip.mp4&recorded_at=2026-10-19T10:00:00", content=b"x"
            ).status_code
            == 422
        )
        assert client.post("/api/search", json={"query": " "}).status_code == 422
        assert client.get("/api/videos").json() == []
        assert not (root / "index.sqlite3").exists()
        assert list((root / "incoming").glob("*")) == []


def test_web_busy_worker_rejects_extra_inference_without_blocking_status(tmp_path, video):
    entered, release = Event(), Event()

    def slow_model():
        entered.set()
        assert release.wait(5)
        return ColorEncoder()

    try:
        with TestClient(create_app(tmp_path, encoder_factory=slow_model)) as client:
            response = client.post("/api/import?name=clip.mp4", content=video.read_bytes())
            assert entered.wait(2)
            assert client.get(f"/api/jobs/{response.json()['id']}").json()["status"] == "running"
            assert client.get("/api/videos").status_code == 200
            assert client.post("/api/search", json={"query": "green"}).status_code == 409
            assert client.post("/api/import?name=other.mp4", content=b"data").status_code == 409
            release.set()
            assert wait_for_job(client, response.json()["id"])["status"] == "succeeded"
    finally:
        release.set()


def test_web_preserves_capture_time_and_limits_source_access(tmp_path, video):
    with TestClient(create_app(tmp_path / "data", encoder_factory=ColorEncoder)) as client:
        response = client.post(
            "/api/import",
            params={"name": "../../clip.mp4", "recorded_at": "2026-10-19T10:00:00+05:30"},
            content=video.read_bytes(),
        )
        assert wait_for_job(client, response.json()["id"])["status"] == "succeeded"
        record = client.get("/api/videos").json()[0]
        assert record["name"] == "clip.mp4"
        assert record["recorded_at"] == "2026-10-19T04:30:00+00:00"
        assert client.get("/api/videos/missing/media").status_code == 404
        assert client.get("/api/frames/99999").status_code == 404
        assert client.get("/data/index.sqlite3").status_code == 404
        assert (
            client.get(
                "/api/videos/missing/media", headers={"host": "attacker.example"}
            ).status_code
            == 400
        )
        blocked = client.post(
            "/api/import?name=clip.mp4",
            content=b"x",
            headers={"origin": "https://attacker.example"},
        )
        assert blocked.status_code == 403


def test_web_library_waits_for_first_database_initialization(tmp_path, video, monkeypatch):
    import sqlite3
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

    import nyx.app as app_module

    initializing, release = Event(), Event()
    real_store = app_module.Store

    class SlowStore(real_store):
        def __init__(self, root, fingerprint, dimensions):
            if not (root / "index.sqlite3").exists():
                root.mkdir(parents=True, exist_ok=True)
                sqlite3.connect(root / "index.sqlite3").close()
                initializing.set()
                assert release.wait(5)
            super().__init__(root, fingerprint, dimensions)

    monkeypatch.setattr(app_module, "Store", SlowStore)
    try:
        with TestClient(
            create_app(tmp_path, encoder_factory=ColorEncoder), raise_server_exceptions=False
        ) as client:
            response = client.post("/api/import?name=clip.mp4", content=video.read_bytes())
            assert initializing.wait(2)
            with ThreadPoolExecutor(max_workers=1) as readers:
                listing = readers.submit(client.get, "/api/videos")
                try:
                    listing.result(timeout=0.1)
                except TimeoutError:
                    pass
                release.set()
                assert listing.result(timeout=2).status_code == 200
            assert wait_for_job(client, response.json()["id"])["status"] == "succeeded"
    finally:
        release.set()


def test_disconnected_upload_removes_partial_file_and_releases_task(tmp_path):
    import asyncio

    from starlette.requests import ClientDisconnect

    app = create_app(tmp_path, encoder_factory=ColorEncoder)

    async def disconnect_during_upload():
        events = iter(
            [
                {"type": "http.request", "body": b"partial video", "more_body": True},
                {"type": "http.disconnect"},
            ]
        )

        async def receive():
            return next(events, {"type": "http.disconnect"})

        async def send(message):
            pass

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/import",
            "raw_path": b"/api/import",
            "query_string": b"name=partial.mp4",
            "headers": [(b"host", b"testserver")],
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "root_path": "",
        }
        with pytest.raises(ClientDisconnect):
            await app(scope, receive, send)

    with TestClient(app) as client:
        asyncio.run(disconnect_during_upload())
        assert list((tmp_path / "incoming").iterdir()) == []
        assert client.get("/api/videos").json() == []
        response = client.post("/api/import?name=next.mp4", content=b"invalid video")
        assert response.status_code == 202
        assert wait_for_job(client, response.json()["id"])["status"] == "failed"
