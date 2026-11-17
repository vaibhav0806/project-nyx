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


def test_correction_and_historical_report_arguments_reach_real_persistence(tmp_path):
    from test_statement_corrections import Encoder, begin, verifier

    from nyx.statements import Statements
    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    model = verifier("bag")
    model.decide = lambda state: {"action": "finish", "observation": 0}
    original = model.generate_json

    def generate(messages, *args, **kwargs):
        if kwargs.get("schema") is None:
            return json.dumps({"statement_ids": [old]})
        return original(messages, *args, **kwargs)

    model.generate_json = generate
    with TestClient(
        create_app(tmp_path, encoder_factory=Encoder, verifier_factory=lambda: model)
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "Correction: my phone is in the bag",
                "request_id": "correction-api",
                "initial_action": {"action": "remember_statement", "supersedes_turn_id": old},
            },
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        new = job["result"]["turn_id"]
        assert [r["turn_id"] for r in statements.search("phone", Encoder())] == [new]
        response = client.post(
            "/api/agent",
            json={
                "message": "What did I report that day?",
                "request_id": "as-of-api",
                "initial_action": {
                    "action": "search_statements",
                    "query": "phone",
                    "as_of": "2026-11-06T18:00:00Z",
                },
            },
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        assert job["result"]["observations"][0]["matches"][0]["turn_id"] == old
        assert job["result"]["review_context"]["statement_refs"][0]["turn_id"] == old
        assert f"transcript:{old}" in job["result"]["sources"]


def test_ten_day_search_includes_day_nine_and_preserves_older_recordings(tmp_path, video):
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Planner)
    ) as client:
        ids = []
        for days in [11, 9, -1]:
            response = client.post(
                "/api/import",
                params={
                    "name": "scene.mp4",
                    "recorded_at": (datetime.now(UTC) - timedelta(days=days)).isoformat(),
                },
                content=video.read_bytes(),
            )
            job = wait_for_job(client, response.json()["id"])
            assert job["status"] == "succeeded", job
            ids.append(job["result"]["video_id"])
        response = client.post(
            "/api/agent",
            json={
                "message": "Where did you last see green in the last ten days?",
                "request_id": "ten-day-fixture",
                "initial_action": {"action": "search_history", "query": "green", "hours": 240},
            },
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        result = job["result"]
        assert result["status"] == "candidate", result
        assert result["visual"]["scope"]["hours"] == 240
        assert result["sources"] == [ids[1]]
        assert all(row["video_id"] == ids[1] for row in result["checked"])
        assert len(client.get("/api/videos").json()) == 3
        assert client.get(f"/api/videos/{ids[0]}/media").status_code == 200


def test_spoken_turn_keeps_candidate_and_tool_trace_after_nonvisual_tool(tmp_path, video):
    from nyx.voice import Voice

    speaker = Voice(tmp_path, None)
    token = speaker.start()["token"]
    message = "Where did you last see green?"
    turn_id = speaker.conversations.begin(message, {"mode": "livekit", "language": "en"})
    speaker.turn = {"id": turn_id, "transcript": message}
    with TestClient(
        create_app(
            tmp_path,
            encoder_factory=ColorEncoder,
            verifier_factory=Planner,
            voice_factory=lambda root: speaker,
        )
    ) as client:
        response = client.post(
            "/api/import",
            params={
                "name": "scene.mp4",
                "recorded_at": (datetime.now(UTC) - timedelta(days=9)).isoformat(),
            },
            content=video.read_bytes(),
        )
        assert wait_for_job(client, response.json()["id"])["status"] == "succeeded"
        results = []
        for number, action in enumerate(
            [
                {"action": "search_history", "query": "green", "hours": 240},
                {"action": "list_reminders"},
            ]
        ):
            response = client.post(
                "/api/agent",
                headers={"x-nyx-voice": token},
                json={
                    "message": message,
                    "request_id": f"voice-tool-{number}",
                    "voice_turn_id": turn_id,
                    "initial_action": action,
                },
            )
            job = wait_for_job(client, response.json()["id"])
            assert job["status"] == "succeeded", job
            results.append(job["result"])
        saved = client.get("/api/companion").json()["conversations"][-1]
        assert saved["plan"]["candidate"]["object_query"] == "green"
        assert saved["plan"]["candidate"]["frame_id"] == results[0]["visual"]["evidence"]["id"]
        assert [step["action"] for step in saved["plan"]["steps"]] == [
            "search_history",
            "finish",
            "list_reminders",
            "finish",
        ]
        assert results[0]["review_context"]["object_query"] == "green"
        assert results[1]["review_context"] == results[0]["review_context"]


def test_livekit_selected_tool_skips_redundant_planner_calls(tmp_path):
    class ToolOnly(Planner):
        def decide(self, state):
            raise AssertionError("LiveKit has already selected this tool")

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=ToolOnly)
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "Where is green?",
                "request_id": "livekit-tool",
                "initial_action": {"action": "inspect_current", "query": "green"},
                "snapshot": snapshot(),
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded"
        assert job["result"]["answer"].startswith("I can see green")


