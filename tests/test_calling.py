import pytest

from nyx.calling import BolnaError, Calls


class Provider:
    ready = True

    def __init__(self):
        self.started = []
        self.response = {"status": "in-progress"}
        self.error = None

    def start(self, row):
        self.started.append(row)
        if self.error:
            raise self.error
        return "execution-1"

    def result(self, execution):
        assert execution == "execution-1"
        return self.response


def setup_calls(tmp_path):
    provider = Provider()
    calls = Calls(tmp_path, provider)
    calls.save_contact(1, "Asha", "daughter", "+919000000001")
    return calls, provider


def test_persistent_dispatch_is_idempotent_and_snapshots_contact(tmp_path):
    calls, provider = setup_calls(tmp_path)
    first = calls.enqueue("turn-1", 1, "Please bring flowers")
    assert calls.enqueue("turn-1", 1, "Please bring flowers")["call_id"] == first["call_id"]
    with pytest.raises(ValueError):
        calls.enqueue("turn-1", 1, "A different message")
    calls.save_contact(1, "Someone else", "friend", "+919000000002")
    calls.tick()
    restored = Calls(tmp_path, provider)
    restored.tick()
    assert len(provider.started) == 1
    assert provider.started[0]["name"] == "Asha"
    assert provider.started[0]["phone"] == "+919000000001"
    assert restored.recent()[0]["status"] == "in-progress"


@pytest.mark.parametrize("uncertain,status", [(True, "unknown"), (False, "failed")])
def test_failed_submission_never_blindly_redials(tmp_path, uncertain, status):
    calls, provider = setup_calls(tmp_path)
    provider.error = BolnaError("Unavailable", uncertain=uncertain)
    calls.enqueue("turn", 1, "Hello")
    calls.tick()
    calls.tick()
    assert len(provider.started) == 1
    assert calls.recent()[0]["status"] == status
    assert calls.claim_update()


def test_restart_during_dispatch_does_not_redial(tmp_path):
    calls, provider = setup_calls(tmp_path)
    row = calls.enqueue("turn", 1, "Hello")
    calls.update(row["call_id"], status="dispatching")
    restored = Calls(tmp_path, provider)
    restored.start()
    restored.close()
    assert restored.recent()[0]["status"] == "unknown"
    assert not provider.started


def test_waits_for_final_result_and_interrupted_report_is_recoverable(tmp_path):
    calls, provider = setup_calls(tmp_path)
    calls.enqueue("turn", 1, "Bring flowers")
    calls.tick()
    provider.response = {"status": "call-disconnected", "transcript": "partial"}
    calls.tick()
    assert calls.claim_update() is None
    provider.response = {
        "status": "completed",
        "transcript": "user: Tomorrow.",
        "summary": "The recipient said tomorrow.",
    }
    calls.tick()
    report = calls.claim_update()
    assert "tomorrow" in report["provider_summary"]
    assert calls.claim_update() is None
    calls.release(report["id"])
    assert calls.claim_update()["id"] == report["id"]
    calls.release(report["id"], delivered=True)
    assert Calls(tmp_path, provider).claim_update() is None
    assert calls.recent()[0]["transcript"] == "user: Tomorrow."


def test_missing_recipient_and_invalid_contact_never_dispatch(tmp_path):
    calls, provider = setup_calls(tmp_path)
    for slot in [0, 6, True]:
        with pytest.raises(ValueError):
            calls.enqueue("turn", slot, "Hello")
    with pytest.raises(ValueError):
        calls.enqueue("turn", 2, "Hello")
    with pytest.raises(ValueError):
        calls.save_contact(2, "Test", "friend", "1234")
    assert not provider.started


def test_native_call_tool_binding():
    from nyx.agent_tools import bind_tool_action

    message = "Please bring flowers. " * 30
    assert bind_tool_action("relay_message", {"contact_slot": 1, "message": message}) == {
        "action": "relay_message",
        "contact_slot": 1,
        "message": message,
    }


