import importlib.util
from pathlib import Path

import pytest


def experiment():
    script = Path(__file__).resolve().parents[1] / "experiments/companion/embedding_replay.py"
    spec = importlib.util.spec_from_file_location("embedding_replay", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_benchmark_budget_counts_previous_spending_and_current_run():
    check = experiment().check_budget
    assert check({"usage": 1.16, "limit": 2}, 1.15, 0.15) > 0
    for snapshot in [
        {"usage": 1.99, "limit": 2},
        {"usage": 1.30, "limit": 2},
        {"usage": float("nan"), "limit": 2},
        {"limit": 2},
    ]:
        with pytest.raises(ValueError):
            check(snapshot, 1.15, 0.15)


def test_budget_guard_counts_response_cost_before_key_usage_settles():
    with pytest.raises(ValueError):
        experiment().check_budget({"usage": 1.15, "limit": 2}, 1.15, 0.15, reported_cost=0.14)


def test_authorized_eight_dollar_cap_keeps_settlement_headroom_and_lower_limits():
    check = experiment().check_budget
    assert check({"usage": 2.51, "limit": 5}, 2.50, 0.15) > 0
    with pytest.raises(ValueError):
        check({"usage": 7.91, "limit": 50}, 7.80, 0.25)
    with pytest.raises(ValueError):
        check({"usage": 1.99, "limit": 2}, 1.90, 0.25)


def test_embedding_metrics_count_negatives_without_inventing_a_confidence_threshold():
    module = experiment()
    rows = [{"id": 3}, {"id": 1}, {"id": 2}]
    assert module.score_candidates(rows, {1, 2})["recall_at_3"] == 1
    assert module.score_candidates(rows, {1, 2})["reciprocal_rank"] == 0.5
    negative = module.score_candidates(rows, set())
    assert negative["recall_at_3"] is None
    assert negative["positive"] is False


def test_reference_fusion_keeps_a_bounded_nomination_budget():
    from nyx.retrieval import merge_candidates

    for limit in [0, 101]:
        with pytest.raises(ValueError):
            merge_candidates([{"id": 1}], [], limit)
