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


def test_repeated_tool_decision_can_be_repaired_without_repeating_the_tool():
    from nyx.agent import agent_steps

    decisions = iter(
        [
            {"action": "inspect_current", "query": "reading glasses"},
            {"action": "inspect_current", "query": "reading glasses"},
            {"action": "search_history", "query": "reading glasses", "hours": 2},
            {"action": "finish", "observation": 1},
        ]
    )
    checked = []

    def tool(action):
        checked.append(action["action"])
        return {
            "status": "uncertain" if action["action"] == "inspect_current" else "seen",
            "answer": "Unclear current view"
            if action["action"] == "inspect_current"
            else "Checked historical sighting",
        }

    result = complete(agent_steps("Find reading glasses", [], lambda state: next(decisions), tool))
    assert result["status"] == "seen"
    assert checked == ["inspect_current", "search_history"]
    assert len(result["decision_errors"]) == 1


def test_still_there_followup_checks_fresh_view_before_historical_evidence():
    from nyx.agent import agent_steps

    decisions = iter(
        [
            {"action": "search_history", "query": "television remote", "hours": 2},
            {"action": "finish", "observation": 0},
        ]
    )

    def tool(action):
        assert action["action"] == "inspect_current"
        return {"kind": "snapshot", "status": "seen", "answer": "Checked current remote"}

    result = complete(
        agent_steps(
            "Is it still there?",
            [{"transcript": "Find my remote", "answer": "Seen yesterday"}],
            lambda state: next(decisions),
            tool,
            available={"current_view": True},
        )
    )
    assert result["status"] == "seen"


def test_planner_rejects_an_already_checked_visual_tool():
    from nyx.verification import LocalVerifier

    verifier = object.__new__(LocalVerifier)
    verifier.generate_json = lambda *args: '{"action":"inspect_current","query":"reading glasses"}'
    with pytest.raises(ValueError, match="already|available"):
        verifier.decide(
            {
                "message": "Find reading glasses",
                "available": {"current_view": True, "history": True},
                "actions": [{"action": "inspect_current", "query": "reading glasses"}],
                "observations": [
                    {"index": 0, "kind": "snapshot", "status": "uncertain", "answer": "Unclear"}
                ],
            }
        )


def test_continuation_repair_and_window_progression_fit_the_six_decision_limit():
    from nyx.agent import agent_steps

    decisions = iter(
        [
            {"action": "inspect_current", "query": "reading glasses"},
            {"action": "inspect_current", "query": "reading glasses"},
            {"action": "search_history", "query": "reading glasses", "hours": 2},
            {"action": "search_history", "query": "reading glasses", "hours": 2},
            {"action": "finish", "observation": 2},
        ]
    )
    seen = []

    def tool(action):
        seen.append(action)
        return {
            "status": "seen" if action.get("hours") == 24 else "uncertain",
            "answer": "Controlled evidence",
        }

    result = complete(agent_steps("Find reading glasses", [], lambda state: next(decisions), tool))
    assert result["status"] == "seen"
    assert [row.get("hours") for row in seen] == [None, 2, 24]
    assert len(result["decision_errors"]) == 1
    assert result["policy_adjustments"][0]["to"]["hours"] == 24


def test_repeated_window_advances_but_a_new_query_in_the_same_window_is_retained():
    from nyx.agent import agent_steps

    decisions = iter(
        [
            {"action": "search_history", "query": "silver glasses", "hours": 2},
            {"action": "search_history", "query": "thin silver reading glasses", "hours": 2},
            {"action": "finish", "observation": 1},
        ]
    )
    queries = []

    def tool(action):
        queries.append((action["query"], action["hours"]))
        return {
            "status": "uncertain" if len(queries) == 1 else "seen",
            "answer": "Controlled result",
        }

    result = complete(agent_steps("Find glasses", [], lambda state: next(decisions), tool))
    assert result["status"] == "seen"
    assert queries == [("silver glasses", 2), ("thin silver reading glasses", 2)]
    assert result["policy_adjustments"] == []


def test_repeating_a_day_window_broadens_to_a_week_without_narrowing_to_two_hours():
    from nyx.agent import agent_steps

    decisions = iter(
        [
            {"action": "search_history", "query": "glasses", "hours": 24},
            {"action": "search_history", "query": "glasses", "hours": 24},
            {"action": "finish", "observation": 1},
        ]
    )
    hours = []

    def tool(action):
        hours.append(action["hours"])
        return {
            "status": "seen" if action["hours"] == 168 else "uncertain",
            "answer": "Controlled evidence",
        }

    result = complete(agent_steps("Last seen glasses", [], lambda state: next(decisions), tool))
    assert result["status"] == "seen"
    assert hours == [24, 168]