def test_contact_api_and_cross_origin_write(tmp_path):
    from fastapi.testclient import TestClient

    from nyx.app import create_app

    with TestClient(create_app(tmp_path)) as client:
        contact = {"name": "Asha", "relationship": "daughter", "phone": "+919000000001"}
        assert client.put("/api/calling/contacts/1", json=contact).status_code == 200
        state = client.get("/api/calling").json()
        assert state["contacts"][0]["name"] == "Asha"
        assert "key" not in state
        assert client.put("/api/calling/contacts/6", json=contact).status_code == 400
        assert (
            client.put(
                "/api/calling/contacts/2", json=contact, headers={"origin": "https://other.example"}
            ).status_code
            == 403
        )
        assert client.delete("/api/calling/contacts/1").status_code == 200
        assert client.get("/api/calling").json()["contacts"] == []


def test_voice_current_result_is_in_reply_context_and_acknowledged_on_completion(
    tmp_path, monkeypatch
):
    import json

    from test_realtime import complete_reply, consume_node, replay_voice_tools, transcribe

    from nyx import realtime

    calls, provider = setup_calls(tmp_path)
    contexts = []
    monkeypatch.setattr(
        realtime.Agent.default, "llm_node", lambda agent, ctx, tools, settings: contexts.append(ctx)
    )

    async def scenario(session, socket, voice):
        await transcribe(session, "Call Asha and ask her to bring flowers")
        result = json.loads(
            await session.agent.run_tool(
                {"action": "relay_message", "contact_slot": 1, "message": "Please bring flowers"}
            )
        )
        assert result["status"] == "pending"
        calls.tick()
        provider.response = {
            "status": "completed",
            "transcript": "user: Tomorrow.",
            "summary": "She said tomorrow.",
        }
        calls.tick()
        await transcribe(session, "Did you talk to Asha?")
        context = session.agent.chat_ctx.copy()
        context.add_message(role="user", content="Did you talk to Asha?")
        await consume_node(session.agent.llm_node(context, [], {}))
        evidence = contexts[-1].items[-1].text_content
        assert '"status": "completed"' in evidence
        assert '"update_to_convey": {' in evidence
        assert "user: Tomorrow." in evidence
        assert calls.recent()[0]["reported"] == 0
        complete_reply(session)
        assert calls.recent()[0]["reported"] == 1

    replay_voice_tools(tmp_path, monkeypatch, scenario, calls=calls)


def test_interrupted_voice_update_remains_pending(tmp_path, monkeypatch):
    import time
    from types import SimpleNamespace

    from test_realtime import consume_node, replay_voice_tools, transcribe

    from nyx import realtime

    calls, provider = setup_calls(tmp_path)
    calls.enqueue("earlier", 1, "Hello")
    calls.tick()
    provider.response = {"status": "no-answer"}
    calls.tick()
    monkeypatch.setattr(realtime.Agent.default, "llm_node", lambda *args: None)

    async def scenario(session, socket, voice):
        await transcribe(session, "Hello Nyx")
        context = session.agent.chat_ctx.copy()
        context.add_message(role="user", content="Hello Nyx")
        await consume_node(session.agent.llm_node(context, [], {}))
        session.handlers["conversation_item_added"](
            SimpleNamespace(
                item=SimpleNamespace(
                    role="assistant",
                    text_content="By the way",
                    interrupted=True,
                    created_at=time.time(),
                )
            )
        )
        assert calls.recent()[0]["reported"] == 0
        await transcribe(session, "What were you saying?")
        assert calls.claim_update() is not None

    replay_voice_tools(tmp_path, monkeypatch, scenario, calls=calls)


