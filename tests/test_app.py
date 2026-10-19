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


def test_web_worker_accepts_one_search_while_indexing_and_bounds_extra_jobs(tmp_path, video):
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
            query = client.post("/api/search", json={"query": "green"})
            assert query.status_code == 202
            assert client.post("/api/search", json={"query": "green"}).status_code == 409
            assert client.post("/api/import?name=other.mp4", content=b"data").status_code == 409
            release.set()
            assert wait_for_job(client, response.json()["id"])["status"] == "succeeded"
            assert wait_for_job(client, query.json()["id"])["status"] == "succeeded"
    finally:
        release.set()


def test_search_has_priority_between_background_index_batches(tmp_path, video):
    from nyx.memory import Store
    from nyx.retrieval import index_video

    store = Store(tmp_path, ColorEncoder.fingerprint, 3)
    baseline = index_video(video, store, ColorEncoder())
    entered, release = Event(), Event()

    class SlowImages(ColorEncoder):
        def encode_images(self, images):
            entered.set()
            assert release.wait(5)
            return super().encode_images(images)

    try:
        with TestClient(create_app(tmp_path, encoder_factory=SlowImages)) as client:
            background = client.post("/api/import?name=new.mp4", content=video.read_bytes()).json()
            assert entered.wait(2)
            query = client.post("/api/search", json={"query": "green"}).json()
            release.set()
            results = wait_for_job(client, query["id"])["result"]["results"]
            assert {row["video_id"] for row in results} == {baseline["video_id"]}
            assert wait_for_job(client, background["id"])["status"] == "succeeded"
    finally:
        release.set()


def test_continuous_segment_is_saved_indexed_and_delivered_once(tmp_path, video):
    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        started = client.post("/api/capture/start", json={"at": "2026-10-19T10:00:00Z"})
        assert started.status_code == 200
        session_id = started.json()["id"]
        params = {
            "recorded_at": "2026-10-19T10:00:00Z",
            "ended_at": "2026-10-19T10:00:04Z",
            "format": "mp4",
        }
        segment = client.post(
            f"/api/capture/{session_id}/segments/0", params=params, content=video.read_bytes()
        )
        assert segment.status_code == 202
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = client.get("/api/capture").json()
            if status["counts"].get("ready") == 1:
                break
            time.sleep(0.01)
        assert status["searchable_through"] == "2026-10-19T10:00:02+00:00"
        repeat = client.post(
            f"/api/capture/{session_id}/segments/0", params=params, content=video.read_bytes()
        )
        assert repeat.json()["id"] == segment.json()["id"]
        assert len(client.get("/api/videos").json()) == 1
        query = client.post("/api/search", json={"query": "green"}).json()
        assert wait_for_job(client, query["id"])["result"]["results"][0]["offset_seconds"] == 2
        client.post(
            f"/api/capture/{session_id}/state",
            json={"state": "stopped", "at": "2026-10-19T10:00:04Z", "reason": "Stopped by user"},
        )
    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        assert len(client.get("/api/videos").json()) == 1
        assert client.get("/api/capture").json()["session"]["state"] == "stopped"


def test_saved_segment_is_recovered_without_camera_access(tmp_path, video):
    from nyx.recording import CaptureJournal

    journal = CaptureJournal(tmp_path)
    session = journal.start("2026-10-19T10:00:00Z")
    segment = journal.begin_segment(
        session["id"], 0, "2026-10-19T10:00:00Z", "2026-10-19T10:00:04Z", ".mp4"
    )
    journal.partial_path(segment["id"]).write_bytes(video.read_bytes())
    journal.finish_upload(segment["id"], video.stat().st_size)
    journal.mark(segment["id"], "indexing")
    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not client.get("/api/videos").json():
            time.sleep(0.01)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = client.get("/api/capture").json()
            if state["counts"].get("ready") == 1:
                break
            time.sleep(0.01)
        assert state["counts"]["ready"] == 1
        assert state["session"]["state"] == "interrupted"
        assert client.get("/api/videos").json()[0]["id"] == segment["id"]


def test_capture_budget_failure_keeps_old_video_and_stops_session(tmp_path, video):
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    old = recordings / "old.mp4"
    old.write_bytes(b"previous video")
    with TestClient(
        create_app(
            tmp_path, encoder_factory=ColorEncoder, video_budget_bytes=old.stat().st_size + 8
        )
    ) as client:
        session = client.post("/api/capture/start", json={"at": "2026-10-19T10:00:00Z"}).json()
        response = client.post(
            f"/api/capture/{session['id']}/segments/0",
            params={
                "recorded_at": "2026-10-19T10:00:00Z",
                "ended_at": "2026-10-19T10:00:04Z",
                "format": "mp4",
            },
            content=video.read_bytes(),
        )
        assert response.status_code == 413
        assert client.get("/api/capture").json()["session"]["state"] == "interrupted"
        assert list((tmp_path / "incoming").iterdir()) == []
        assert old.read_bytes() == b"previous video"


def test_saved_but_unindexed_capture_stays_playable_when_model_is_unavailable(tmp_path, video):
    def broken_model():
        raise RuntimeError("model unavailable")

    with TestClient(create_app(tmp_path, encoder_factory=broken_model)) as client:
        session = client.post("/api/capture/start", json={"at": "2026-10-19T10:00:00Z"}).json()
        response = client.post(
            f"/api/capture/{session['id']}/segments/0",
            params={
                "recorded_at": "2026-10-19T10:00:00Z",
                "ended_at": "2026-10-19T10:00:04Z",
                "format": "mp4",
            },
            content=video.read_bytes(),
        )
        segment_id = response.json()["id"]
        source = client.get(
            f"/api/capture/segments/{segment_id}/media", headers={"range": "bytes=0-7"}
        )
        assert source.status_code == 206
        assert source.content == video.read_bytes()[:8]
        assert client.get("/api/videos").json() == []


def test_interrupted_capture_indexes_clip_offsets_without_inventing_frame_clock_time(
    tmp_path, video
):
    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        session = client.post("/api/capture/start", json={"at": "2026-10-19T10:00:00Z"}).json()
        response = client.post(
            f"/api/capture/{session['id']}/segments/0",
            params={
                "recorded_at": "2026-10-19T10:00:00Z",
                "ended_at": "2026-10-19T10:00:04Z",
                "format": "mp4",
                "timing_uncertain": "true",
            },
            content=video.read_bytes(),
        )
        assert wait_for_job(client, response.json()["id"])["status"] == "succeeded"
        assert client.get("/api/videos").json()[0]["recorded_at"] is None


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
