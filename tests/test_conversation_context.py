import json
from copy import deepcopy

import pytest


def test_typed_provider_never_receives_invalidated_assistant_claims():
    from test_native_agent import finish

    from nyx.agent import native_agent_steps

    payloads = []

    def generate(messages, tools):
        payloads.append(messages)
        return {"role": "assistant", "content": "Which phone do you mean?"}

    finish(
        native_agent_steps(
            "Where is it?",
            [
                {
                    "transcript": "Find my green phone",
                    "answer": "It was beside the deleted orange vase.",
                    "sources_available": False,
                    "plan": {
                        "steps": [{"action": "search_history", "query": "green phone", "hours": 2}]
                    },
                }
            ],
            generate,
            lambda _: pytest.fail(),
        )
    )
    assert "deleted orange vase" not in json.dumps(payloads)
    assert "green phone" in json.dumps(payloads)


def test_recent_context_is_bounded_without_mutating_saved_rows():
    from nyx.conversation_context import recent_context

    turns = [
        {
            "id": str(i),
            "status": "complete",
            "at": "2026-11-14T12:00:00Z",
            "transcript": f"Request {i}: " + "a" * 1400,
            "answer": "b" * 8000,
            "sources_available": True,
            "plan": {
                "snapshot": "private-large-blob" * 10000,
                "steps": [
                    {
                        "action": "search_history",
                        "query": "green phone",
                        "hours": 240,
                        "excluded_frame_ids": [10, 11],
                        "before_frame_id": 20,
                    }
                ],
            },
        }
        for i in range(30)
    ]
    original = deepcopy(turns)
    context = recent_context(turns)
    assert len(json.dumps(context, ensure_ascii=False)) <= 12000
    assert len(context) <= 12 and context[-1]["id"] == "29"
    assert context[-1]["plan"]["steps"][-1]["query"] == "green phone"
    assert context[-1]["plan"]["steps"][-1]["before_frame_id"] == 20
    assert context[-1]["plan"]["steps"][-1]["excluded_frame_ids"] == [10, 11]
    assert "private-large-blob" not in json.dumps(context)
    assert turns == original


def test_unavailable_context_removes_answers_and_source_reference_metadata():
    from nyx.conversation_context import recent_context

    row = {
        "status": "complete",
        "transcript": "Find my keys",
        "answer": "Deleted location",
        "sources_available": False,
        "plan": {
            "candidate": {"frame_id": 42, "object_query": "keys"},
            "statement_refs": [{"turn_id": "withdrawn"}],
        },
    }
    context = recent_context([row])
    assert not context[0].get("answer")
    assert not context[0]["plan"].get("candidate")
    assert not context[0]["plan"].get("statement_refs")


def test_report_selection_and_historical_cutoff_survive_context_projection():
    from nyx.conversation_context import recent_context

    row = {
        "status": "complete",
        "transcript": "Use the newest report at that time",
        "answer": "A saved report",
        "plan": {
            "steps": [
                {
                    "action": "search_statements",
                    "query": "green phone",
                    "as_of": "2026-11-07T12:00:00Z",
                    "selection": "latest_report",
                }
            ]
        },
    }
    step = recent_context([row])[0]["plan"]["steps"][0]
    assert step["as_of"] == "2026-11-07T12:00:00Z"
    assert step["selection"] == "latest_report"


def test_live_context_keeps_current_tool_pair_and_instructions_when_history_is_evicted():
    from livekit.agents import llm

    from nyx.conversation_context import bounded_live_context

    chat = llm.ChatContext()
    chat.add_message(role="system", content="Trusted instructions")
    for i in range(30):
        chat.add_message(role="user", content=f"Old question {i}")
        chat.add_message(role="assistant", content="Old answer " * 200)
    chat.add_message(role="user", content="Find the green phone")
    chat.items.extend(
        [
            llm.FunctionCall(
                call_id="current", name="look_for_object", arguments='{"query":"green phone"}'
            ),
            llm.FunctionCallOutput(
                call_id="current",
                name="look_for_object",
                output="Checked a candidate",
                is_error=False,
            ),
        ]
    )
    original_count = len(chat.items)
    bounded = bounded_live_context(chat, max_chars=12000, max_items=16)
    assert len(bounded.items) <= 16
    assert bounded.items[0].text_content == "Trusted instructions"
    assert [item.type for item in bounded.items[-3:]] == [
        "message",
        "function_call",
        "function_call_output",
    ]
    assert bounded.items[-3].text_content == "Find the green phone"
    assert bounded.items[-2].call_id == bounded.items[-1].call_id == "current"
    assert len(chat.items) == original_count


def test_oversized_active_tool_exchange_fails_before_provider_inference():
    from livekit.agents import llm

    from nyx.cloud import CloudError
    from nyx.conversation_context import bounded_live_context

    chat = llm.ChatContext()
    chat.add_message(role="user", content="Current request")
    chat.items.extend(
        [
            llm.FunctionCall(call_id="current", name="search_statements", arguments="{}"),
            llm.FunctionCallOutput(
                call_id="current", name="search_statements", output="x" * 20000, is_error=False
            ),
        ]
    )
    with pytest.raises(CloudError):
        bounded_live_context(chat, max_chars=12000)


def test_future_dated_facts_cannot_bypass_memory_eligibility_through_chat_history():
    from test_native_agent import finish

    from nyx.agent import native_agent_steps

    payloads = []

    def generate(messages, tools):
        payloads.append(messages)
        return {"role": "assistant", "content": "No eligible report found."}

    context = [
        {
            "at": "2099-01-01T00:00:00Z",
            "transcript": "My watch is in the bathroom cabinet.",
            "answer": "Saved in bathroom cabinet",
            "sources_available": True,
            "plan": {"steps": [{"action": "recall_memory", "query": "bathroom cabinet"}]},
        }
    ]
    finish(
        native_agent_steps(
            "What have I said about my watch up to now?", context, generate, lambda _: pytest.fail()
        )
    )
    serialized = json.dumps(payloads)
    assert "bathroom cabinet" not in serialized
    assert "timestamp is invalid or in the future" in serialized
    assert context[0]["transcript"] == "My watch is in the bathroom cabinet."
