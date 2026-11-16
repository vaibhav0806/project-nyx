import json
from types import SimpleNamespace

import pytest
from PIL import Image

from nyx.reference import resolve_reference


@pytest.fixture(autouse=True)
def separated_candidate(monkeypatch):
    monkeypatch.setenv("NYX_HOUSEHOLD_REFERENCE_POLICY", "separated")


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
    def generate(*args, **kwargs):
        if "unique_referent" in kwargs.get("schema", {}).get("properties", {}):
            return json.dumps(
                {"targets": "Fixture target", "unique_referent": True, "ambiguous": False}
            )
        return json.dumps(result)

    return SimpleNamespace(generate_json=generate)


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


def test_report_claim_and_visual_identity_resolve_independently():
    calls = []

    def generate(messages, *args, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            assert all(
                part.get("type") != "image"
                for message in messages
                if isinstance(message["content"], list)
                for part in message["content"]
            )
            return json.dumps({"kind": "reported_placement", "destination": "drawer"})
        if len(calls) == 3:
            return json.dumps(
                {"targets": "Fixture target", "unique_referent": True, "ambiguous": False}
            )
        return json.dumps(decision(kind="none", destination=""))

    result = resolve_reference(
        SimpleNamespace(generate_json=generate),
        "I put this in the drawer.",
        [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
        placement=True,
    )
    assert result["status"] == "resolved"
    assert result["kind"] == "reported_placement" and result["destination"] == "drawer"
    assert result["object_description"] == "black phone"
    assert len(calls) == 3


def test_refused_claim_does_not_resolve_or_upload_visual_identity():
    calls = []

    def generate(messages, *args, **kwargs):
        calls.append(messages)
        assert len(calls) == 1
        assert all(
            part.get("type") != "image"
            for message in messages
            if isinstance(message["content"], list)
            for part in message["content"]
        )
        return json.dumps({"kind": "none", "destination": ""})

    result = resolve_reference(
        SimpleNamespace(generate_json=generate),
        "I did not put this in the drawer.",
        [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
        placement=True,
    )
    assert result["status"] == "clarify"


def test_independent_ambiguity_check_can_withhold_an_apparently_resolved_target():
    calls = []

    def generate(messages, *args, **kwargs):
        calls.append(kwargs.get("schema", {}))
        if len(calls) == 1:
            return json.dumps({"kind": "reported_placement", "destination": "drawer"})
        if len(calls) == 2:
            return json.dumps(decision(kind="none", destination=""))
        return json.dumps(
            {
                "targets": "Two plausible objects are shown equally.",
                "unique_referent": False,
                "ambiguous": True,
            }
        )

    result = resolve_reference(
        SimpleNamespace(generate_json=generate),
        "I put this in the drawer.",
        [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
        placement=True,
    )
    assert result["status"] == "clarify"
    assert len(calls) == 3


@pytest.mark.parametrize("unique,ambiguous", [(True, True), (False, False)])
def test_visual_reference_requires_unambiguous_agreement(unique, ambiguous):
    def generate(*args, **kwargs):
        if "unique_referent" in kwargs.get("schema", {}).get("properties", {}):
            return json.dumps(
                {"targets": "Possible targets.", "unique_referent": unique, "ambiguous": ambiguous}
            )
        return json.dumps(decision())

    result = resolve_reference(
        SimpleNamespace(generate_json=generate),
        "I put this in the kitchen.",
        [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
        placement=True,
    )
    assert result["status"] == "clarify"


@pytest.mark.parametrize(
    "check",
    [
        None,
        {},
        {"targets": "phone", "unique_referent": "true", "ambiguous": False},
        {"targets": "", "unique_referent": True, "ambiguous": False},
    ],
)
def test_malformed_visual_check_cannot_resolve_identity(check):
    def generate(*args, **kwargs):
        if "unique_referent" in kwargs.get("schema", {}).get("properties", {}):
            return json.dumps(check)
        return json.dumps(decision())

    with pytest.raises(ValueError, match="Invalid visual reference check"):
        resolve_reference(
            SimpleNamespace(generate_json=generate),
            "Where did I put this?",
            [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
        )


def test_identity_stage_requests_only_identity_not_a_second_placement_decision():
    calls = []

    def generate(messages, *args, **kwargs):
        fields = set(kwargs["schema"]["properties"])
        calls.append(fields)
        if fields == {"kind", "destination"}:
            return '{"kind":"reported_placement","destination":"drawer"}'
        if "unique_referent" in fields:
            return '{"targets":"phone","unique_referent":true,"ambiguous":false}'
        assert fields == {"object_description", "source", "frame_index", "ambiguous"}
        return '{"object_description":"phone","source":"visual","frame_index":0,"ambiguous":false}'

    result = resolve_reference(
        SimpleNamespace(generate_json=generate),
        "I put this in the drawer.",
        [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
        placement=True,
    )
    assert result["status"] == "resolved"
    assert result["kind"] == "reported_placement" and result["destination"] == "drawer"
    assert len(calls) == 3


def test_identity_lookup_cannot_invent_a_placement_claim():
    result = resolve_reference(
        verifier(decision(kind="reported_placement", destination="invented location")),
        "Which item am I showing?",
        [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
    )
    assert result["status"] == "resolved"
    assert result["kind"] == "none" and result["destination"] == ""
    assert "claim_source" not in result


def test_identity_handoff_without_the_independent_check_is_refused():
    identity = decision(kind="none", destination="")
    result = resolve_reference(
        verifier(decision(kind="reported_placement", destination="drawer")),
        "I put this in the drawer.",
        [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
        placement=True,
        identity=identity,
    )
    assert result["status"] == "clarify"


def test_default_joint_policy_does_not_promote_a_refused_placement(monkeypatch):
    monkeypatch.delenv("NYX_HOUSEHOLD_REFERENCE_POLICY", raising=False)
    calls = []

    def generate(*args, **kwargs):
        fields = set(kwargs["schema"]["properties"])
        calls.append(fields)
        assert "kind" in fields and "object_description" in fields
        return json.dumps(decision(kind="none", destination=""))

    result = resolve_reference(
        SimpleNamespace(generate_json=generate),
        "I put this in the drawer.",
        [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
        placement=True,
        identity={
            **decision(),
            "visual_identity_check": {"unique_referent": True, "ambiguous": False},
        },
    )
    assert result["status"] == "clarify"
    assert len(calls) == 1


def test_default_joint_policy_requires_the_independent_check(monkeypatch):
    monkeypatch.delenv("NYX_HOUSEHOLD_REFERENCE_POLICY", raising=False)
    calls = []

    def generate(*args, **kwargs):
        fields = set(kwargs["schema"]["properties"])
        calls.append(fields)
        if "unique_referent" in fields:
            return '{"targets":"two phones","unique_referent":false,"ambiguous":true}'
        assert "kind" in fields and "object_description" in fields
        return json.dumps(decision(kind="reported_placement", destination="drawer"))

    result = resolve_reference(
        SimpleNamespace(generate_json=generate),
        "I put this in the drawer.",
        [{"image": Image.new("RGB", (10, 10)), "captured_at": "now"}],
        placement=True,
    )
    assert result["status"] == "clarify"
    assert len(calls) == 2


def test_invalid_household_policy_fails_before_inference(monkeypatch):
    monkeypatch.setenv("NYX_HOUSEHOLD_REFERENCE_POLICY", "unknown")
    with pytest.raises(ValueError, match="must be joint or separated"):
        resolve_reference(SimpleNamespace(), "I put this in the drawer.", [], placement=True)
