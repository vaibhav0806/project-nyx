import base64
import json
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

pytest_plugins = ["test_nyx"]


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

    def inspect_departure(self, images, **context):
        return {
            "departure": True,
            "uncertain": False,
            "approached_exit": True,
            "exit_interaction": True,
            "cue": "Synthetic exit sequence",
            "region": {
                "label": "Synthetic exit",
                "kind": "exterior_exit",
                "box": [0.8, 0.1, 0.95, 0.8],
                "uncertain": False,
            },
            "entities": [
                [{"box": [x - 0.04, 0.4, x + 0.04, 0.6], "score": 0.9}] for x in [0.2, 0.5, 0.82]
            ],
        }


def snapshot(color="green"):
    out = BytesIO()
    Image.new("RGB", (160, 96), color).save(out, format="JPEG")
    return base64.b64encode(out.getvalue()).decode()


def test_live_dense_selection_keeps_exact_semantic_times_in_delivery_evidence(tmp_path):
    class Dense(Planner):
        def inspect_departure(self, images, *, times, view_id):
            assert len(images) == len(times) == 4
            assert view_id
            return {
                **super().inspect_departure(images),
                "frame_indices": [1, 2, 3],
                "semantic_checked": True,
            }

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Dense)
    ) as client:
        request = client.post(
            "/api/agent",
            json={"message": "Remind me about water when I leave", "request_id": "dense-evidence"},
        ).json()
        wait_for_job(client, request["id"])
        now = datetime.now(UTC)
        session = client.post("/api/capture/start", json={"at": now.isoformat()}).json()
        for i in range(7):
            response = client.post(
                "/api/observe",
                json={
                    "session_id": session["id"],
                    "captured_at": (now + timedelta(seconds=i / 10)).isoformat(),
                    "image": snapshot("gray" if i == 0 else "white"),
                },
            )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        expected = [(now + timedelta(seconds=x)).isoformat() for x in [0.2, 0.4, 0.6]]
        assert job["result"]["frame_times"] == expected
        evidence = json.loads(client.get("/api/companion").json()["pending"][0]["evidence"])
        assert evidence["frame_times"] == expected
        assert evidence["semantic_frame_times"] == expected


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
        plan = client.get("/api/companion").json()["conversations"][-1]["plan"]
        assert plan["steps"][0]["query"] == "green"
        assert plan["model"]["model"] == "deterministic-fixture"


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
        for index, color in enumerate(["gray"] + ["white"] * 6):
            response = client.post(
                "/api/observe",
                json={
                    "session_id": session["id"],
                    "captured_at": (now + timedelta(seconds=index / 10)).isoformat(),
                    "image": snapshot(color),
                },
            )
            assert response.status_code in {200, 202}, response.text
            if index < 6:
                assert response.status_code == 200
        assert response.status_code == 202
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        assert job["result"]["deliveries"]
        assert job["result"]["decision"]["act"]
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


def test_brief_live_flash_keeps_requested_reminder_armed_without_inspection(tmp_path):
    class NoInspection(Planner):
        def inspect_departure(self, images, **context):
            pytest.fail("A short returned-to-baseline flash must not invoke vision")

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=NoInspection)
    ) as client:
        request = client.post(
            "/api/agent",
            json={"message": "Remind me about water when I leave", "request_id": "flash"},
        ).json()
        wait_for_job(client, request["id"])
        now = datetime.now(UTC)
        session = client.post("/api/capture/start", json={"at": now.isoformat()}).json()
        for tick in range(16):
            response = client.post(
                "/api/observe",
                json={
                    "session_id": session["id"],
                    "captured_at": (now + timedelta(seconds=tick / 10)).isoformat(),
                    "image": snapshot("white" if tick == 5 else "gray"),
                },
            )
            assert response.status_code == 200
        status = client.get("/api/companion").json()
        assert status["reminders"][0]["state"] == "armed"
        assert status["pending"] == []
        assert status["observation"]["phase"] == "quiet"


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


