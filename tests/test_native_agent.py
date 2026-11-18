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


def call(name="look_for_object", **arguments):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def test_historical_recall_scopes_prepared_memory_before_final_generation():
    current = {
        "id": "new",
        "turn_id": "new",
        "content": "CURRENT_CUPBOARD",
        "at": "2026-11-12T12:00:00Z",
        "sources": ["transcript:new"],
    }
    prepared = {
        "kind": "memory",
        "status": "noop",
        "records": [current],
        "sources": ["transcript:new"],
    }
    generations = []

    def generate(messages, tools):
        generations.append(json.dumps(messages))
        if len(generations) == 1:
            return call("recall_memory", query="camera", as_of="2026-11-11T12:00:00Z")
        assert "CURRENT_CUPBOARD" not in generations[-1]
        return {"role": "assistant", "content": "Your report then said dining shelf."}

    result = finish(
        native_agent_steps(
            "What did I report as of November 11?",
            [],
            generate,
            lambda action: {
                "kind": "memories",
                "status": "retrieved",
                "matches": [],
                "sources": ["transcript:old"],
            },
            memory_context=prepared,
        )
    )
    assert result["sources"] == ["transcript:old"]
    assert prepared["records"] == [current]


@pytest.mark.parametrize("stage", ["generation", "tool"])
def test_provider_failure_is_not_retried_or_converted_into_success(stage):
    from nyx.cloud import CloudError

    calls = []

    def generate(*args):
        calls.append("generation")
        if stage == "generation":
            raise CloudError("Provider unavailable")
        return call(query="glasses", history=True)

    def tool(action):
        calls.append("tool")
        raise CloudError("Provider unavailable")

    with pytest.raises(CloudError, match="unavailable"):
        finish(native_agent_steps("Find glasses", [], generate, tool))
    assert calls == (["generation"] if stage == "generation" else ["generation", "tool"])


def test_identical_calls_are_cached_and_failure_to_finish_is_reported():
    tools = []
    result = finish(
        native_agent_steps(
            "Find glasses",
            [],
            lambda *args: call(query="glasses"),
            lambda action: tools.append(action) or {"status": "seen", "answer": "A candidate"},
            max_steps=3,
        )
    )
    assert len(tools) == 1
    assert result["status"] == "uncertain" and "limit" in result["answer"]


def test_temporal_boundary_cannot_be_dropped_after_a_tool_returns_it():
    requests = [
        call(query="book", history=True, hours=0, before_frame_id=20),
        call(query="book", history=True, hours=0),
        {"role": "assistant", "content": "I could not complete the earlier search."},
    ]
    tools = []

    def tool(action):
        tools.append(action)
        return {"status": "uncertain", "answer": "No match yet", "scope": {"before_frame_id": 20}}

    result = finish(
        native_agent_steps("Earlier than that", [], lambda *args: requests.pop(0), tool)
    )
    assert len(tools) == 1
    assert "Retain before_frame_id=20" in result["decision_errors"][0]


def test_cancellation_between_tool_progress_steps_closes_the_source_generator():
    state = {"cancelled": False, "closed": False}

    def tool(action):
        try:
            yield {"progress": "first"}
            state["cancelled"] = True
            yield {"progress": "second"}
            pytest.fail("Cancelled source generator advanced")
        finally:
            state["closed"] = True

    with pytest.raises(ValueError, match="cancel"):
        finish(
            native_agent_steps(
                "Find book",
                [],
                lambda *args: call(query="book"),
                tool,
                cancelled=lambda: state["cancelled"],
            )
        )
    assert state["closed"]


def test_memory_sources_are_retained_without_an_explicit_recall_tool_call():
    memory = {"kind": "memory", "status": "saved", "records": [], "sources": ["transcript:fact"]}

    def generate(messages, tools):
        assert "Memory context:" in messages[-1]["content"]
        return {"role": "assistant", "content": "I remember your preference."}

    result = finish(
        native_agent_steps(
            "I prefer tea", [], generate, lambda _: pytest.fail(), memory_context=memory
        )
    )
    assert result["sources"] == ["transcript:fact"] and result["status"] == "saved"
