import json
from types import SimpleNamespace

import pytest
from PIL import Image

from nyx.reference import REFERENCE_INSTRUCTIONS, resolve_reference


def decision(**changes):
    return {"object_description": "black phone", "frame_index": 0, "ambiguous": False, **changes}


def verifier(result, calls):
    def generate(messages, *args, **kwargs):
        calls.append(messages)
        assert messages[0]["content"] == REFERENCE_INSTRUCTIONS
        assert set(kwargs["schema"]["required"]) == set(decision())
        return json.dumps(result)

    return SimpleNamespace(generate_json=generate)


def test_one_visual_call_selects_earlier_supporting_frame_without_classifying_memory():
    frames = [
        {"image": Image.new("RGB", (10, 10), c), "captured_at": t}
        for c, t in [("red", "earlier"), ("black", "later")]
    ]
    calls = []
    result = resolve_reference(verifier(decision(), calls), "I'll keep this in the kitchen", frames)
    assert result["status"] == "resolved" and result["frame_index"] == 0
    assert result["captured_at"] == "earlier" and len(calls) == 1
    assert "kind" not in result and "destination" not in result


@pytest.mark.parametrize(
    "changes",
    [
        {"object_description": ""},
        {"frame_index": 10},
        {"frame_index": True},
        {"frame_index": -1},
        {"ambiguous": True},
        {"ambiguous": "false"},
        {"object_description": "x" * 161},
        {"extra": "invented"},
    ],
)
def test_unsupported_reference_protocol_requires_clarification(changes):
    frames = [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}]
    calls = []
    result = resolve_reference(
        verifier(decision(**changes), calls), "Where did I put this?", frames
    )
    assert result["status"] == "clarify" and len(calls) == 1


def test_missing_visual_window_never_infers_a_shown_object_from_destination():
    result = resolve_reference(SimpleNamespace(), "I'll put this in my wardrobe", [])
    assert result["status"] == "clarify"
