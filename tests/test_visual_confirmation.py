"""A visual task is one observation, without a second AI judge."""

import json

import pytest
from PIL import Image

from nyx.verification import PROMPT, CloudVerifier


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
            assert PROMPT in messages[0]["content"][-1]["text"]
            return json.dumps(
                {
                    "visibility": visibility,
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