def test_completed_evidence_at_decision_limit_is_returned_without_another_model_call():
    from nyx.agent import agent_steps

    result = complete(
        agent_steps(
            "Find glasses",
            [],
            lambda state: {"action": "inspect_current", "query": "glasses"},
            lambda action: {
                "kind": "snapshot",
                "status": "seen",
                "answer": "Checked at left of book",
            },
            max_steps=1,
        )
    )
    assert result["status"] == "seen"
    assert result["answer"] == "Checked at left of book"
    assert len(result["steps"]) == 1


def test_explicit_last_seen_question_cannot_be_answered_from_current_view_only():
    from nyx.agent import agent_steps

    decisions = iter(
        [
            {"action": "inspect_current", "query": "blue water bottle"},
            {"action": "finish", "observation": 0},
        ]
    )

    def tool(action):
        assert action == {"action": "search_history", "query": "blue water bottle", "hours": 2}
        return {"kind": "history", "status": "seen", "answer": "Checked historical sighting"}

    result = complete(
        agent_steps(
            "Where did you last see it?",
            [],
            lambda state: next(decisions),
            tool,
            available={"current_view": True, "dated_history": True},
        )
    )
    assert result["status"] == "seen"


def test_schema_placeholder_is_not_a_resolved_visual_query():
    from nyx.verification import LocalVerifier

    verifier = object.__new__(LocalVerifier)
    verifier.generate_json = lambda *args: (
        '{"action":"inspect_current","query":"resolved object description"}'
    )
    with pytest.raises(ValueError, match="description|query"):
        verifier.decide({"message": "Find my remote", "available": {"current_view": True}})


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


def test_present_question_checks_available_current_view_before_archive():
    from nyx.agent import agent_steps

    decisions = iter(
        [
            {"action": "search_history", "query": "reading glasses", "hours": 2},
            {"action": "finish", "observation": 0},
        ]
    )

    def tool(action):
        assert action["action"] == "inspect_current"
        return {"kind": "snapshot", "status": "seen", "answer": "Visible beside the book"}

    result = complete(
        agent_steps(
            "Where are my reading glasses?",
            [],
            lambda state: next(decisions),
            tool,
            available={"current_view": True},
        )
    )
    assert result["status"] == "seen"


def test_cancellation_stops_between_history_images_not_after_the_entire_tool():
    from nyx.agent import agent_steps

    stopped = [False]

    def history(action):
        yield {"checked": 1}
        pytest.fail("A cancelled request must not inspect another image")

    steps = agent_steps(
        "Where did you last see glasses?",
        [],
        lambda state: {"action": "search_history", "query": "glasses", "hours": 2},
        history,
        cancelled=lambda: stopped[0],
    )
    assert next(steps) == {"checked": 1}
    stopped[0] = True
    with pytest.raises(ValueError, match="cancelled"):
        next(steps)


def test_time_budget_is_checked_between_images_of_a_history_tool(monkeypatch):
    from nyx.agent import agent_steps

    clock = [0.0]
    monkeypatch.setattr("nyx.agent.time.monotonic", lambda: clock[0])

    def history(action):
        yield {"checked": 1}
        pytest.fail("No further inference should start after the request budget")

    steps = agent_steps(
        "Last seen glasses",
        [],
        lambda state: {"action": "search_history", "query": "glasses", "hours": 2},
        history,
    )
    assert next(steps) == {"checked": 1}
    clock[0] = 100.0
    assert complete(steps)["status"] == "uncertain"


def test_invalid_completion_gets_one_bounded_correction_before_a_real_tool_result():
    from nyx.agent import agent_steps

    decisions = iter(
        [
            {"action": "finish", "observation": 0},
            {"action": "remind_on_departure", "message": "Take water"},
            {"action": "finish", "observation": 0},
        ]
    )

    def decide(state):
        if state.get("decision_error"):
            assert not state["observations"]
            assert "observation" in state["decision_error"]
        return next(decisions)

    result = complete(
        agent_steps(
            "Remind me to take water when I leave",
            [],
            decide,
            lambda action: {"status": "armed", "answer": "Next departure request saved"},
        )
    )
    assert result["status"] == "armed"
    assert result["answer"] == "Next departure request saved"
    assert len(result["decision_errors"]) == 1


