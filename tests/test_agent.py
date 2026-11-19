import pytest


def test_historical_memory_argument_is_strictly_validated_and_old_tools_retired():
    from nyx.agent import validate_action

    assert validate_action(
        {"action": "recall_memory", "query": "phone", "as_of": "2026-11-06T12:00:00Z"}
    )["as_of"]
    for action in [
        {"action": "remember_statement"},
        {"action": "remind_on_departure", "message": "Water"},
        {"action": "recall_memory", "query": "phone", "as_of": "2026-11-06T12:00:00"},
    ]:
        with pytest.raises((ValueError, TypeError)):
            validate_action(action)


def complete(steps):
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


@pytest.mark.parametrize("ids", [[True], [-1], ["2"], list(range(33)), "1"])
def test_search_rejects_invalid_exclusion_ids(ids):
    from nyx.agent import validate_action

    with pytest.raises(ValueError, match="frame IDs"):
        validate_action({"action": "search_matches", "query": "mug", "excluded_frame_ids": ids})


@pytest.mark.parametrize("identifier", [True, -1, "12", 1.5, None])
def test_history_boundary_requires_a_saved_frame_id(identifier):
    from nyx.agent import validate_action

    with pytest.raises(ValueError, match="before_frame_id"):
        validate_action(
            {"action": "search_history", "query": "book", "hours": 0, "before_frame_id": identifier}
        )


def test_visual_tool_projection_keeps_evidence_without_canned_prose():
    from nyx.agent import _model_tool_result

    result = {
        "kind": "history",
        "answer": "A possible match. Its identity is unconfirmed.",
        "identity_verified": False,
        "evidence": {
            "observed_at": "2026-10-19T02:08:00+05:30",
            "judgment": {
                "visibility": "visible",
                "presence": "physical",
                "location": "in the hands",
                "description": "a black phone",
                "scene_context": "probably filming themselves",
            },
        },
    }
    result["status"] = "candidate"
    result["evidence"].update(id=768, similarity=0.36, video_path="recordings/a.webm")
    projected = _model_tool_result(result)
    assert projected == {
        "kind": "history",
        "status": "candidate",
        "frame_id": 768,
        "seen_at": "2026-10-19T02:08:00+05:30",
        "visibility": "visible",
        "presence": "physical",
        "location": "in the hands",
        "description": "a black phone",
    }
    assert _model_tool_result(projected) == projected
    assert "answer" in result and "scene_context" in result["evidence"]["judgment"]
    assert (
        _model_tool_result({"kind": "history", "answer": "No result", "evidence": None})["answer"]
        == "No result"
    )


def test_visual_tool_projection_reports_recent_sightings_relatively():
    from datetime import UTC, datetime, timedelta

    from nyx.agent import _model_tool_result

    seen = (datetime.now(UTC) - timedelta(minutes=7)).isoformat()
    projected = _model_tool_result(
        {
            "kind": "snapshot",
            "status": "seen",
            "identity_verified": False,
            "captured_at": seen,
            "judgment": {"visibility": "visible", "location": "in your hand"},
            "scope": {"note": "The model can be wrong."},
        }
    )
    assert projected["seen_ago"] == "about 7 minutes ago"
    assert "identity_verified" not in projected and "scope" not in projected
