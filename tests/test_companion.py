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


def test_followup_answer_keeps_original_evidence_dependency(tmp_path, video):
    from nyx.voice import Conversations

    payloads = []

    class Repeating(Planner):
        def agent_reply(self, messages, tools):
            payloads.append(json.dumps(messages))
            return {
                "role": "assistant",
                "content": "The earlier sighting was beside the amber jar.",
            }

    conversations = Conversations(tmp_path)
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Repeating)
    ) as client:
        imported = client.post(
            "/api/import", params={"name": "scene.mp4"}, content=video.read_bytes()
        )
        source = wait_for_job(client, imported.json()["id"])["result"]["video_id"]
        original = conversations.begin("Where were the keys?", {})
        conversations.finish(original, "A possible sighting beside the amber jar.", [source])
        job = client.post(
            "/api/agent", json={"message": "Repeat that location", "request_id": "repeat"}
        )
        assert wait_for_job(client, job.json()["id"])["status"] == "succeeded"
        assert "amber jar" in payloads[-1]
        assert client.delete("/api/videos/" + source).status_code == 200
        job = client.post(
            "/api/agent",
            json={
                "message": "Can you still establish that location?",
                "request_id": "after-delete",
            },
        )
        assert wait_for_job(client, job.json()["id"])["status"] == "succeeded"
        assert "amber jar" not in payloads[-1]


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
        assert result["visual"]["identity_verified"] is False
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
                {"action": "process_memory"},
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
            "process_memory",
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

    def memory_reply(self, payload, schema):
        from test_personal_memory import response

        return response()

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
        latest_user = max(i for i, row in enumerate(messages) if row["role"] == "user")
        for row in messages[:latest_user]:
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
        return {"action": "inspect_current", "query": "green"}

    def inspect(self, image, query):
        return {
            "visibility": "visible",
            "location": "in the center",
            "description": "Green fixture",
            "ambiguous": False,
        }


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
        assert result["visual"]["identity_verified"] is False
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


def test_ambiguous_current_view_asks_user_without_searching_history(tmp_path):
    class Ambiguous(Planner):
        def decide(self, state):
            if state["observations"]:
                return {"action": "finish", "observation": 0}
            return {"action": "inspect_current", "query": "mug"}

        def inspect(self, image, query):
            return {"visibility": "uncertain", "location": None, "ambiguous": True}

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
        assert [step["action"] for step in result["steps"]] == ["inspect_current"]


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
            return {"action": "chat", "message": "Hello."}

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
        assert wait_for_job(client, job["id"])["result"]["answer"] == "Hello."
        assert len(states) == 1
        job = client.post(
            "/api/agent",
            json={"message": "Hello", "request_id": "local-context", "timezone": "Asia/Kolkata"},
        ).json()
        wait_for_job(client, job["id"])
        assert states[0]["now"] == now.isoformat()
        assert states[0]["user_timezone"] == "Asia/Kolkata"


def test_identify_shown_object_returns_description_for_subsequent_search(tmp_path):
    class ReferenceVerifier(Planner):
        def generate_json(self, *args, **kwargs):
            if "unique_referent" in kwargs.get("schema", {}).get("properties", {}):
                return json.dumps(
                    {"targets": "Fixture target", "unique_referent": True, "ambiguous": False}
                )
            return '{"targets":"One green object","target_count":1,"object_description":"Green fixture","frame_index":0,"ambiguous":false}'

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
            images = [p["image"] for p in messages[-1]["content"] if p["type"] == "image"]
            assert len(images) == 2
            assert images[0].getpixel((40, 40))[1] > 80
            assert max(images[1].getpixel((40, 40))) < 10
            return '{"targets":"One green phone","target_count":1,"object_description":"green phone","frame_index":0,"ambiguous":false}'

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
        reference = job["result"]["observations"][0]
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


def test_typed_conversation_uses_the_shared_native_agent_policy(tmp_path):
    from nyx.agent_policy import AGENT_INSTRUCTIONS
    from nyx.agent_tools import tool_schemas

    class NativeVerifier(Planner):
        def agent_reply(self, messages, tools):
            assert messages[0]["content"] == AGENT_INSTRUCTIONS
            assert tools == tool_schemas()
            assert (
                next(row["content"] for row in reversed(messages) if row["role"] == "user")
                == "Hello"
            )
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


