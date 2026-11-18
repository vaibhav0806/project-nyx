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
