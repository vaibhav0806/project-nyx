import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def workflow(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location(
        "recall_workflows", root / "experiments/companion/recall_workflows.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(identifier="recall", split="development", text="My phone is in the bag"):
    return {
        "id": identifier,
        "split": split,
        "group": identifier,
        "reports": [{"id": "claim", "text": text, "days_ago": 2}],
        "query": "What did I say about my phone?",
        "expected_reports": ["claim"],
    }


def test_manifest_rejects_source_leakage_and_invalid_report_references(workflow):
    with pytest.raises(ValueError, match="leakage"):
        workflow.validate_cases([case(), case("other", "holdout")])
    invalid = case()
    invalid["expected_reports"] = ["invented"]
    with pytest.raises(ValueError, match="report"):
        workflow.validate_cases([invalid])


def test_workflow_identity_cannot_escape_artifact_directory(workflow):
    with pytest.raises(ValueError, match="identity"):
        workflow.validate_cases([case("../../outside")])


def test_scoring_requires_exact_direct_reports_and_attributed_sources(workflow):
    score_answer = workflow.score_answer
    result = {
        "status": "complete",
        "answer": "You said your phone is in the bag.",
        "observations": [{"kind": "statements", "matches": [{"turn_id": "saved"}]}],
        "sources": ["transcript:saved", "transcript:prior-correction-source"],
    }
    assert score_answer(case(), result, {"claim": "saved"})["correct"]
    result["observations"][0]["matches"].append({"turn_id": "unrelated"})
    assert not score_answer(case(), result, {"claim": "saved"})["correct"]
    result["observations"][0]["matches"].pop()
    result["sources"] = []
    assert not score_answer(case(), result, {"claim": "saved"})["correct"]


def test_failed_or_uncited_positive_outputs_cannot_pass(workflow):
    score_answer = workflow.score_answer
    assert not score_answer(case(), None, {"claim": "saved"})["correct"]
    assert not score_answer(
        case(), {"status": "chat", "answer": "It is in the bag."}, {"claim": "saved"}
    )["correct"]


def test_negative_requires_abstention_or_an_empty_checked_statement_lookup(workflow):
    score_answer = workflow.score_answer
    negative = case()
    negative["expected_reports"] = []
    assert score_answer(negative, {"status": "clarify", "answer": "Which object?"}, {})["correct"]
    assert not score_answer(negative, {"status": "chat", "answer": "It is in the bag."}, {})[
        "correct"
    ]
    checked = {
        "status": "complete",
        "answer": "No relevant saved statement.",
        "observations": [{"kind": "statements", "matches": []}],
    }
    assert score_answer(negative, checked, {})["correct"]
