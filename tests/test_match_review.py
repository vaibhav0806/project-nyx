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


def test_conversational_rejection_reaches_agent_and_skips_candidate_after_restart(tmp_path, video):
    class Reviewing(CandidateVerifier):
        def decide(self, state):
            if state["observations"]:
                return {"action": "finish", "observation": 0}
            if state["message"] == "nah man its not this item":
                previous = state["conversation"][-1]["plan"]["candidate"]
                assert previous["frame_id"] == first_id
                return {
                    "action": "search_matches",
                    "query": "green",
                    "excluded_frame_ids": [previous["frame_id"]],
                }
            return {"action": "search_matches", "query": "green"}

    def app():
        return create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Reviewing)

    with TestClient(app()) as client:
        imported = client.post(
            "/api/import", params={"name": "review.mp4"}, content=video.read_bytes()
        ).json()
        wait_for_job(client, imported["id"])
        job = client.post(
            "/api/agent", json={"message": "Find green in my imported video", "request_id": "first"}
        ).json()
        first = wait_for_job(client, job["id"])["result"]
        first_id = first["visual"]["evidence"]["id"]
    with TestClient(app()) as client:
        job = client.post(
            "/api/agent", json={"message": "nah man its not this item", "request_id": "reject"}
        ).json()
        second = wait_for_job(client, job["id"])["result"]
        assert second["status"] == "candidate"
        assert second["visual"]["evidence"]["id"] != first_id
        assert first_id not in [row["id"] for row in second["checked"]]
        assert second["steps"][0]["excluded_frame_ids"] == [first_id]
        assert (
            client.get("/api/companion").json()["conversations"][-1]["transcript"]
            == "nah man its not this item"
        )


def test_direct_candidate_can_be_rejected_via_normal_agent_request(tmp_path, video):
    from datetime import UTC, datetime

    from test_companion import snapshot

    class Reviewing(CandidateVerifier):
        def decide(self, state):
            if state["observations"]:
                return {"action": "finish", "observation": 0}
            candidate = state["available"]["presented_candidate"]
            assert candidate["object_query"] == "green"
            return {
                "action": "search_matches",
                "query": "green",
                "excluded_frame_ids": [candidate["frame_id"]],
            }

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Reviewing)
    ) as client:
        imported = client.post(
            "/api/import", params={"name": "review.mp4"}, content=video.read_bytes()
        ).json()
        wait_for_job(client, imported["id"])
        job = client.post("/api/answer", json={"object_query": "green", "mode": "relevance"}).json()
        candidate = wait_for_job(client, job["id"])["result"]
        frame_id = candidate["evidence"]["id"]
        job = client.post(
            "/api/agent",
            json={
                "message": "Please find another one, that's not it",
                "request_id": "reject",
                "presented_frame_id": frame_id,
                "presented_query": "green",
                "snapshot": snapshot(),
                "captured_at": datetime.now(UTC).isoformat(),
            },
        ).json()
        result = wait_for_job(client, job["id"])["result"]
        assert result["status"] == "candidate"
        assert result["visual"]["evidence"]["id"] != frame_id


@pytest.mark.parametrize(
    "mode,semantic_latest,rejected_count",
    [("relevance", False, 5), ("latest", False, 17), ("latest", True, 17)],
)
def test_rejection_can_reach_beyond_initial_candidate_limit(
    tmp_path, monkeypatch, mode, semantic_latest, rejected_count
):
    from PIL import Image

    from nyx.answers import history_steps
    from nyx.memory import Store

    store = Store(tmp_path / "index", ColorEncoder.fingerprint, 3)
    source = store.add_video("fixture.mp4", "fixture.mp4", "2026-10-19T10:00:00Z", 1)
    store.add_frames(source, [(i, f"{i}.jpg") for i in range(24)], [[0, 1, 0]] * 24)
    store.finish_video(source)
    monkeypatch.setattr("nyx.answers.frame_image", lambda *args: Image.new("RGB", (8, 8), "green"))
    rejected = []
    for _ in range(rejected_count + 1):
        steps = history_steps(
            "green",
            store,
            ColorEncoder(),
            CandidateVerifier,
            mode=mode,
            semantic_latest=semantic_latest,
            video_id=source,
            seen_after="2026-10-19T10:00:00Z",
            seen_before="2026-10-19T10:00:23Z",
            excluded_frame_ids=rejected,
        )
        while True:
            try:
                next(steps)
            except StopIteration as done:
                result = done.value
                break
        assert result["status"] == "candidate"
        frame_id = result["evidence"]["id"]
        assert frame_id not in rejected
        assert result["scope"]["checked_count"] == 1
        assert result["scope"]["candidates_retrieved"] <= result["scope"]["candidate_limit"]
        rejected.append(frame_id)


@pytest.mark.parametrize(
    "recorded_at,missing,hours",
    [
        ("2026-10-20T10:00:00Z", False, 0),
        (None, False, 0),
        ("2026-10-20T10:00:00Z", True, 0),
        ("old", False, 2),
    ],
)
def test_agent_can_search_strictly_before_evidence_without_rejecting_it(
    tmp_path, video, recorded_at, missing, hours
):
    from datetime import UTC, datetime, timedelta

    from nyx.agent import validate_action

    if recorded_at == "old":
        recorded_at = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    selected = {}

    class EarlierVerifier(CandidateVerifier):
        def decide(self, state):
            if state["observations"]:
                return {"action": "finish", "observation": 0}
            return validate_action(
                {
                    "action": "search_history",
                    "query": "green",
                    "hours": hours,
                    "before_frame_id": selected["id"],
                    "excluded_frame_ids": [],
                }
            )

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=EarlierVerifier)
    ) as client:
        params = {"name": "earlier.mp4"}
        if recorded_at:
            params["recorded_at"] = recorded_at
        response = client.post("/api/import", params=params, content=video.read_bytes()).json()
        wait_for_job(client, response["id"])
        from nyx.memory import Store

        store = Store(tmp_path, ColorEncoder.fingerprint, 3)
        rows = store.search([0, 1, 0], limit=100)
        selected.update(max(rows, key=lambda row: row["offset_seconds"]))
        if missing:
            selected["id"] = 999999
        response = client.post(
            "/api/agent",
            json={
                "message": "Show me an earlier moment with the same item.",
                "request_id": str(uuid4()),
            },
        ).json()
        job = wait_for_job(client, response["id"])
        assert job["status"] == "succeeded"
        result = job["result"]
        if recorded_at and not missing and hours == 0:
            visual = result["visual"]
            assert visual["status"] == "candidate"
            assert visual["evidence"]["observed_at"] < selected["observed_at"]
            assert all(row["observed_at"] < selected["observed_at"] for row in visual["checked"])
            assert visual["scope"]["excluded_frame_ids"] == []
            assert visual["scope"]["before_frame_id"] == selected["id"]
            assert selected["id"] in {row["id"] for row in store.search([0, 1, 0])}
        else:
            assert result["status"] == "uncertain"
            assert (
                "predates this search window" if hours else "no available recording timestamp"
            ) in result["answer"]
