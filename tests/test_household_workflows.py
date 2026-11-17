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
        "observations": [{"kind": "memories", "matches": [{"turn_id": "old"}]}],
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
            "kind": "report",
            "visual": {"status": "resolved"},
        }
    ]
    assert not module.score_setup(case, ["first", "second"], linked, [])
    linked.insert(
        0,
        {
            "turn_id": "first",
            "kind": "report",
            "visual": {"status": "resolved"},
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


def test_native_replay_uses_authenticated_owned_turn_and_existing_api(tmp_path):
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient
    from PIL import Image
    from test_companion import Planner
    from test_nyx import ColorEncoder

    from nyx.app import create_app
    from nyx.voice import Voice

    speaker = Voice(tmp_path, object())
    encoder, verifier = ColorEncoder(), Planner()
    with TestClient(
        create_app(
            tmp_path,
            encoder_factory=lambda: encoder,
            verifier_factory=lambda: verifier,
            voice_factory=lambda _: speaker,
        )
    ) as client:
        headers = {"x-nyx-voice": client.post("/api/voice/session").json()["token"]}
        text = "Hello"
        identifier = speaker.conversations.begin(text, {"mode": "livekit"})
        speaker.turn = {"id": identifier, "transcript": text}
        job = module.request_turn(
            tmp_path,
            encoder,
            verifier,
            text,
            [Image.new("RGB", (40, 40), "green")],
            initial_action={"action": "chat", "message": "Hello"},
            client=client,
            voice_turn_id=identifier,
            headers=headers,
            context_at=datetime.now(UTC).isoformat(),
        )
        assert job["status"] == "succeeded"
        assert job["result"]["voice_turn_id"] == identifier
        assert job["result"]["turn_id"] == identifier
