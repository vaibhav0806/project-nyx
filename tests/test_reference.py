import json
from types import SimpleNamespace

import pytest
from PIL import Image

from nyx.reference import resolve_reference


def decision(**changes):
    return {
        "object_description": "black phone",
        "destination": "kitchen",
        "kind": "intention",
        "source": "visual",
        "frame_index": 0,
        "ambiguous": False,
        **changes,
    }


def verifier(result):
    return SimpleNamespace(generate_json=lambda *a, **k: json.dumps(result))


def test_reference_selects_earlier_supporting_frame():
    frames = [
        {"image": Image.new("RGB", (10, 10), c), "captured_at": t}
        for c, t in [("red", "earlier"), ("black", "later")]
    ]
    result = resolve_reference(
        verifier(decision()), "I'll keep this in the kitchen", frames, placement=True
    )
    assert result["status"] == "resolved"
    assert result["frame_index"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"object_description": "this"},
        {"object_description": "kitchen"},
        {"frame_index": 10},
        {"frame_index": True},
        {"ambiguous": True},
        {"source": "unresolved"},
        {"destination": "invented room"},
        {"object_description": "kitchen", "source": "explicit_text", "frame_index": -1},
    ],
)
def test_unsupported_links_require_clarification(changes):
    frames = [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}]
    result = resolve_reference(
        verifier(decision(**changes)), "I'll keep this in the kitchen", frames, placement=True
    )
    assert result["status"] == "clarify"


def test_destination_cannot_be_explicit_object_without_visual_support():
    result = resolve_reference(
        verifier(
            decision(
                object_description="wardrobe",
                destination="my wardrobe",
                source="explicit_text",
                frame_index=-1,
            )
        ),
        "I'll put this in my wardrobe",
        [],
        placement=True,
    )
    assert result["status"] == "clarify"


def test_explicit_named_object_needs_no_visual_claim():
    result = resolve_reference(
        verifier(decision(object_description="phone", source="explicit_text", frame_index=-1)),
        "I'll keep my phone in the kitchen",
        [],
        placement=True,
    )
    assert result["status"] == "resolved"


@pytest.mark.parametrize(
    "object_name,spoken_name", [("phone", "microphone"), ("keys", "monkeys"), ("cup", "cupboard")]
)
def test_explicit_object_cannot_be_a_fragment_of_a_different_word(object_name, spoken_name):
    result = resolve_reference(
        verifier(
            decision(
                object_description=object_name,
                destination="desk",
                source="explicit_text",
                frame_index=-1,
            )
        ),
        f"I will put my {spoken_name} on the desk",
        [],
        placement=True,
    )
    assert result["status"] == "clarify"


@pytest.mark.parametrize(
    "object_name,text",
    [
        ("black phone", "I'll put my BLACK PHONE, on the desk."),
        ("चाबी", "मैं अपनी चाबी desk पर रखूँगी।"),
    ],
)
def test_complete_explicit_phrases_remain_supported(object_name, text):
    result = resolve_reference(
        verifier(
            decision(
                object_description=object_name,
                destination="desk",
                source="explicit_text",
                frame_index=-1,
            )
        ),
        text,
        [],
        placement=True,
    )
    assert result["status"] == "resolved"


@pytest.mark.parametrize(
    "text,object_name,destination",
    [
        ("In the kitchen, I will keep my phone.", "phone", "kitchen"),
        ("दराज में मैं अपना चश्मा रखूँगी।", "चश्मा", "दराज"),
        ("I'm in the kitchen. My phone will stay in the kitchen.", "phone", "kitchen"),
    ],
)
def test_explicit_object_can_follow_the_destination(text, object_name, destination):
    result = resolve_reference(
        verifier(
            decision(
                object_description=object_name,
                destination=destination,
                source="explicit_text",
                frame_index=-1,
            )
        ),
        text,
        [],
        placement=True,
    )
    assert result["status"] == "resolved"