@pytest.mark.parametrize(
    "status", ["seen", "candidate", "armed", "cancelled", "complete", "clarify"]
)
def test_completed_tool_result_needs_no_additional_model_generation(status):
    from nyx.verification import LocalVerifier

    verifier = object.__new__(LocalVerifier)
    verifier.generate_json = lambda *args: pytest.fail(
        "Completed evidence needs no more generation"
    )
    action = verifier.decide(
        {
            "observations": [
                {"index": 0, "status": "uncertain", "answer": "No current view"},
                {"index": 1, "status": status, "answer": "Authoritative completed tool result"},
            ]
        }
    )
    assert action == {"action": "finish", "observation": 1}


def test_changed_object_query_has_its_own_search_windows_without_loading_model():
    import json

    from nyx.verification import LocalVerifier

    verifier = LocalVerifier.__new__(LocalVerifier)

    def generate(messages, *args):
        state = json.loads(messages[1]["content"])
        assert state["remaining_query"] == "blue bottle"
        assert state["remaining_history_hours"] == [2, 24, 168, 0]
        assert state["message"] == "No, the blue bottle, not the red one"
        return '{"action":"search_history","query":"blue bottle","hours":2}'

    verifier.generate_json = generate
    result = verifier.decide(
        {
            "message": "No, the blue bottle, not the red one",
            "conversation": [{"transcript": "Find my red bottle", "answer": "Earlier answer"}],
            "available": {"current_view": True, "history": True},
            "actions": [
                {"action": "search_history", "query": "red bottle", "hours": 2},
                {"action": "search_history", "query": "red bottle", "hours": 24},
                {"action": "inspect_current", "query": "blue bottle"},
            ],
            "observations": [{"status": "uncertain", "answer": "Not confirmed"}],
        }
    )
    assert result["query"] == "blue bottle" and result["hours"] == 2


def test_corrected_query_survives_time_widening_and_old_answer_is_not_evidence():
    from nyx.agent import agent_steps

    context = [{"transcript": "Where is my red bottle?", "answer": "By the window"}]
    choices = iter(
        [
            {"action": "inspect_current", "query": "blue water bottle"},
            {"action": "search_history", "query": "blue water bottle", "hours": 2},
            {"action": "search_history", "query": "blue water bottle", "hours": 2},
            {"action": "finish", "observation": 2},
        ]
    )

    def decide(state):
        assert state["conversation"] == context
        assert state["message"] == "No, the blue water bottle, not that one"
        return next(choices)

    received = []

    def tool(action):
        received.append(action)
        return {"status": "uncertain", "answer": "No confirmed sighting"}

    result = complete(agent_steps("No, the blue water bottle, not that one", context, decide, tool))
    assert all(row["query"] == "blue water bottle" for row in received)
    assert [row.get("hours") for row in received] == [None, 2, 24]
    assert result["answer"] == "No confirmed sighting"
    assert result["sources"] == []


def test_planner_can_inspect_a_changed_query_after_an_uncertain_current_check():
    from nyx.verification import LocalVerifier

    verifier = object.__new__(LocalVerifier)
    verifier.generate_json = lambda *args: (
        '{"action":"inspect_current","query":"silver reading glasses"}'
    )
    action = verifier.decide(
        {
            "message": "Find the silver reading glasses",
            "available": {"current_view": True, "history": True},
            "actions": [{"action": "inspect_current", "query": "glasses"}],
            "observations": [
                {"index": 0, "kind": "snapshot", "status": "uncertain", "answer": "Ambiguous"}
            ],
        }
    )
    assert action == {"action": "inspect_current", "query": "silver reading glasses"}


def test_followup_planner_receives_last_corrected_tool_query_without_old_evidence():
    import json

    from nyx.verification import LocalVerifier

    verifier = object.__new__(LocalVerifier)

    def generate(messages):
        state = json.loads(messages[1]["content"])
        turn = state["conversation"][-1]
        assert turn["previous_tool_query"] == "green ceramic mug"
        assert turn["sources_available"] is False
        assert turn["transcript"] == "No, the green ceramic one"
        return json.dumps(
            {"action": "search_history", "query": turn["previous_tool_query"], "hours": 2}
        )

    verifier.generate_json = generate
    action = verifier.decide(
        {
            "message": "Where did you last see it?",
            "conversation": [
                {
                    "transcript": "No, the green ceramic one",
                    "answer": "Old answer",
                    "sources_available": False,
                    "plan": {
                        "steps": [
                            {"action": "inspect_current", "query": "mug"},
                            {"action": "inspect_current", "query": "green ceramic mug"},
                            {"action": "finish", "observation": 1},
                        ]
                    },
                }
            ],
            "available": {"current_view": False, "history": True},
        }
    )
    assert action["query"] == "green ceramic mug"