@pytest.mark.parametrize("relation", ["entering", "standing", "turnback", "unknown_exit"])
def test_semantic_departure_without_grounded_motion_preserves_armed_request(tmp_path, relation):
    class Contradictory(Planner):
        def inspect_departure(self, images, **context):
            result = super().inspect_departure(images, **context)
            points = {
                "entering": [0.82, 0.5, 0.2],
                "standing": [0.82] * 3,
                "turnback": [0.3, 0.82, 0.4],
            }
            if relation == "unknown_exit":
                result["region"]["kind"] = "unknown"
            else:
                result["entities"] = [
                    [{"box": [x - 0.04, 0.4, x + 0.04, 0.6], "score": 0.9}]
                    for x in points[relation]
                ]
            return result

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Contradictory)
    ) as client:
        request = client.post(
            "/api/agent",
            json={"message": "Remind me about water when I leave", "request_id": "geometry"},
        ).json()
        wait_for_job(client, request["id"])
        now = datetime.now(UTC)
        session = client.post("/api/capture/start", json={"at": now.isoformat()}).json()
        for index, color in enumerate(["gray"] + ["white"] * 6):
            response = client.post(
                "/api/observe",
                json={
                    "session_id": session["id"],
                    "captured_at": (now + timedelta(seconds=index / 10)).isoformat(),
                    "image": snapshot(color),
                },
            )
        assert response.status_code == 202
        result = wait_for_job(client, response.json()["id"])["result"]
        assert not result["deliveries"]
        assert result["decision"]["reason"] == (
            "unresolved_exit" if relation == "unknown_exit" else "unconfirmed_approach"
        )
        state = client.get("/api/companion").json()
        assert state["reminders"][0]["state"] == "armed"
        assert not state["pending"]


@pytest.mark.parametrize("interruption", ["cancel", "stop", "expired", "changed"])
def test_inflight_departure_cannot_act_after_cancellation_camera_stop_or_expiry(
    tmp_path, monkeypatch, interruption
):
    from threading import Event

    entered, release = Event(), Event()
    clock = [datetime.now(UTC)]

    class Clock:
        @staticmethod
        def now(zone):
            return clock[0]

    class Waiting(Planner):
        def inspect_departure(self, images, **context):
            entered.set()
            assert release.wait(5)
            return super().inspect_departure(images, **context)

    monkeypatch.setattr("nyx.companion.datetime", Clock)
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Waiting)
    ) as client:
        try:
            request = client.post(
                "/api/agent",
                json={"message": "Remind me about water when I leave", "request_id": "inflight"},
            ).json()
            wait_for_job(client, request["id"])
            clock[0] = datetime.now(UTC)
            now = clock[0]
            state = client.get("/api/companion").json()
            item = state["reminders"][0]
            session = client.post("/api/capture/start", json={"at": now.isoformat()}).json()
            for tick in range(7):
                response = client.post(
                    "/api/observe",
                    json={
                        "session_id": session["id"],
                        "captured_at": (now + timedelta(seconds=tick / 10)).isoformat(),
                        "image": snapshot("gray" if tick == 0 else "white"),
                    },
                )
            assert response.status_code == 202
            assert entered.wait(2)
            if interruption == "cancel":
                client.delete("/api/reminders/" + item["id"])
            elif interruption == "stop":
                client.post(
                    f"/api/capture/{session['id']}/state",
                    json={
                        "state": "stopped",
                        "at": (now + timedelta(seconds=0.7)).isoformat(),
                        "reason": "Test stop",
                    },
                )
            elif interruption == "changed":
                for tick in range(7, 15):
                    client.post(
                        "/api/observe",
                        json={
                            "session_id": session["id"],
                            "captured_at": (now + timedelta(seconds=tick / 10)).isoformat(),
                            "image": snapshot("black"),
                        },
                    )
            else:
                clock[0] += timedelta(seconds=20)
            release.set()
            outcome = wait_for_job(client, response.json()["id"])
            assert outcome["status"] == ("failed" if interruption == "expired" else "succeeded")
            if interruption == "changed":
                assert outcome["result"]["decision"]["reason"] == "superseded_evidence"
                assert outcome["result"]["delivery_continuity"]["reason"] == "scene_changed"
            status = client.get("/api/companion").json()
            assert status["observation"]["state"] != "checking"
            assert status["pending"] == []
            assert status["reminders"][0]["state"] == (
                "cancelled" if interruption == "cancel" else "armed"
            )
        finally:
            release.set()


