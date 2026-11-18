import importlib.util
from pathlib import Path


def test_native_replay_checks_actual_dispatch_not_just_integer_shape(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location(
        "native_voice", root / "experiments/companion/native_voice.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for hours, expected in [(48, False), (240, True)]:
        result = module.dispatch(
            tmp_path / str(hours),
            "Where did you last see my phone?",
            [
                {
                    "name": "look_for_object",
                    "arguments": {"query": "phone", "history": True, "hours": hours},
                }
            ],
        )
        assert result[0]["valid"] is expected


def test_native_arguments_keep_valid_sdk_positional_binding(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location(
        "native_voice", root / "experiments/companion/native_voice.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tool = module.schemas(tmp_path)["tools"]["look_for_object"]
    arguments = module.bind_call(tool, '{"query":"phone","history":true,"hours":240}')
    assert arguments["query"] == "phone" and arguments["hours"] == 240


def test_continuation_requesting_another_tool_is_not_a_finished_workflow(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location(
        "spoken_fresh_evidence", root / "experiments/companion/spoken_fresh_evidence.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (
        module.continuation_status(
            {"message": {"tool_calls": [{"function": {"name": "search_statements"}}]}}
        )
        == "awaiting_tools"
    )
    assert (
        module.continuation_status({"message": {"content": "Possible match yesterday."}})
        == "complete"
    )
    assert module.continuation_status({"message": {"content": None}}) == "failed"
