"""Human review preserves source attribution without promoting model guesses to identity."""

from typing import ClassVar
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_app import wait_for_job
from test_nyx import ColorEncoder

from nyx.app import create_app

pytest_plugins = ["test_nyx"]


class CandidateVerifier:
    fingerprint: ClassVar[dict] = {"model": "deliberately-permissive-fixture"}

    def inspect(self, image, query):
        return {"visibility": "visible", "location": "center", "description": "Possible object"}


@pytest.mark.parametrize("recorded_at", [None, "2026-10-19T10:00:00+00:00"])
def test_reject_confirm_replay_restart_and_source_deletion(tmp_path, video, recorded_at):
    def app():
        return create_app(
            tmp_path, encoder_factory=ColorEncoder, verifier_factory=CandidateVerifier
        )

    with TestClient(app()) as client:
        params = {"name": "review-fixture.mp4"}
        if recorded_at:
            params["recorded_at"] = recorded_at
        imported = client.post("/api/import", params=params, content=video.read_bytes()).json()
        source = wait_for_job(client, imported["id"])["result"]["video_id"]
        request = {"object_query": "green", "mode": "relevance", "video_id": source}
        job = client.post("/api/answer", json=request).json()
        first = wait_for_job(client, job["id"])["result"]
        assert first["status"] == "candidate"
        assert "Is this the item" in first["answer"]
        request["excluded_frame_ids"] = [first["evidence"]["id"]]
        job = client.post("/api/answer", json=request).json()
        second = wait_for_job(client, job["id"])["result"]
        assert second["evidence"]["id"] not in request["excluded_frame_ids"]
        assert all(row["id"] not in request["excluded_frame_ids"] for row in second["checked"])
        assert second["scope"]["video_id"] == source
        choice = {
            "frame_id": second["evidence"]["id"],
            "object_query": "green",
            "request_id": str(uuid4()),
        }
        confirmed = client.post("/api/matches/confirm", json=choice)
        assert confirmed.status_code == 200
        result = confirmed.json()
        assert result["status"] == "confirmed"
        assert result["confirmation"] == "user"
        assert result["evidence"]["observed_at"] == second["evidence"]["observed_at"]
        assert "current location" in result["answer"]
        if not recorded_at:
            assert "capture time unknown" in result["answer"]
        assert client.post("/api/matches/confirm", json=choice).json() == result
        assert (
            client.post(
                "/api/matches/confirm", json={**choice, "object_query": "other"}
            ).status_code
            == 409
        )
        assert len(client.get("/api/companion").json()["conversations"]) == 1
        missing = {**choice, "frame_id": 999999, "request_id": str(uuid4())}
        assert client.post("/api/matches/confirm", json=missing).status_code == 404
    with TestClient(app()) as client:
        assert client.post("/api/matches/confirm", json=choice).json() == result
        assert client.delete(f"/api/videos/{source}").status_code == 200
        assert client.post("/api/matches/confirm", json=choice).status_code == 404
        assert (
            client.get("/api/companion").json()["conversations"][-1]["sources_available"] is False
        )


def test_rejection_keeps_time_bounds_and_does_not_load_model_when_all_excluded(tmp_path, video):
    from nyx.answers import history_steps
    from nyx.memory import Store
    from nyx.retrieval import index_video

    store = Store(tmp_path / "index", ColorEncoder.fingerprint, 3)
    index_video(video, store, ColorEncoder(), recorded_at="2026-10-19T10:00:00+00:00")
    with store.connection() as db:
        ids = [row["id"] for row in db.execute("SELECT id FROM frames")]
    steps = history_steps(
        "green",
        store,
        ColorEncoder(),
        lambda: pytest.fail("Rejected frames must not be rechecked"),
        seen_after="2026-10-19T09:00:00+00:00",
        excluded_frame_ids=ids,
    )
    with pytest.raises(StopIteration) as done:
        next(steps)
    result = done.value.value
    assert result["status"] == "uncertain"
    assert result["checked"] == []
    assert result["scope"]["seen_after"] == "2026-10-19T09:00:00+00:00"
