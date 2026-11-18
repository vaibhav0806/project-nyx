"""A visual task is one observation, without a second AI judge."""

import json

import pytest
from PIL import Image

from nyx.verification import PROMPT, CloudVerifier


@pytest.mark.parametrize(
    "presence,count,ambiguous,expected",
    [
        ("physical", 1, False, "visible"),
        ("depicted", 1, False, "not_visible"),
        ("absent", 0, False, "not_visible"),
        ("physical", 2, False, "uncertain"),
        ("physical", 1, True, "uncertain"),
    ],
)
def test_ordinary_inspection_distinguishes_scene_presence_from_depicted_visibility(
    presence, count, ambiguous, expected
):
    calls = []

    class Client:
        def generate(self, *args, **kwargs):
            calls.append(args)
            return json.dumps(
                {
                    "scene_context": "An observed scene",
                    "presence": presence,
                    "description": "Object evidence",
                    "matching_count": count,
                    "ambiguous": ambiguous,
                    "location": "by the table",
                }
            )

    result = CloudVerifier(Client()).inspect(Image.new("RGB", (10, 10)), "an object")
    assert len(calls) == 1
    assert result["visibility"] == expected
    if expected != "visible":
        assert result["location"] is None


@pytest.mark.parametrize("with_reference", [False, True])
@pytest.mark.parametrize("wrapped", [False, True])
def test_inspection_wire_requires_one_object_and_never_unwraps_a_model_array(
    with_reference, wrapped
):
    from io import BytesIO

    from nyx.cloud import OpenRouter

    observed = {
        "visibility": "visible",
        "location": "on the table",
        "description": "An object",
        "matching_count": 1,
        "ambiguous": False,
    }
    if not with_reference:
        observed.pop("visibility")
        observed.update(scene_context="A physical room with a table", presence="physical")
    calls = []

    def transport(request, timeout):
        body = json.loads(request.data)
        calls.append(body)
        shape = body["response_format"]
        assert shape["type"] == "json_schema"
        assert shape["json_schema"]["strict"] is True
        schema = shape["json_schema"]["schema"]
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        assert set(schema["required"]) == set(observed)
        raw = json.dumps([observed] if wrapped else observed)
        return BytesIO(
            json.dumps(
                {"choices": [{"finish_reason": "stop", "message": {"content": raw}}]}
            ).encode()
        )

    verifier = CloudVerifier(OpenRouter(key="offline-fixture", transport=transport))
    image = Image.new("RGB", (10, 10))
    result = (
        verifier.inspect_reference(image, image, "an object")
        if with_reference
        else verifier.inspect(image, "an object")
    )
    assert len(calls) == 1
    assert result["visibility"] == ("uncertain" if wrapped else "visible")


@pytest.mark.parametrize(
    "visibility,count,ambiguous,expected",
    [
        ("visible", 1, False, "visible"),
        ("visible", 2, False, "uncertain"),
        ("visible", 1, True, "uncertain"),
        ("not_visible", 0, False, "not_visible"),
        ("uncertain", 0, False, "uncertain"),
    ],
)
def test_one_inspection_returns_only_supported_protocol_output(
    visibility, count, ambiguous, expected
):
    calls = []

    class Client:
        def generate(self, messages, model, max_tokens, **kwargs):
            calls.append((messages, model))
            assert messages[0] == {"role": "system", "content": PROMPT}
            return json.dumps(
                {
                    "scene_context": "An observed room",
                    "presence": {
                        "visible": "physical",
                        "not_visible": "absent",
                        "uncertain": "uncertain",
                    }[visibility],
                    "matching_count": count,
                    "ambiguous": ambiguous,
                    "description": "Observed candidate",
                    "location": "on the table" if visibility == "visible" else "",
                }
            )

    verifier = CloudVerifier(Client())
    result = verifier.inspect(Image.new("RGB", (10, 10)), "a bottle")
    assert result["visibility"] == expected and len(calls) == 1
    assert calls[0][1] == "google/gemini-3.5-flash-lite"
    if expected != "visible":
        assert result["location"] is None
    assert not hasattr(verifier, "confirm_positive")


def test_reference_candidate_uses_the_same_visual_model_once():
    calls = []

    class Client:
        def generate(self, messages, model, max_tokens, **kwargs):
            calls.append((messages, model))
            return '{"visibility":"uncertain","location":"","description":"Lookalikes cannot establish identity.","matching_count":2,"ambiguous":true}'

    verifier = CloudVerifier(Client())
    result = verifier.inspect_reference(
        Image.new("RGB", (10, 10)), Image.new("RGB", (10, 10)), "phone"
    )
    assert result["visibility"] == "uncertain"
    assert len(calls) == 1 and calls[0][1] == verifier.vision_model