def test_voice_agent_reply_requires_the_authoritative_matching_turn(tmp_path):
    from nyx.voice import Voice

    class Speech:
        def speak(self, text):
            return "fixture-audio"

    speaker = Voice(tmp_path, Speech())
    with TestClient(
        create_app(
            tmp_path,
            encoder_factory=ColorEncoder,
            verifier_factory=Planner,
            voice_factory=lambda root: speaker,
        )
    ) as client:
        token = client.post("/api/voice/session").json()["token"]
        identifier = speaker.conversations.begin("Where is green?", {"mode": "agent"})
        speaker.turn = {
            "id": identifier,
            "at": datetime.now(UTC).isoformat(),
            "transcript": "Where is green?",
            "plan": {"mode": "agent"},
        }
        headers = {"x-nyx-voice": token}
        job = client.post(
            "/api/agent",
            headers=headers,
            json={
                "message": "Where is green?",
                "voice_turn_id": identifier,
                "request_id": identifier,
                "snapshot": snapshot(),
                "captured_at": datetime.now(UTC).isoformat(),
            },
        ).json()
        wait_for_job(client, job["id"])
        reply = client.post(
            "/api/voice/reply", headers=headers, json={"turn_id": identifier, "job_id": job["id"]}
        )
        assert reply.status_code == 200, reply.text
        assert reply.json()["answer"].startswith("I can see green")
        assert reply.json()["audio"] == "fixture-audio"


def test_agent_falls_back_to_recent_verified_history_instead_of_an_old_match(tmp_path, video):
    import numpy as np

    class FindingPlanner(Planner):
        def decide(self, state):
            if not state["observations"]:
                return {"action": "inspect_current", "query": "green"}
            if len(state["observations"]) == 1:
                return {"action": "search_history", "query": "green", "hours": 2}
            return {"action": "finish", "observation": 1}

        def inspect(self, image, query):
            green = np.asarray(image).mean(axis=(0, 1))[1] > 100
            return {
                "visibility": "visible" if green else "not_visible",
                "location": "center" if green else None,
                "description": "Color fixture",
                "ambiguous": False,
            }

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=FindingPlanner)
    ) as client:
        ids = []
        for hours in [240, 1]:
            job = client.post(
                "/api/import",
                params={
                    "name": "scene.mp4",
                    "recorded_at": (datetime.now(UTC) - timedelta(hours=hours)).isoformat(),
                },
                content=video.read_bytes(),
            ).json()
            ids.append(wait_for_job(client, job["id"])["result"]["video_id"])
        job = client.post(
            "/api/agent",
            json={
                "message": "Where is green?",
                "request_id": "find-green",
                "snapshot": snapshot("red"),
                "captured_at": datetime.now(UTC).isoformat(),
            },
        ).json()
        result = wait_for_job(client, job["id"])["result"]
        assert result["status"] == "candidate"
        assert result["visual"]["evidence"]["video_id"] == ids[1]
        assert ids[0] not in result["sources"]
        client.delete(f"/api/videos/{ids[1]}")
        assert client.get("/api/jobs/" + job["id"]).json()["status"] == "failed"
        assert (
            client.get("/api/companion").json()["conversations"][-1]["sources_available"] is False
        )


def test_misrouted_model_cannot_cancel_a_reminder_without_user_request(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    reminder = tasks.create("water-request", "Take water")

    class BadPlanner(Planner):
        def decide(self, state):
            return {"action": "cancel_reminder", "id": reminder["id"]}

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=BadPlanner)
    ) as client:
        job = client.post(
            "/api/agent",
            json={"message": "Where is my water bottle?", "request_id": "lookup-request"},
        ).json()
        assert wait_for_job(client, job["id"])["status"] == "succeeded"
        assert tasks.get(reminder["id"])["state"] == "armed"


def test_timed_departure_cannot_be_silently_saved_as_an_unconditional_reminder(tmp_path):
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Planner)
    ) as client:
        job = client.post(
            "/api/agent",
            json={
                "message": "Remind me to take water when I leave at six",
                "request_id": "timed-exit",
            },
        ).json()
        result = wait_for_job(client, job["id"])["result"]
        assert result["status"] == "clarify"
        assert client.get("/api/companion").json()["reminders"] == []


