from datetime import UTC, datetime

import pytest


def complete(steps):
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def test_agent_observes_failure_and_chooses_another_tool_before_finishing():
    from nyx.agent import agent_steps

    decisions = iter(
        [
            {"action": "inspect_current", "query": "silver reading glasses"},
            {"action": "search_history", "query": "silver reading glasses", "hours": 2},
            {"action": "finish", "observation": 1},
        ]
    )

    def decide(state):
        if len(state["observations"]) == 1:
            assert state["observations"][0]["status"] == "uncertain"
        return next(decisions)

    def tool(action):
        if action["action"] == "inspect_current":
            return {
                "kind": "snapshot",
                "status": "uncertain",
                "answer": "Not confirmed in this view.",
                "checked": [],
            }
        assert action["hours"] == 2
        return {
            "kind": "history",
            "status": "seen",
            "answer": "Last seen beside the newspaper this morning.",
            "checked": [{"video_id": "source-1"}],
        }

    result = complete(agent_steps("Where are the reading ones?", [], decide, tool))
    assert result["status"] == "seen"
    assert result["answer"] == "Last seen beside the newspaper this morning."
    assert result["sources"] == ["source-1"]
    assert [step["action"] for step in result["steps"]] == [
        "inspect_current",
        "search_history",
        "finish",
    ]


def test_agent_cannot_invent_a_visual_answer_or_run_without_a_bound():
    from nyx.agent import agent_steps

    result = complete(
        agent_steps(
            "Where are my glasses?",
            [],
            lambda state: {"action": "finish", "observation": 3},
            lambda action: pytest.fail("No tool selected"),
        )
    )
    assert result["status"] == "uncertain"
    repeated = complete(
        agent_steps(
            "Find glasses",
            [],
            lambda state: {"action": "inspect_current", "query": "glasses"},
            lambda action: {"status": "uncertain", "answer": "Unclear"},
            max_steps=3,
        )
    )
    assert len(repeated["steps"]) <= 3
    assert repeated["status"] == "uncertain"


def test_agent_cancellation_prevents_a_pending_side_effect():
    from nyx.agent import agent_steps

    steps = agent_steps(
        "Remind me about water",
        [],
        lambda state: {"action": "remind_on_departure", "message": "Take water"},
        lambda action: pytest.fail("Cancelled tool must not execute"),
        cancelled=lambda: True,
    )
    with pytest.raises(ValueError, match="cancelled"):
        complete(steps)


def test_agent_context_keeps_corrections_but_marks_deleted_evidence_unavailable():
    from nyx.agent import agent_steps

    context = [
        {"transcript": "The thin silver pair", "answer": "Old location", "sources_available": False}
    ]

    def decide(state):
        assert state["conversation"][0]["transcript"] == "The thin silver pair"
        assert state["conversation"][0]["sources_available"] is False
        assert datetime.fromisoformat(state["now"]).tzinfo == UTC
        return {"action": "clarify", "message": "Do you mean your silver reading glasses?"}

    result = complete(agent_steps("Find them", context, decide, lambda action: None))
    assert result["status"] == "clarify"
