import json

import pytest

from nyx.agent import native_agent_steps
from nyx.agent_policy import AGENT_INSTRUCTIONS


def finish(generator):
    while True:
        try:
            next(generator)
        except StopIteration as done:
            return done.value


def test_native_tools_continue_to_an_answer_with_real_evidence_sources():
    calls, actions = [], []

    def generate(messages, tools):
        calls.append(messages.copy())
        assert messages[0]["content"] == AGENT_INSTRUCTIONS
        assert "look_for_object" in [row["function"]["name"] for row in tools]
        if len(calls) == 1:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "look_for_object",
                            "arguments": json.dumps(
                                {"query": "blue bottle", "history": True, "hours": 240}
                            ),
                        },
                    }
                ],
            }
        assert messages[-1]["role"] == "tool" and messages[-1]["tool_call_id"] == "call-1"
        assert "snapshot_url" not in messages[-1]["content"]
        return {"role": "assistant", "content": "I found a possible match in the recording."}

    def tool(action):
        actions.append(action)
        return {
            "kind": "history",
            "status": "candidate",
            "answer": "A possible match.",
            "checked": [{"video_id": "clip-1", "id": 3}],
            "sources": ["clip-1"],
            "snapshot_url": "data:image/jpeg;base64,not-model-text",
        }

    result = finish(native_agent_steps("Where did I last see my bottle?", [], generate, tool))
    assert actions == [{"action": "search_history", "query": "blue bottle", "hours": 240}]
    assert result["answer"] == "I found a possible match in the recording."
    assert result["sources"] == ["clip-1"]
    assert result["visual"]["status"] == "candidate"


def test_delegated_voice_tool_executes_without_another_model_decision():
    def no_model(*args):
        raise AssertionError("A native voice tool must not invoke a second conversational planner")

    result = finish(
        native_agent_steps(
            "What is this?",
            [],
            no_model,
            lambda action: {"kind": "reference", "status": "clarify", "answer": "Which item?"},
            initial_action={"action": "identify_shown_object"},
        )
    )
    assert result["status"] == "clarify" and result["answer"] == "Which item?"


def test_cancellation_before_model_or_tool_work_is_not_swallowed():
    def forbidden(*args):
        raise AssertionError("Cancelled work ran")

    with pytest.raises(ValueError, match="cancel"):
        finish(native_agent_steps("Hello", [], forbidden, forbidden, cancelled=lambda: True))


def test_existing_direct_chat_payload_preserves_the_api_contract():
    def forbidden(*args):
        raise AssertionError("A direct response is not an inference or backend tool")

    result = finish(
        native_agent_steps(
            "Hello", [], forbidden, forbidden, initial_action={"action": "chat", "message": "Hello"}
        )
    )
    assert result["answer"] == "Hello" and result["status"] == "chat"