def test_user_information_is_remembered_before_the_agent_replies(tmp_path):
    from test_personal_memory import Encoder, operation, response

    class MemoryVerifier(Planner):
        def memory_reply(self, payload, schema):
            turn = payload["current_turn"]
            return response([operation(turn["turn_id"], turn["text"], "Prefers tea without sugar")])

        def agent_reply(self, messages, tools):
            with __import__("sqlite3").connect(tmp_path / "conversations.sqlite3") as db:
                assert (
                    db.execute("SELECT content FROM memories").fetchone()[0]
                    == "Prefers tea without sugar"
                )
            assert "Prefers tea without sugar" in json.dumps(messages)
            return {"role": "assistant", "content": "I'll remember your tea preference."}

    with TestClient(
        create_app(tmp_path, encoder_factory=Encoder, verifier_factory=MemoryVerifier)
    ) as client:
        job = client.post(
            "/api/agent",
            json={"message": "I prefer tea without sugar.", "request_id": "auto-memory"},
        ).json()
        result = wait_for_job(client, job["id"])
        assert result["status"] == "succeeded", result
        assert result["result"]["sources"] == ["transcript:" + result["result"]["turn_id"]]


def test_memory_provider_failure_preserves_raw_input_without_false_saved_reply(tmp_path):
    from nyx.cloud import CloudError

    class BrokenMemory(Planner):
        def memory_reply(self, *args):
            raise CloudError("Memory provider unavailable")

        def agent_reply(self, *args):
            pytest.fail("Agent cannot claim a save after failed memory processing")

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=BrokenMemory)
    ) as client:
        job = client.post(
            "/api/agent", json={"message": "I prefer tea without sugar", "request_id": "failure"}
        ).json()
        assert wait_for_job(client, job["id"])["status"] == "failed"
        turn = client.get("/api/companion").json()["conversations"][-1]
        assert turn["transcript"] == "I prefer tea without sugar" and not turn["answer"]


def test_source_deletion_during_response_generation_withholds_stale_answer(tmp_path):
    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    old = conversations.begin("Find my glasses", {})
    conversations.finish(old, "A possible match beside the orange vase", ["old-video"])

    class Deleting(Planner):
        def agent_reply(self, messages, tools):
            conversations.invalidate("old-video")
            return {"role": "assistant", "content": "They are beside the orange vase"}

    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=Deleting)
    ) as client:
        job = client.post(
            "/api/agent",
            json={"message": "Where are they?", "request_id": "deleted-during-inference"},
        ).json()
        assert wait_for_job(client, job["id"])["status"] == "failed"
        turn = client.get("/api/companion").json()["conversations"][-1]
        assert not turn["answer"]


def test_spoken_tool_handoff_retains_actual_memory_records_and_pending_dependencies(tmp_path):
    from test_personal_memory import Encoder, operation, response

    from nyx.personal_memory import PersonalMemory
    from nyx.voice import Voice

    speaker = Voice(tmp_path, None)
    old_text = "I prefer tea without sugar"
    old = speaker.conversations.begin(old_text, {})

    def memory_reply(payload, schema):
        if payload.get("mode") == "recall":
            return response(relevant_ids=[payload["memories"][0]["id"]])
        return response([operation(old, old_text, "Prefers tea without sugar")])

    memory = PersonalMemory(speaker.conversations, Encoder(), memory_reply)
    memory.process(old)
    speaker.conversations.finish(old, "Noted")
    model = Planner()
    model.memory_reply = memory_reply
    action = {"action": "recall_memory", "query": "tea preference"}
    with TestClient(
        create_app(
            tmp_path,
            encoder_factory=Encoder,
            verifier_factory=lambda: model,
            voice_factory=lambda _: speaker,
        )
    ) as client:
        token = client.post("/api/voice/session").json()["token"]
        current = speaker.conversations.begin("What is my tea preference?", {"mode": "livekit"})
        speaker.turn = {"id": current, "transcript": "What is my tea preference?"}
        job = client.post(
            "/api/agent",
            headers={"x-nyx-voice": token},
            json={
                "message": speaker.turn["transcript"],
                "voice_turn_id": current,
                "request_id": "voice-memory-detail",
                "initial_action": action,
            },
        ).json()
        assert wait_for_job(client, job["id"])["status"] == "succeeded"
        actual = speaker.conversations.tool_result(current, action)
        assert actual["matches"][0]["content"] == "Prefers tea without sugar"
        assert "transcript:" + old in speaker.conversations.recent()[-1]["sources"]
        with pytest.raises(ValueError, match="match"):
            speaker.conversations.tool_result(
                current, {"action": "recall_memory", "query": "coffee"}
            )
        speaker.conversations.invalidate("transcript:" + old)
        with pytest.raises(ValueError, match="no longer"):
            speaker.conversations.tool_result(current, action)


def test_interrupted_pending_turn_keeps_registered_evidence_dependencies(tmp_path):
    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    turn = conversations.begin("Find my bottle", {})
    conversations.update_plan(turn, {}, sources=["video-a"])
    conversations.finish(turn, status="interrupted")
    assert conversations.recent()[-1]["sources"] == ["video-a"]
    conversations.invalidate("video-a")
    assert not conversations.recent()[-1]["sources_available"]