class Planner:
    fingerprint: ClassVar[dict] = {"model": "deterministic-fixture"}

    def agent_reply(self, messages, tools):
        """Scripted provider fixture; API execution uses native calls, not a test planner."""
        from nyx.agent_tools import bind_tool_action

        metadata = next(
            json.loads(row["content"])
            for row in reversed(messages)
            if row["role"] == "system" and row["content"].startswith("{")
        )
        observations = [json.loads(row["content"]) for row in messages if row["role"] == "tool"]
        for index, row in enumerate(observations):
            row["index"] = index
            row["statement_refs"] = row.get("matches", [])
        actions = [
            bind_tool_action(call["function"]["name"], call["function"]["arguments"])
            for row in messages
            for call in row.get("tool_calls", [])
        ]
        conversation = []
        for row in messages[:-1]:
            if row["role"] == "user":
                conversation.append({"transcript": row["content"], "answer": ""})
            elif row["role"] == "assistant" and row.get("content"):
                if row["content"].startswith("Saved context metadata: ") and conversation:
                    prior = json.loads(row["content"].split(": ", 1)[1])
                    conversation[-1].update(prior)
                    conversation[-1]["plan"] = {
                        "steps": prior.get("previous_tools", []),
                        "candidate": prior.get("candidate"),
                        "statement_refs": prior.get("statement_refs", []),
                    }
                    conversation[-1]["previous_tool_query"] = next(
                        (
                            a["query"]
                            for a in reversed(prior.get("previous_tools", []))
                            if "query" in a
                        ),
                        None,
                    )
                elif conversation:
                    conversation[-1]["answer"] = row["content"]
        state = {
            **metadata,
            "message": next(row["content"] for row in reversed(messages) if row["role"] == "user"),
            "observations": observations,
            "actions": actions,
            "conversation": conversation,
            "reminders": [],
        }
        action = self.decide(state)
        name = action["action"]
        if name in {"chat", "clarify"}:
            return {"role": "assistant", "content": action["message"]}
        if name == "finish":
            chosen = observations[action["observation"]]
            answer = chosen["answer"]
            if "statement_observation" in action:
                answer += " " + observations[action["statement_observation"]]["answer"]
            return {"role": "assistant", "content": answer}
        arguments = {k: v for k, v in action.items() if k != "action"}
        if name in {"inspect_current", "search_history", "search_matches"}:
            arguments["history"] = name == "search_history"
            arguments["undated"] = name == "search_matches"
            name = "look_for_object"
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"fixture-{len(actions)}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ],
        }

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
        assert job["status"] == "succeeded", json.dumps(job)
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
        assert job["status"] == "succeeded", json.dumps(job)
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
        result = wait_for_job(client, job["id"])
        assert result["result"]["answer"].startswith("I can see green")
        speaker.turn = None
        rejected = client.post(
            "/api/agent",
            headers=headers,
            json={
                "message": "Where is green?",
                "voice_turn_id": identifier,
                "request_id": "expired",
            },
        )
        assert rejected.status_code == 409


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