def test_search_argument_repair_identifies_extra_field_before_tool_execution():
    from nyx.agent import agent_steps

    def decide(state):
        if state["observations"]:
            return {"action": "finish", "observation": 0}
        if state.get("decision_error"):
            assert "search_matches" in state["decision_error"]
            assert "Remove: hours" in state["decision_error"]
            return {"action": "search_matches", "query": "red mug"}
        return {"action": "search_matches", "query": "red mug", "hours": 2}

    calls = []

    def tool(action):
        calls.append(action)
        return {"status": "seen", "answer": "Controlled imported sighting"}

    result = complete(agent_steps("Find the red mug in my imported clip", [], decide, tool))
    assert calls == [{"action": "search_matches", "query": "red mug"}]
    assert len(result["decision_errors"]) == 1
    assert result["status"] == "seen"


@pytest.mark.parametrize("dated,expected", [(True, "search_history"), (False, "search_matches")])
def test_last_seen_starts_with_dated_history_before_undated_matches(dated, expected):
    from nyx.agent import agent_steps

    choices = iter(
        [
            {"action": "search_matches", "query": "green ceramic mug"},
            {"action": "finish", "observation": 0},
        ]
    )
    calls = []

    def tool(action):
        calls.append(action)
        return {"status": "seen", "answer": "Controlled sighting with appropriate time attribution"}

    complete(
        agent_steps(
            "Where did you last see it?",
            [],
            lambda state: next(choices),
            tool,
            available={"dated_history": dated, "undated_history": True, "history": True},
        )
    )
    assert calls[0]["action"] == expected
    assert calls[0]["query"] == "green ceramic mug"
    if dated:
        assert calls[0]["hours"] == 2


@pytest.mark.parametrize("ids", [[True], [-1], ["2"], list(range(33)), "1"])
def test_search_rejects_invalid_exclusion_ids(ids):
    from nyx.agent import validate_action

    with pytest.raises(ValueError, match="frame IDs"):
        validate_action({"action": "search_matches", "query": "mug", "excluded_frame_ids": ids})


def test_planner_receives_candidate_and_rejections_without_image_payloads():
    import json

    from nyx.verification import LocalVerifier

    verifier = object.__new__(LocalVerifier)

    def generate(messages):
        state = json.loads(messages[1]["content"])
        assert state["review_context"]["candidate"]["frame_id"] == 42
        assert state["review_context"]["exclusions_if_rejected"] == [40, 42]
        assert "nah man" in messages[0]["content"]
        return json.dumps(
            {
                "action": "search_history",
                "query": "blue mug",
                "hours": 24,
                "excluded_frame_ids": [40, 42],
            }
        )

    verifier.generate_json = generate
    action = verifier.decide(
        {
            "message": "nah, not that one",
            "conversation": [
                {
                    "transcript": "Find my blue mug",
                    "answer": "Is this it?",
                    "plan": {
                        "candidate": {
                            "frame_id": 42,
                            "object_query": "blue mug",
                            "excluded_frame_ids": [40],
                        },
                        "steps": [
                            {
                                "action": "search_history",
                                "query": "blue mug",
                                "hours": 2,
                                "excluded_frame_ids": [40],
                            }
                        ],
                    },
                }
            ],
        }
    )
    assert action["excluded_frame_ids"] == [40, 42]


def test_history_policy_adjustment_preserves_model_selected_exclusions():
    from nyx.agent import agent_steps

    calls = []

    def decide(state):
        return (
            {"action": "finish", "observation": 0}
            if state["observations"]
            else {"action": "search_matches", "query": "glasses", "excluded_frame_ids": [71, 74]}
        )

    def tool(action):
        calls.append(action)
        return {"kind": "history", "status": "candidate", "answer": "Is this it?"}

    complete(
        agent_steps(
            "Where did you last see them?",
            [],
            decide,
            tool,
            available={"dated_history": True, "history": True},
        )
    )
    assert calls == [
        {"action": "search_history", "query": "glasses", "hours": 2, "excluded_frame_ids": [71, 74]}
    ]
