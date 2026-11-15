import importlib.util
from pathlib import Path


def test_native_policy_score_rejects_missing_wrong_and_forbidden_calls():
    spec = importlib.util.spec_from_file_location(
        "spoken_policy_cases",
        Path(__file__).resolve().parents[1] / "experiments/companion/spoken_policy_cases.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    case = {"tool": "search_statements", "arguments": {"selection": "latest_report"}}
    assert module.score(case, []) is False
    assert module.score(case, [{"name": "remember_statement", "arguments": {}}]) is False
    assert (
        module.score(case, [{"name": "search_statements", "arguments": {"selection": "all"}}])
        is False
    )
    assert (
        module.score(
            case,
            [
                {
                    "name": "search_statements",
                    "arguments": {"selection": "latest_report", "query": "glasses"},
                }
            ],
        )
        is True
    )
    assert module.score({"tool": None}, []) is True
    assert module.score({"tool": None}, [{"name": "departure_reminder", "arguments": {}}]) is False