def test_agent_cannot_present_a_snapshot_that_ages_out_during_final_planning(tmp_path, monkeypatch):
    clock = [datetime.now(UTC)]

    class Clock:
        @staticmethod
        def now(zone):
            return clock[0]

    class SlowFinish(Planner):
        def decide(self, state):
            result = super().decide(state)
            if state["observations"]:
                clock[0] += timedelta(seconds=20)
            return result

    monkeypatch.setattr("nyx.companion.datetime", Clock)
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=SlowFinish)
    ) as client:
        job = client.post(
            "/api/agent",
            json={
                "message": "Where is green?",
                "request_id": "aging-snapshot",
                "snapshot": snapshot(),
                "captured_at": clock[0].isoformat(),
            },
        ).json()
        result = wait_for_job(client, job["id"])
        assert result["status"] == "failed"
        assert "stale" in result["error"]


def test_replayed_request_after_restart_does_not_claim_a_cancelled_reminder_is_armed(tmp_path):
    body = {"message": "Remind me about water when I leave", "request_id": "stable-request"}
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Planner)
    ) as client:
        job = client.post("/api/agent", json=body).json()
        wait_for_job(client, job["id"])
        item = client.get("/api/companion").json()["reminders"][0]
        client.delete("/api/reminders/" + item["id"])
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Planner)
    ) as client:
        job = client.post("/api/agent", json=body).json()
        result = wait_for_job(client, job["id"])["result"]
        assert result["status"] == "cancelled"
        assert len(client.get("/api/companion").json()["reminders"]) == 1


@pytest.mark.parametrize(
    "message",
    [
        "Do not remind me about water when I leave",
        "Cancel the reminder about water when I leave",
        "Remind me about water when I leave tomorrow",
    ],
)
def test_model_cannot_drop_negation_or_a_future_day_from_departure_request(tmp_path, message):
    class Misroute(Planner):
        def decide(self, state):
            return (
                {"action": "finish", "observation": 0}
                if state["observations"]
                else {"action": "remind_on_departure", "message": "Take water"}
            )

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Misroute)
    ) as client:
        job = client.post(
            "/api/agent", json={"message": message, "request_id": "constrained-request"}
        ).json()
        wait_for_job(client, job["id"])
        assert client.get("/api/companion").json()["reminders"] == []


def test_imported_unknown_time_media_can_be_checked_without_claiming_latest(tmp_path, video):
    import numpy as np

    class ImportedPlanner(Planner):
        def decide(self, state):
            return (
                {"action": "finish", "observation": 0}
                if state["observations"]
                else {"action": "search_matches", "query": "green"}
            )

        def inspect(self, image, query):
            visible = np.asarray(image).mean(axis=(0, 1))[1] > 100
            return {
                "visibility": "visible" if visible else "not_visible",
                "location": "center" if visible else None,
                "description": "Color fixture",
                "ambiguous": False,
            }

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=ImportedPlanner)
    ) as client:
        imported = client.post(
            "/api/import", params={"name": "unknown.mp4"}, content=video.read_bytes()
        ).json()
        wait_for_job(client, imported["id"])
        job = client.post(
            "/api/agent",
            json={"message": "Find green in my imported clip", "request_id": "undated-query"},
        ).json()
        output = wait_for_job(client, job["id"])["result"]
        assert output["status"] == "candidate"
        assert output["visual"]["evidence"]["observed_at"] is None
        assert "don't know when" in output["answer"]
        assert "latest" not in output["answer"].lower()


def test_wrong_cancellation_is_repaired_before_tools_and_preserves_existing_request(tmp_path):
    class Repair(Planner):
        def decide(self, state):
            if state["observations"]:
                return {"action": "finish", "observation": 0}
            if state["reminders"] and not state.get("decision_error"):
                return {"action": "cancel_reminder", "id": state["reminders"][0]["id"]}
            if state["reminders"]:
                assert "cancel" in state["decision_error"]
                assert state["actions"] == []
            return {"action": "remind_on_departure", "message": "Take your water bottle"}

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Repair)
    ) as client:
        for request_id in ["first", "second"]:
            job = client.post(
                "/api/agent",
                json={
                    "message": "Remind me to take my water bottle when I leave",
                    "request_id": request_id,
                },
            ).json()
            result = wait_for_job(client, job["id"])["result"]
            assert result["status"] == "armed"
        assert len(result["decision_errors"]) == 1
        rows = client.get("/api/companion").json()["reminders"]
        assert len(rows) == 2 and all(r["state"] == "armed" for r in rows)


