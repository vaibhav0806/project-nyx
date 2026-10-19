import base64
from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import ClassVar

import pytest
from PIL import Image

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from test_app import wait_for_job
from test_nyx import ColorEncoder

from nyx.app import create_app


class Planner:
    fingerprint: ClassVar[dict] = {"model": "deterministic-fixture"}

    def decide(self, state):
        if state["observations"]:
            return {"action": "finish", "observation": 0}
        if "cancel" in state["message"].lower():
            return {"action": "cancel_reminder", "id": state["reminders"][0]["id"]}
        if "remind" in state["message"].lower():
            return {"action": "remind_on_departure", "message": "Take your water bottle"}
        return {"action": "inspect_current", "query": "green"}

    def inspect(self, image, query):
        return {
            "visibility": "visible",
            "location": "in the center",
            "description": "Green fixture",
            "ambiguous": False,
        }

    def inspect_departure(self, images):
        return {"departure": True, "uncertain": False, "cue": "Synthetic exit sequence"}


def snapshot(color="green"):
    out = BytesIO()
    Image.new("RGB", (160, 96), color).save(out, format="JPEG")
    return base64.b64encode(out.getvalue()).decode()


def test_typed_companion_uses_local_tools_persists_context_and_deletes_source_links(tmp_path):
    root = tmp_path / "data"
    with TestClient(
        create_app(root, encoder_factory=ColorEncoder, verifier_factory=Planner)
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "Where is the green thing?",
                "request_id": "request-1",
                "snapshot": snapshot(),
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )
        assert response.status_code == 202
        result = wait_for_job(client, response.json()["id"])["result"]
        assert result["status"] == "seen"
        assert result["visual"]["kind"] == "snapshot"
        assert result["steps"][0]["query"] == "green"
        assert client.get("/api/companion").json()["conversations"][-1]["status"] == "complete"
    with TestClient(
        create_app(root, encoder_factory=ColorEncoder, verifier_factory=Planner)
    ) as client:
        assert (
            client.get("/api/companion").json()["conversations"][-1]["transcript"]
            == "Where is the green thing?"
        )


def test_request_creates_one_next_departure_reminder_and_cancel_works(tmp_path):
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Planner)
    ) as client:
        response = client.post(
            "/api/agent",
            json={"message": "Remind me about water when I leave", "request_id": "turn-1"},
        )
        result = wait_for_job(client, response.json()["id"])
        assert result["status"] == "succeeded", result
        tasks = client.get("/api/companion").json()["reminders"]
        assert len(tasks) == 1 and tasks[0]["state"] == "armed"
        again = client.post(
            "/api/agent",
            json={"message": "Remind me about water when I leave", "request_id": "turn-1"},
        )
        wait_for_job(client, again.json()["id"])
        assert len(client.get("/api/companion").json()["reminders"]) == 1
        client.delete(f"/api/reminders/{tasks[0]['id']}")
        assert client.get("/api/companion").json()["reminders"][0]["state"] == "cancelled"


def test_live_observer_does_not_wait_for_recording_segment_and_requires_owner(tmp_path):
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Planner)
    ) as client:
        task = client.post(
            "/api/agent",
            json={"message": "Remind me about water when I leave", "request_id": "turn-1"},
        ).json()
        wait_for_job(client, task["id"])
        session = client.post(
            "/api/capture/start", json={"at": datetime.now(UTC).isoformat()}
        ).json()
        now = datetime.now(UTC)
        for index, color in enumerate(["gray", "gray", "white"]):
            response = client.post(
                "/api/observe",
                json={
                    "session_id": session["id"],
                    "captured_at": (now + timedelta(seconds=index - 2)).isoformat(),
                    "image": snapshot(color),
                },
            )
            assert response.status_code in {200, 202}, response.text
        assert response.status_code == 202
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        assert job["result"]["deliveries"]
        assert client.get("/api/videos").json() == []
        wrong = client.post(
            "/api/observe",
            json={
                "session_id": "wrong",
                "captured_at": datetime.now(UTC).isoformat(),
                "image": snapshot(),
            },
        )
        assert wrong.status_code == 409


def test_no_active_reminder_means_no_visual_model_load_for_live_observation(tmp_path):
    def no_model():
        pytest.fail("Idle observing must not load a model")

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=no_model)
    ) as client:
        session = client.post(
            "/api/capture/start", json={"at": datetime.now(UTC).isoformat()}
        ).json()
        response = client.post(
            "/api/observe",
            json={
                "session_id": session["id"],
                "captured_at": datetime.now(UTC).isoformat(),
                "image": snapshot(),
            },
        )
        assert response.json()["state"] == "quiet"
