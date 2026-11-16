import importlib.util
from pathlib import Path

import pytest


def experiment():
    path = Path(__file__).resolve().parents[1] / "experiments/companion/runtime_replay.py"
    spec = importlib.util.spec_from_file_location("runtime_replay", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capacity_keeps_video_vector_and_thumbnail_requirements_separate():
    estimate = experiment().estimate_capacity(thumbnail_bytes=10000)
    assert estimate["nominal_video_bytes"] == 108000000000
    assert estimate["sample_floor_count"] == 432000
    assert estimate["raw_vector_bytes"] == 1327104000
    assert estimate["projected_thumbnail_bytes"] == 4320000000
    assert estimate["nominal_budget_hours"] == pytest.approx(2.3860929422)


def test_window_scoring_counts_missing_and_extra_sources_as_failures():
    score = experiment().score_window(["day-1", "day-9"], ["day-1", "future"])
    assert not score["correct"]
    assert score["missing"] == ["day-9"] and score["unexpected"] == ["future"]


@pytest.mark.parametrize(
    "kwargs", [{"days": 0}, {"bit_rate": float("nan")}, {"sample_seconds": -1}]
)
def test_invalid_capacity_parameters_cannot_generate_plausible_estimates(kwargs):
    with pytest.raises(ValueError):
        experiment().estimate_capacity(**kwargs)
