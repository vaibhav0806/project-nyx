import time
from threading import Event
from typing import ClassVar

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


def import_ready(client, video, name="desk.mp4"):
    job = client.post("/api/import", params={"name": name}, content=video.read_bytes()).json()
    result = wait_for_job(client, job["id"])
    assert result["status"] == "succeeded"
    return result["result"]["video_id"]


def test_delete_source_removes_video_thumbnails_vectors_and_preserves_other_clips(tmp_path, video):
    import sqlite3

    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        removed = import_ready(client, video)
        retained = import_ready(client, video, "retained.mp4")
        query = client.post("/api/search", json={"query": "green", "video_id": removed}).json()
        old = wait_for_job(client, query["id"])["result"]["results"][0]
        assert client.delete(f"/api/videos/{removed}").status_code == 200
        assert not list((tmp_path / "recordings").glob(f"{removed}.*"))
        assert not (tmp_path / "frames" / removed).exists()
        assert client.get(old["media_url"]).status_code == 404
        assert client.get(old["thumbnail_url"]).status_code == 404
        with sqlite3.connect(tmp_path / "index.sqlite3") as db:
            assert (
                db.execute("SELECT COUNT(*) FROM frames WHERE video_id = ?", (removed,)).fetchone()[
                    0
                ]
                == 0
            )
        assert [row["id"] for row in client.get("/api/videos").json()] == [retained]
    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        query = client.post("/api/search", json={"query": "green"}).json()
        assert {
            row["video_id"] for row in wait_for_job(client, query["id"])["result"]["results"]
        } == {retained}


@pytest.mark.parametrize("legacy_index", [False, True])
def test_deleted_thumbnail_url_cannot_alias_newly_indexed_evidence(tmp_path, video, legacy_index):
    import sqlite3

    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        removed = import_ready(client, video)
        query = client.post("/api/search", json={"query": "green"}).json()
        old = wait_for_job(client, query["id"])["result"]["results"][0]
        if legacy_index:
            with sqlite3.connect(tmp_path / "index.sqlite3") as db:
                db.execute("DELETE FROM meta WHERE key = 'next_frame_id'")
        assert client.delete(f"/api/videos/{removed}").status_code == 200
        import_ready(client, video, "new.mp4")
        assert client.get(old["thumbnail_url"]).status_code == 404


def test_delete_failed_capture_without_loading_model_and_prevent_duplicate_resurrection(
    tmp_path, video
):
    from nyx.recording import CaptureJournal

    journal = CaptureJournal(tmp_path)
    session = journal.start("2026-10-19T10:00:00Z")
    segment = journal.begin_segment(
        session["id"], 0, "2026-10-19T10:00:00Z", "2026-10-19T10:00:04Z", ".mp4"
    )
    journal.partial_path(segment["id"]).write_bytes(video.read_bytes())
    journal.finish_upload(segment["id"], video.stat().st_size)
    journal.mark(segment["id"], "failed", "No model")
    journal.transition(session["id"], "stopped", "2026-10-19T10:00:04Z", "Stopped")

    def no_model():
        pytest.fail("Deleting a source must not load a model")

    with TestClient(create_app(tmp_path, encoder_factory=no_model)) as client:
        assert client.delete(f"/api/videos/{segment['id']}").status_code == 200
        status = client.get("/api/capture").json()
        assert status["video_bytes"] == 0
        assert status["recorded_through"] is None
        assert status["searchable_through"] is None
        duplicate = client.post(
            f"/api/capture/{session['id']}/segments/0",
            params={
                "recorded_at": "2026-10-19T10:00:00Z",
                "ended_at": "2026-10-19T10:00:04Z",
                "format": "mp4",
            },
            content=video.read_bytes(),
        )
        assert duplicate.json()["state"] == "deleted"
        assert client.get("/api/capture").json()["video_bytes"] == 0
        assert client.delete(f"/api/videos/{segment['id']}").status_code == 200