def test_stale_single_snapshot_cannot_bypass_utterance_window_before_inference(tmp_path):
    def forbidden():
        pytest.fail("Stale visual input must fail before provider initialization")

    with TestClient(
        create_app(
            tmp_path,
            encoder_factory=ColorEncoder,
            verifier_factory=forbidden,
            voice_factory=lambda _: None,
        )
    ) as client:
        response = client.post(
            "/api/agent",
            json={
                "message": "I put this in the drawer",
                "request_id": "stale-reference",
                "snapshot": snapshot(),
                "captured_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
            },
        )
        assert response.status_code == 400


@pytest.mark.parametrize("ambiguous", [False, True])
def test_memory_and_native_tool_share_one_reference_check_per_owned_window(tmp_path, ambiguous):
    from test_personal_memory import response as memory_response

    class ReferenceVerifier(Planner):
        calls = 0

        def memory_reply(self, payload, schema):
            return memory_response(needs_visual=payload["visual"] is None)

        def generate_json(self, *args, **kwargs):
            self.calls += 1
            return json.dumps(
                {
                    "targets": "Multiple targets" if ambiguous else "A green object",
                    "target_count": 2 if ambiguous else 1,
                    "object_description": "" if ambiguous else "green object",
                    "frame_index": -1 if ambiguous else 0,
                    "ambiguous": ambiguous,
                }
            )

        def agent_reply(self, messages, tools):
            if any(row["role"] == "tool" for row in messages):
                return {"role": "assistant", "content": "Which item?" if ambiguous else "Noted."}
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "reference",
                        "type": "function",
                        "function": {"name": "identify_shown_object", "arguments": "{}"},
                    }
                ],
            }

    model = ReferenceVerifier()
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=lambda: model)
    ) as client:
        now = datetime.now(UTC).isoformat()
        for number in range(2):
            job = client.post(
                "/api/agent",
                json={
                    "message": "I put this in the drawer.",
                    "request_id": f"window-{number}",
                    "context_at": now,
                    "visual_frames": [{"snapshot": snapshot(), "captured_at": now}],
                },
            ).json()
            result = wait_for_job(client, job["id"])
            assert result["status"] == "succeeded", result
            assert model.calls == number + 1


def test_voice_reference_reuse_requires_same_turn_pixels_and_clocks(tmp_path):
    from nyx.voice import Voice

    class ReferenceVerifier(Planner):
        calls = 0

        def generate_json(self, *args, **kwargs):
            self.calls += 1
            return json.dumps(
                {
                    "targets": "A fixture object",
                    "target_count": 1,
                    "object_description": "fixture object",
                    "frame_index": 0,
                    "ambiguous": False,
                }
            )

    model, speaker = ReferenceVerifier(), Voice(tmp_path, None)
    with TestClient(
        create_app(
            tmp_path,
            encoder_factory=ColorEncoder,
            verifier_factory=lambda: model,
            voice_factory=lambda _: speaker,
        )
    ) as client:
        token = client.post("/api/voice/session").json()["token"]
        now = datetime.now(UTC)
        text = "What am I showing?"
        turn = speaker.conversations.begin(text, {"mode": "livekit"})
        speaker.turn = {"id": turn, "transcript": text}
        for number, (color, offset) in enumerate(
            [("green", 0), ("green", 0), ("blue", 0), ("blue", -1)]
        ):
            job = client.post(
                "/api/agent",
                headers={"x-nyx-voice": token},
                json={
                    "message": text,
                    "voice_turn_id": turn,
                    "request_id": f"identify-{number}",
                    "initial_action": {"action": "identify_shown_object"},
                    "context_at": now.isoformat(),
                    "visual_frames": [
                        {
                            "snapshot": snapshot(color),
                            "captured_at": (now + timedelta(seconds=offset)).isoformat(),
                        }
                    ],
                },
            ).json()
            result = wait_for_job(client, job["id"])
            assert result["status"] == "succeeded", result
            assert model.calls == [1, 1, 2, 3][number]
        with speaker.conversations.connect() as db:
            db.execute("UPDATE turns SET sources_available=0 WHERE id=?", (turn,))
        job = client.post(
            "/api/agent",
            headers={"x-nyx-voice": token},
            json={
                "message": text,
                "voice_turn_id": turn,
                "request_id": "deleted-reference",
                "initial_action": {"action": "identify_shown_object"},
                "context_at": now.isoformat(),
                "visual_frames": [
                    {
                        "snapshot": snapshot("blue"),
                        "captured_at": (now - timedelta(seconds=1)).isoformat(),
                    }
                ],
            },
        ).json()
        assert wait_for_job(client, job["id"])["status"] == "failed"
        assert model.calls == 3
