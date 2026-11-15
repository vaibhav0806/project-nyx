import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "visual_cases", Path(__file__).resolve().parents[1] / "experiments/companion/visual_cases.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
build_cases, score = module.build_cases, module.score


def test_cases_freeze_counts_and_keep_one_source_in_one_split():
    records = [
        {"id": 1, "category": 44, "split": "development", "sha256": "a", "file_name": "one.jpg"},
        {"id": 2, "category": 75, "split": "holdout", "sha256": "b", "file_name": "two.jpg"},
    ]
    annotations = [
        {"image_id": 1, "category_id": 44},
        {"image_id": 1, "category_id": 44},
        {"image_id": 2, "category_id": 75},
    ]
    cases = build_cases(records, annotations)
    assert len(cases) == 4
    assert [c["expected"] for c in cases] == ["ambiguous", "absent", "single", "absent"]
    assert len({c["id"] for c in cases}) == 4
    with pytest.raises(ValueError, match="source"):
        build_cases(records + [{**records[0], "split": "holdout"}], annotations)


@pytest.mark.parametrize(
    "expected,judgment,correct,unsafe",
    [
        ("single", {"visibility": "visible", "location": "desk"}, True, False),
        ("single", {"visibility": "uncertain"}, False, False),
        ("absent", {"visibility": "visible", "location": "desk"}, False, True),
        ("absent", {"visibility": "not_visible"}, True, False),
        ("ambiguous", {"visibility": "visible", "location": "desk"}, False, True),
        ("ambiguous", {"visibility": "uncertain", "ambiguous": True}, True, False),
        ("ambiguous", {"visibility": "not_visible"}, False, False),
    ],
)
def test_proxy_scoring_keeps_misses_separate_from_unsafe_positives(
    expected, judgment, correct, unsafe
):
    assert score(expected, judgment) == {"correct": correct, "unsafe_positive": unsafe}


def test_failure_cannot_pass_as_an_abstention():
    assert score("absent", None) == {"correct": False, "unsafe_positive": False}
    assert score("single", {"visibility": "visible", "location": None})["correct"] is False