def test_delete_failure_hides_evidence_and_startup_completes_removal(tmp_path, video, monkeypatch):
    from pathlib import Path

    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        source_id = import_ready(client, video)
        original_unlink = Path.unlink

        def fail_video(path, *args, **kwargs):
            if path.parent == tmp_path / "recordings":
                raise OSError("test disk failure")
            return original_unlink(path, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(Path, "unlink", fail_video)
            assert client.delete(f"/api/videos/{source_id}").status_code == 503
        assert client.get(f"/api/videos/{source_id}/media").status_code == 404
        query = client.post("/api/search", json={"query": "green"}).json()
        assert wait_for_job(client, query["id"])["result"]["results"] == []
    with TestClient(
        create_app(tmp_path, encoder_factory=lambda: pytest.fail("No model needed"))
    ) as client:
        assert client.get("/api/videos").json() == []
        assert not list((tmp_path / "recordings").glob(f"{source_id}.*"))
        assert not (tmp_path / "frames" / source_id).exists()


def test_delete_rejects_active_work_and_foreign_origin(tmp_path, video):
    entered, release = Event(), Event()

    class SlowEncoder(ColorEncoder):
        def encode_images(self, images):
            entered.set()
            assert release.wait(5)
            return super().encode_images(images)

    try:
        with TestClient(create_app(tmp_path, encoder_factory=SlowEncoder)) as client:
            client.post("/api/import?name=desk.mp4", content=video.read_bytes())
            assert entered.wait(2)
            source_id = client.get("/api/videos").json()[0]["id"]
            assert client.delete(f"/api/videos/{source_id}").status_code == 409
            assert (
                client.delete(
                    f"/api/videos/{source_id}", headers={"origin": "https://elsewhere.example"}
                ).status_code
                == 403
            )
            release.set()
    finally:
        release.set()


def test_delete_rejects_unregistered_and_escaping_sources(tmp_path, video):
    import sqlite3

    outside = tmp_path.parent / f"{tmp_path.name}-outside.mp4"
    outside.write_bytes(b"keep")
    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        assert client.delete("/api/videos/unknown").status_code == 404
        source_id = import_ready(client, video)
        with sqlite3.connect(tmp_path / "index.sqlite3") as db:
            db.execute("UPDATE videos SET path = ? WHERE id = ?", (str(outside), source_id))
        assert client.delete(f"/api/videos/{source_id}").status_code == 400
        assert outside.read_bytes() == b"keep"


def test_delete_requires_recording_stopped(tmp_path, video):
    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        source_id = import_ready(client, video)
        session = client.post("/api/capture/start", json={"at": "2026-10-19T10:00:00Z"}).json()
        assert client.delete(f"/api/videos/{source_id}").status_code == 409
        client.post(
            f"/api/capture/{session['id']}/state",
            json={"state": "paused", "at": "2026-10-19T10:00:01Z", "reason": "Pause"},
        )
        assert client.delete(f"/api/videos/{source_id}").status_code == 409
        assert client.get(f"/api/videos/{source_id}/media").status_code == 200


def test_pending_delete_with_persistent_disk_failure_keeps_app_available(
    tmp_path, video, monkeypatch
):
    from pathlib import Path

    from nyx.recording import CaptureJournal

    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        source_id = import_ready(client, video)
    journal = CaptureJournal(tmp_path)
    journal.request_deletion(source_id, f"recordings/{source_id}.mp4")
    original_unlink = Path.unlink

    def fail_video(path, *args, **kwargs):
        if path.parent == tmp_path / "recordings":
            raise OSError("test disk failure")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_video)
        with TestClient(
            create_app(tmp_path, encoder_factory=lambda: pytest.fail("No model needed"))
        ) as client:
            assert client.get("/").status_code == 200
            assert client.get(f"/api/videos/{source_id}/media").status_code == 404
            assert client.get("/api/videos").json()[0]["status"] == "deleting"
    with TestClient(
        create_app(tmp_path, encoder_factory=lambda: pytest.fail("No model needed"))
    ) as client:
        assert client.get("/api/videos").json() == []


