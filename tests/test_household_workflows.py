import copy
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "household_workflows",
    Path(__file__).resolve().parents[1] / "experiments/companion/household_workflows.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_workflows_have_disjoint_sources_and_valid_report_labels():
    cases = json.loads(Path(module.__file__).with_suffix(".json").read_text())["cases"]
    assert len(module.validate_cases(cases)) == 8
    corrupt = copy.deepcopy(cases)
    corrupt[-1]["sources"] = [corrupt[0]["sources"][0]]
    with pytest.raises(ValueError, match="Source reuse"):
        module.validate_cases(corrupt)
    corrupt = copy.deepcopy(cases)
    corrupt[0]["expected_report"] = 9
    with pytest.raises(ValueError, match="expected report"):
        module.validate_cases(corrupt)


def test_workflow_recall_requires_exact_report_attribution_and_negative_evidence():
    result = {
        "answer": "You said the drawer.",
        "observations": [{"kind": "statements", "matches": [{"turn_id": "old"}]}],
        "sources": ["transcript:old"],
    }
    assert module.score_recall(result, ["old"])["correct"]
    assert not module.score_recall(result, ["new"])["correct"]
    result["sources"] = []
    assert not module.score_recall(result, ["old"])["correct"]
    assert not module.score_recall(None, [])["correct"]
    assert not module.score_recall({"answer": "I know.", "observations": []}, [])["correct"]
    assert module.score_recall({"answer": "Which item?", "status": "clarify"}, [])["correct"]


def test_complete_workflow_cannot_pass_when_an_earlier_save_was_lost():
    case = {"kind": "reported_placement", "expected_report": 1}
    linked = [
        {
            "turn_id": "second",
            "kind": "reported_placement",
            "resolver": {"reference": {"source": "visual"}},
        }
    ]
    assert not module.score_setup(case, ["first", "second"], linked, [])
    linked.insert(
        0,
        {
            "turn_id": "first",
            "kind": "reported_placement",
            "resolver": {"reference": {"source": "visual"}},
        },
    )
    assert module.score_setup(case, ["first", "second"], linked, [])
    case["correction"] = True
    assert not module.score_setup(case, ["first", "second"], linked, [])
    assert module.score_setup(
        case,
        ["first", "second"],
        linked,
        [{"previous_turn_id": "first", "replacement_turn_id": "second"}],
    )
