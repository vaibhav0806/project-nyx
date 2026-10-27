"""Evaluation must expose failures rather than reward missing actions."""

import runpy
from pathlib import Path

score_case = runpy.run_path(str(Path(__file__).parents[1] / "experiments/companion/planner.py"))[
    "score_case"
]


def test_rejection_without_search_does_not_pass_exclusion_check():
    checks = score_case(
        {"concepts": [], "required_exclusions": [74]},
        {"status": "chat", "steps": [{"action": "chat", "message": "Okay"}]},
    )
    assert not checks["rejected_frames"]


def test_unrelated_search_fails_when_it_carries_old_exclusions():
    checks = score_case(
        {"concepts": ["wallet"], "no_exclusions": True},
        {
            "status": "seen",
            "steps": [
                {
                    "action": "search_history",
                    "query": "brown wallet",
                    "hours": 2,
                    "excluded_frame_ids": [74],
                }
            ],
        },
    )
    assert checks["query_concepts"]
    assert not checks["no_stale_exclusions"]


def test_time_change_does_not_authorize_rejecting_candidate():
    checks = score_case(
        {"concepts": ["glasses"], "forbidden_exclusions": [74]},
        {
            "status": "seen",
            "steps": [
                {
                    "action": "search_history",
                    "query": "reading glasses",
                    "hours": 24,
                    "excluded_frame_ids": [71, 74],
                }
            ],
        },
    )
    assert not checks["no_unrequested_rejection"]


def test_older_footage_requires_a_wider_window():
    case = {"concepts": ["glasses"], "wider_than_hours": 2}
    result = {
        "status": "seen",
        "steps": [{"action": "search_history", "query": "glasses", "hours": 2}],
    }
    assert not score_case(case, result)["requested_wider_window"]
    result["steps"][0]["hours"] = 24
    assert score_case(case, result)["requested_wider_window"]
    result["steps"][0]["hours"] = 0
    assert score_case(case, result)["requested_wider_window"]