def test_history_answer_has_time_evidence_and_is_invalidated_by_deletion(tmp_path, video):
    class VisibleVerifier:
        fingerprint: ClassVar[dict] = {"model": "test-verifier"}

        def inspect(self, image, object_query):
            assert image.size == (64, 64)
            assert object_query == "green"
            return {"visibility": "visible", "location": "center", "description": "Green visible"}

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=VisibleVerifier)
    ) as client:
        response = client.post(
            "/api/import",
            params={"name": "dated.mp4", "recorded_at": "2026-10-19T10:00:00Z"},
            content=video.read_bytes(),
        )
        source_id = wait_for_job(client, response.json()["id"])["result"]["video_id"]
        request = client.post(
            "/api/answer",
            json={
                "object_query": "green",
                "mode": "latest",
                "seen_after": "2026-10-19T10:00:01Z",
                "seen_before": "2026-10-19T10:00:03Z",
            },
        )
        job_id = request.json()["id"]
        answer = wait_for_job(client, job_id)["result"]
        assert answer["evidence"]["observed_at"] == "2026-10-19T10:00:02+00:00"
        assert answer["verifier"]["model"] == "test-verifier"
        assert [row["offset_seconds"] for row in answer["evidence"]["context"]] == [2]
        assert client.get(answer["evidence"]["media_url"]).status_code == 200
        assert client.delete(f"/api/videos/{source_id}").status_code == 200
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "failed"
        assert (
            client.post(
                "/api/answer", json={"object_query": "green", "seen_after": "2026-10-19T10:00:00"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/answer",
                json={
                    "object_query": "green",
                    "seen_after": "2026-10-19T12:00:00Z",
                    "seen_before": "2026-10-19T10:00:00Z",
                },
            ).status_code
            == 400
        )


def test_fresh_snapshot_checks_exact_image_and_rejects_stale_or_invalid_input(tmp_path):
    from datetime import UTC, datetime, timedelta
    from io import BytesIO

    from PIL import Image

    class SnapshotVerifier:
        fingerprint: ClassVar[dict] = {"model": "snapshot-test"}

        def inspect(self, image, object_query):
            assert image.size == (80, 60)
            assert object_query == "green"
            return {"visibility": "visible", "location": "center", "description": "Green visible"}

    buffer = BytesIO()
    Image.new("RGB", (80, 60), "lime").save(buffer, format="JPEG")
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=SnapshotVerifier)
    ) as client:
        params = {"object_query": "green", "captured_at": datetime.now(UTC).isoformat()}
        response = client.post("/api/inspect", params=params, content=buffer.getvalue())
        result = wait_for_job(client, response.json()["id"])["result"]
        assert result["kind"] == "snapshot"
        assert result["snapshot_url"].startswith("data:image/jpeg;base64,")
        assert "snapshot" in result["answer"]
        assert not (tmp_path / "inspections").exists()
        params["captured_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
        assert (
            client.post("/api/inspect", params=params, content=buffer.getvalue()).status_code == 400
        )
        params["captured_at"] = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
        assert (
            client.post("/api/inspect", params=params, content=buffer.getvalue()).status_code == 400
        )
        params["captured_at"] = datetime.now(UTC).isoformat()
        assert client.post("/api/inspect", params=params, content=b"invalid").status_code == 400
        assert (
            client.post("/api/inspect", params=params, content=b"x" * (2 * 1024**2 + 1)).status_code
            == 413
        )


def test_snapshot_expiring_in_queue_never_reaches_the_visual_model(tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from io import BytesIO

    from PIL import Image

    import nyx.app as app_module

    now = datetime.now(UTC)

    class QueueClock:
        calls = 0

        @classmethod
        def now(cls, timezone):
            cls.calls += 1
            return now if cls.calls == 1 else now + timedelta(seconds=16)

    image = BytesIO()
    Image.new("RGB", (16, 16), "white").save(image, format="PNG")
    monkeypatch.setattr(app_module, "datetime", QueueClock)
    with TestClient(
        create_app(
            tmp_path,
            encoder_factory=ColorEncoder,
            verifier_factory=lambda: pytest.fail("Expired evidence must not be inspected"),
        )
    ) as client:
        response = client.post(
            "/api/inspect",
            params={"object_query": "keys", "captured_at": now.isoformat()},
            content=image.getvalue(),
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "failed"
        assert "stale" in job["error"]


def test_snapshot_expiring_during_model_load_is_not_inspected(tmp_path, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from io import BytesIO

    from PIL import Image

    import nyx.app as app_module

    captured_time = datetime.now(UTC)

    class Clock:
        current = captured_time

        @classmethod
        def now(cls, timezone):
            return cls.current

    class Verifier:
        def inspect(self, image, object_query):
            raise AssertionError("Model load expired this snapshot; request a new image")

    def load_model():
        Clock.current = captured_time + timedelta(seconds=16)
        return Verifier()

    data = BytesIO()
    Image.new("RGB", (16, 16), "white").save(data, format="PNG")
    monkeypatch.setattr(app_module, "datetime", Clock)
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=load_model)
    ) as client:
        response = client.post(
            "/api/inspect",
            params={"object_query": "keys", "captured_at": captured_time.isoformat()},
            content=data.getvalue(),
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "failed"
        assert "stale" in job["error"]


def test_visual_work_is_bounded_while_controls_and_search_requests_stay_responsive(tmp_path, video):
    entered, release = Event(), Event()

    class SlowVerifier:
        fingerprint: ClassVar[dict] = {"model": "slow-test"}

        def inspect(self, image, object_query):
            entered.set()
            assert release.wait(5)
            return {
                "visibility": "visible",
                "location": "center",
                "description": "Test observation",
            }

    try:
        with TestClient(
            create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=SlowVerifier)
        ) as client:
            import_ready(client, video)
            first = client.post(
                "/api/answer", json={"object_query": "green", "mode": "relevance"}
            ).json()
            assert entered.wait(2)
            assert client.get("/api/capture").status_code == 200
            assert client.post("/api/answer", json={"object_query": "green"}).status_code == 409
            search = client.post("/api/search", json={"query": "green"})
            assert search.status_code == 202
            release.set()
            assert wait_for_job(client, search.json()["id"])["status"] == "succeeded"
            assert wait_for_job(client, first["id"])["status"] == "succeeded"
    finally:
        release.set()