@pytest.mark.parametrize(
    "message",
    [
        "Do not cancel my reminder",
        "Don't forget my reminder",
        "Remind me to cancel my appointment when I leave",
        "Where is the sign saying cancel reminder?",
    ],
)
def test_negated_or_embedded_cancellation_cannot_change_reminders(tmp_path, message):
    class Cancel(Planner):
        def decide(self, state):
            return {"action": "cancel_reminder", "id": state["reminders"][0]["id"]}

    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("existing", "Take water")
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Cancel)
    ) as client:
        job = client.post("/api/agent", json={"message": message, "request_id": "negated"}).json()
        result = wait_for_job(client, job["id"])["result"]
        assert result["status"] == "uncertain"
        assert result["steps"] == []
        assert tasks.get(item["id"])["state"] == "armed"


@pytest.mark.parametrize(
    "message,extra,expected",
    [
        ("Cancel that reminder", False, "cancelled"),
        ("Cancel that reminder", True, "clarify"),
        ("Cancel my appointment", False, "clarify"),
        ("Cancel Take water reminder", "duplicate", "clarify"),
        ("Cancel Take water reminder", True, "cancelled"),
    ],
)
def test_cancellation_requires_unambiguous_reminder_target(tmp_path, message, extra, expected):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    first = tasks.create("one", "Take water")
    if extra:
        tasks.create("two", "Take water" if extra == "duplicate" else "Take keys")

    class Select(Planner):
        def decide(self, state):
            if state.get("decision_error"):
                return {"action": "clarify", "message": "Which departure reminder should I cancel?"}
            if state["observations"]:
                return {"action": "finish", "observation": 0}
            return {"action": "cancel_reminder", "id": first["id"]}

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Select)
    ) as client:
        job = client.post(
            "/api/agent", json={"message": message, "request_id": "cancel-specific"}
        ).json()
        result = wait_for_job(client, job["id"])["result"]
        assert result["status"] == expected
        assert tasks.get(first["id"])["state"] == (
            "cancelled" if expected == "cancelled" else "armed"
        )


def test_ambiguous_current_view_asks_user_without_searching_history(tmp_path):
    from nyx.verification import CloudVerifier

    class Ambiguous(Planner):
        def decide(self, state):
            if state["observations"]:
                return CloudVerifier.decide(self, state)
            return {"action": "inspect_current", "query": "mug"}

        def inspect(self, image, query):
            return {"visibility": "uncertain", "location": None, "ambiguous": True}

        def generate_decision(self, *args):
            pytest.fail("A clarification result needs no additional model call")

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Ambiguous)
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "Find my mug",
                "request_id": "ambiguous-current",
                "snapshot": snapshot("green"),
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )
        result = wait_for_job(client, response.json()["id"])["result"]
        assert result["status"] == "clarify"
        assert "Which one" in result["answer"]
        assert [step["action"] for step in result["steps"]] == ["inspect_current", "finish"]


def test_clock_and_agent_context_use_browser_timezone(tmp_path, monkeypatch):
    now = datetime.fromisoformat("2026-10-31T19:39:00+05:30")

    def local_clock(zone):
        assert zone == "Asia/Kolkata"
        return now

    monkeypatch.setattr("nyx.companion.local_now", local_clock)
    states = []

    class LocalPlanner(Planner):
        def decide(self, state):
            states.append(state)
            return {"action": "chat", "reply": "Hello."}

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=LocalPlanner)
    ) as client:
        job = client.post(
            "/api/agent",
            json={
                "message": "What's the time right now, ma'am?",
                "request_id": "clock",
                "timezone": "Asia/Kolkata",
            },
        ).json()
        assert wait_for_job(client, job["id"])["result"]["answer"] == "It's 7:39 pm."
        assert states == []
        job = client.post(
            "/api/agent",
            json={"message": "Hello", "request_id": "local-context", "timezone": "Asia/Kolkata"},
        ).json()
        wait_for_job(client, job["id"])
        assert states[0]["now"] == now.isoformat()
        assert states[0]["user_timezone"] == "Asia/Kolkata"