def test_statement_tools_persist_across_app_restart(tmp_path):
    class StatementEncoder(ColorEncoder):
        def encode_text(self, text):
            return super().encode_text("green")

    class StatementVerifier(Planner):
        def generate_json(self, messages, limit, **kwargs):
            if "unique_referent" in kwargs.get("schema", {}).get("properties", {}):
                return json.dumps(
                    {"targets": "Fixture target", "unique_referent": True, "ambiguous": False}
                )
            from nyx.voice import Conversations

            text = str(messages)
            if set(kwargs.get("schema", {}).get("properties", {})) == {"kind", "destination"}:
                return json.dumps({"kind": "intention", "destination": "kitchen"})
            if "Resolve the object" in text:
                return '{"kind":"intention","object_description":"green phone","source":"visual","frame_index":0,"destination":"kitchen","ambiguous":false}'
            with Conversations(tmp_path).connect() as db:
                row = db.execute("SELECT turn_id FROM statements LIMIT 1").fetchone()
            return json.dumps({"statement_ids": [row["turn_id"]]})

    with TestClient(
        create_app(tmp_path, encoder_factory=StatementEncoder, verifier_factory=StatementVerifier)
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "I'll put this in the kitchen",
                "request_id": "remember",
                "initial_action": {"action": "remember_statement"},
                "snapshot": snapshot(),
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", json.dumps(job)
        assert "linked" in job["result"]["answer"]
    with TestClient(
        create_app(tmp_path, encoder_factory=StatementEncoder, verifier_factory=StatementVerifier)
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "Where is my phone?",
                "request_id": "recall",
                "initial_action": {"action": "search_statements", "query": "green phone"},
            },
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", json.dumps(job)
        assert "kitchen" in job["result"]["answer"]
        assert "not visual confirmation" in job["result"]["answer"]


def test_optional_statement_source_lost_during_verification_preserves_visual_result(
    tmp_path, video
):
    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    claim = conversations.begin("The green thing is in the kitchen", {})
    conversations.finish(claim, sources=["other-spoken-clip"])

    class ContextVerifier(Planner):
        def generate_json(self, messages, *args, **kwargs):
            conversations.invalidate("other-spoken-clip")
            return json.dumps({"statement_ids": [claim]})

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=ContextVerifier)
    ) as client:
        imported = client.post("/api/import?name=fixture.mp4", content=video.read_bytes()).json()
        video_id = wait_for_job(client, imported["id"])["result"]["video_id"]
        response = client.post(
            "/api/agent",
            json={
                "message": "Find the green thing",
                "request_id": "context-loss",
                "initial_action": {"action": "search_matches", "query": "green"},
            },
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        result = job["result"]
        assert result["visual"]["evidence"]["video_id"] == video_id
        assert not result["visual"].get("spoken_context")
        assert result["sources"] == [video_id]
        assert not conversations.recent()[0]["sources_available"]


def test_deleted_media_invalidates_cached_statement_only_answer_and_request_replay(tmp_path, video):
    from test_statement_corrections import verifier

    from nyx.statements import Statements
    from nyx.voice import Conversations

    class ReportEncoder(ColorEncoder):
        def encode_text(self, text):
            return super().encode_text("green")

    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    model = verifier()
    with TestClient(
        create_app(tmp_path, encoder_factory=ReportEncoder, verifier_factory=lambda: model)
    ) as client:
        imported = client.post("/api/import?name=fixture.mp4", content=video.read_bytes()).json()
        video_id = wait_for_job(client, imported["id"])["result"]["video_id"]
        claim = conversations.begin("My phone is in the kitchen", {})
        statements.remember(claim, model, ReportEncoder())
        conversations.finish(claim, sources=[video_id])
        model.generate_json = lambda *args, **kwargs: json.dumps({"statement_ids": [claim]})
        request = {
            "message": "What did I say about my phone?",
            "request_id": "statement-only",
            "initial_action": {"action": "search_statements", "query": "phone"},
        }
        response = client.post("/api/agent", json=request)
        job_id = response.json()["id"]
        result = wait_for_job(client, job_id)["result"]
        assert not result["checked"] and video_id in result["sources"]
        assert client.delete(f"/api/videos/{video_id}").status_code == 200
        cached = client.get("/api/jobs/" + job_id).json()
        assert cached["status"] == "failed" and "result" not in cached
        replay = client.post("/api/agent", json=request).json()
        assert replay["id"] == job_id
        assert client.get("/api/jobs/" + job_id).json()["status"] == "failed"
        assert not conversations.recent()[-1]["sources_available"]


def test_identify_shown_object_returns_description_for_subsequent_search(tmp_path):
    class ReferenceVerifier(Planner):
        def generate_json(self, *args, **kwargs):
            if "unique_referent" in kwargs.get("schema", {}).get("properties", {}):
                return json.dumps(
                    {"targets": "Fixture target", "unique_referent": True, "ambiguous": False}
                )
            return '{"object_description":"Green fixture","destination":"","kind":"none","source":"visual","frame_index":0,"ambiguous":false}'

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=ReferenceVerifier)
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "Where did I put this?",
                "request_id": "identify",
                "initial_action": {"action": "identify_shown_object"},
                "snapshot": snapshot(),
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded"
        assert job["result"]["answer"].startswith("Shown object: Green fixture")