def test_typed_tool_queues_and_reports_only_after_display_receipt(tmp_path, monkeypatch):
    import json

    from fastapi.testclient import TestClient
    from test_app import wait_for_job
    from test_companion import Planner
    from test_nyx import ColorEncoder

    from nyx.app import create_app
    from nyx.calling import Bolna

    monkeypatch.setattr(Bolna, "ready", property(lambda self: True))

    class RelayPlanner(Planner):
        def agent_reply(self, messages, tools):
            current = json.loads(messages[-1]["content"].split(": ", 1)[1])
            if current["update_to_convey"]:
                assert current["update_to_convey"]["status"] == "completed"
                return {"role": "assistant", "content": "I talked to Asha—she said tomorrow."}
            if any(row["role"] == "tool" for row in messages):
                return {"role": "assistant", "content": "I have queued the call."}
            assert '"relationship": "daughter"' in json.dumps(messages).replace('\\"', '"')
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-tool",
                        "type": "function",
                        "function": {
                            "name": "relay_message",
                            "arguments": '{"contact_slot":1,"message":"Bring flowers"}',
                        },
                    }
                ],
            }

    # No network: replace dispatch and drive completion through the durable ledger.
    monkeypatch.setattr(Calls, "tick", lambda self: None)
    calls = Calls(tmp_path)
    calls.save_contact(1, "Asha", "daughter", "+919000000001")
    with TestClient(
        create_app(tmp_path, encoder_factory=ColorEncoder, verifier_factory=RelayPlanner)
    ) as client:
        response = client.post(
            "/api/agent",
            json={"message": "Call my daughter and ask for flowers", "request_id": "typed-1"},
        )
        job = wait_for_job(client, response.json()["id"])
        assert job["status"] == "succeeded", job
        assert calls.recent()[0]["message"] == "Bring flowers"
        calls.update(calls.recent()[0]["id"], status="completed", summary="She said tomorrow.")
        response = client.post(
            "/api/agent",
            json={
                "message": "Hello",
                "request_id": "typed-2",
            },
        )
        job_id = response.json()["id"]
        result = wait_for_job(client, job_id)["result"]
        assert "tomorrow" in result["answer"]
        assert calls.recent()[0]["reported"] == 0
        assert client.post(f"/api/calling/updates/{job_id}/seen").status_code == 200
        assert calls.recent()[0]["reported"] == 1


def test_call_context_uses_current_name_only_for_same_phone_and_keeps_reported_results(tmp_path):
    calls, provider = setup_calls(tmp_path)
    calls.enqueue("turn", 1, "Are you free?")
    calls.tick()
    provider.response = {"status": "completed", "transcript": "user: Yes."}
    calls.tick()
    calls.save_contact(1, "Updated name", "friend", "+919000000001")
    report = calls.claim_update()
    assert report["recipient"] == "Updated name"
    calls.release(report["id"], delivered=True)
    assert calls.context()["recent_calls"][0]["status"] == "completed"
    assert calls.claim_update() is None
    calls.save_contact(1, "Different person", "friend", "+919000000002")
    assert calls.context()["recent_calls"][0]["recipient"] == "Asha"


@pytest.mark.parametrize(
    "reason,hangup,status,error",
    [
        ("agent_voice_error", "synthesizer_error", "failed", "voice service failed"),
        (None, "synthesizer_error", "failed", "voice service failed"),
        ("inactivity_timeout", "inactivity_timeout", "completed", "silence timeout"),
        ("user_hangup", None, "completed", ""),
    ],
)
@pytest.mark.parametrize("transcript", ["", "user: I'll come over at seven."])
def test_terminal_call_reason_is_exposed_without_claiming_recipient_behavior(
    tmp_path, reason, hangup, status, error, transcript
):
    calls, provider = setup_calls(tmp_path)
    calls.enqueue("turn", 1, "When are you coming over?")
    calls.tick()
    provider.response = {
        "status": "completed",
        "termination_reason": reason,
        "telephony_data": {"hangup_reason": hangup},
        "transcript": transcript,
    }
    calls.tick()
    report = calls.claim_update()
    assert report["status"] == status
    assert error in report["error"]
    assert report["transcript"] == transcript
    assert "no response was confirmed" not in report["error"]
    assert len(provider.started) == 1
    calls.tick()
    assert len(provider.started) == 1
