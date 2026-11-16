import pytest


def test_freshness_has_explicit_half_life_and_does_not_replace_relevance():
    from nyx.memory_policy import memory_priority

    result = memory_priority(
        0.8,
        "2026-11-08T12:00:00Z",
        now="2026-11-15T12:00:00Z",
        half_life_days=7,
        recency_weight=0.5,
    )
    assert result["freshness"] == pytest.approx(0.5)
    assert result["priority"] == pytest.approx(1.0)
    irrelevant = memory_priority(
        0, "2026-11-15T12:00:00Z", now="2026-11-15T12:00:00Z", recency_weight=1
    )
    assert irrelevant["priority"] == 0


@pytest.mark.parametrize("intent", ["historical", "last_seen", "reported"])
def test_noncurrent_queries_disable_recency_weight(intent):
    from nyx.memory_policy import memory_priority

    result = memory_priority(
        0.8, "2026-11-06T12:00:00Z", now="2026-11-15T12:00:00Z", recency_weight=1, intent=intent
    )
    assert result["priority"] == 0.8 and result["eligible"]


def test_unknown_and_future_times_are_not_promoted_to_new_evidence():
    from nyx.memory_policy import memory_priority

    unknown = memory_priority(0.7, None, now="2026-11-15T12:00:00Z", recency_weight=1)
    assert unknown["freshness"] is None and unknown["priority"] == 0.7
    future = memory_priority(
        0.9, "2026-11-16T12:00:00Z", now="2026-11-15T12:00:00Z", recency_weight=1
    )
    assert future["eligible"] is False and future["priority"] is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"half_life_days": 0},
        {"recency_weight": -1},
        {"recency_weight": 2},
        {"half_life_days": float("nan")},
    ],
)
def test_invalid_policy_parameters_are_rejected(kwargs):
    from nyx.memory_policy import memory_priority

    with pytest.raises(ValueError):
        memory_priority(0.5, None, now="2026-11-15T12:00:00Z", **kwargs)