def test_utterance_window_uses_earlier_image_when_latest_snapshot_is_blank(tmp_path):
    class WindowVerifier(Planner):
        def generate_json(self, messages, *args, **kwargs):
            if "unique_referent" in kwargs.get("schema", {}).get("properties", {}):
                return json.dumps(
                    {"targets": "Fixture target", "unique_referent": True, "ambiguous": False}
                )
            images = [p["image"] for p in messages[0]["content"] if p["type"] == "image"]
            assert len(images) == 2
            assert images[0].getpixel((40, 40))[1] > 80
            assert max(images[1].getpixel((40, 40))) < 10
            return '{"object_description":"green phone","destination":"","kind":"none","source":"visual","frame_index":0,"ambiguous":false}'

    now = datetime.now(UTC)
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=WindowVerifier)
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "Where did I keep this?",
                "request_id": "window-earlier",
                "initial_action": {"action": "identify_shown_object"},
                "snapshot": snapshot("black"),
                "captured_at": now.isoformat(),
                "context_at": now.isoformat(),
                "visual_frames": [
                    {
                        "snapshot": snapshot(),
                        "captured_at": (now - timedelta(seconds=8)).isoformat(),
                    },
                    {"snapshot": snapshot("black"), "captured_at": now.isoformat()},
                ],
            },
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        assert "green phone" in job["result"]["answer"]
        reference = job["result"]["observations"][0]["reference"]
        assert reference["frame_index"] == 0


def test_utterance_window_rejects_unrelated_old_frames(tmp_path):
    now = datetime.now(UTC)
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Planner)
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "Where is this?",
                "request_id": "old-window",
                "context_at": now.isoformat(),
                "visual_frames": [
                    {
                        "snapshot": snapshot(),
                        "captured_at": (now - timedelta(seconds=50)).isoformat(),
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert "outside the utterance window" in response.text


@pytest.mark.parametrize("with_window", [False, True])
def test_planner_knows_utterance_images_exist_without_claiming_a_current_view(
    tmp_path, with_window
):
    observed = []

    class WindowPlanner(Planner):
        def decide(self, state):
            observed.append(state["available"])
            return {"action": "chat", "message": "Boundary check."}

    now = datetime.now(UTC)
    body = {"message": "I put this in the drawer.", "request_id": "window-availability"}
    if with_window:
        body.update(
            context_at=now.isoformat(),
            visual_frames=[{"snapshot": snapshot(), "captured_at": now.isoformat()}],
        )
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=WindowPlanner)
    ) as client:
        response = client.post("/api/agent", json=body)
        assert wait_for_job(client, response.json()["id"])["status"] == "succeeded"
    assert observed[0]["current_view"] is False
    assert observed[0]["turn_visual_context"] is with_window
    assert observed[0]["turn_visual_frame_count"] == int(with_window)


@pytest.mark.parametrize("change", [None, "pixels", "timestamp", "context", "turn", "refusal"])
def test_visual_identity_handoff_reuses_only_the_same_owned_window(tmp_path, change, monkeypatch):
    monkeypatch.setenv("NYX_HOUSEHOLD_REFERENCE_POLICY", "separated")
    from nyx.voice import Voice

    identities, checks = [], []

    class HandoffVerifier(Planner):
        def generate_json(self, messages, *args, **kwargs):
            fields = set(kwargs.get("schema", {}).get("properties", {}))
            if fields == {"kind", "destination"}:
                return '{"kind":"reported_placement","destination":"drawer"}'
            if "unique_referent" in fields:
                checks.append(True)
                return '{"targets":"one phone","unique_referent":true,"ambiguous":false}'
            identities.append(True)
            if change == "refusal" and len(identities) == 2:
                return '{"source":"unresolved","ambiguous":true}'
            return (
                '{"object_description":"phone","source":"visual","frame_index":0,"ambiguous":false}'
            )

    class HandoffEncoder(ColorEncoder):
        def encode_text(self, text):
            import numpy as np

            return np.array([1, 0, 0], dtype=np.float32)

    speaker = Voice(tmp_path, object())
    with TestClient(
        create_app(
            tmp_path,
            encoder_factory=HandoffEncoder,
            verifier_factory=HandoffVerifier,
            voice_factory=lambda root: speaker,
        )
    ) as client:
        headers = {"x-nyx-voice": client.post("/api/voice/session").json()["token"]}
        message = "I put this in the drawer."
        identifier = speaker.conversations.begin(message, {"mode": "livekit"})
        speaker.turn = {"id": identifier, "transcript": message}
        now = datetime.now(UTC)
        body = {
            "message": message,
            "voice_turn_id": identifier,
            "request_id": "first-identify",
            "context_at": now.isoformat(),
            "visual_frames": [{"snapshot": snapshot(), "captured_at": now.isoformat()}],
            "initial_action": {"action": "identify_shown_object"},
        }
        first = client.post("/api/agent", headers=headers, json=body)
        assert wait_for_job(client, first.json()["id"])["result"]["status"] == "complete"
        if change == "pixels":
            body["visual_frames"][0]["snapshot"] = snapshot("red")
        elif change == "timestamp":
            body["visual_frames"][0]["captured_at"] = (now - timedelta(seconds=1)).isoformat()
        elif change == "context":
            body["context_at"] = (now + timedelta(seconds=1)).isoformat()
        elif change == "turn":
            identifier = speaker.conversations.begin(message, {"mode": "livekit"})
            speaker.turn = {"id": identifier, "transcript": message}
            body["voice_turn_id"] = identifier
        if change == "refusal":
            body["request_id"] = "second-identify"
            rejected = client.post("/api/agent", headers=headers, json=body)
            assert wait_for_job(client, rejected.json()["id"])["result"]["status"] == "clarify"
        body.update(request_id="then-remember", initial_action={"action": "remember_statement"})
        saved = client.post("/api/agent", headers=headers, json=body)
        job = wait_for_job(client, saved.json()["id"])
        assert job["status"] == "succeeded", job
        assert job["result"]["status"] == "complete", job
        assert len(identities) == (1 if change is None else 3 if change == "refusal" else 2)
        assert len(checks) == (1 if change is None else 2)
        with speaker.conversations.connect() as db:
            row = db.execute(
                "SELECT resolver FROM statements WHERE turn_id=?", (identifier,)
            ).fetchone()
        reference = json.loads(row[0])["reference"]
        assert reference["kind"] == "reported_placement" and reference["destination"] == "drawer"
        assert reference["visual_identity_check"]["unique_referent"] is True


def test_typed_conversation_uses_the_shared_native_agent_policy(tmp_path):
    from nyx.agent_policy import AGENT_INSTRUCTIONS
    from nyx.agent_tools import tool_schemas

    class NativeVerifier(Planner):
        def agent_reply(self, messages, tools):
            assert messages[0]["content"] == AGENT_INSTRUCTIONS
            assert tools == tool_schemas()
            assert messages[-1]["content"] == "Hello"
            return {"role": "assistant", "content": "Hello from the shared agent."}

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=NativeVerifier)
    ) as client:
        response = client.post(
            "/api/agent", json={"message": "Hello", "request_id": "native-typed"}
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        assert job["result"]["answer"] == "Hello from the shared agent."
