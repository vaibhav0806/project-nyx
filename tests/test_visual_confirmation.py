import json

import pytest
from PIL import Image

from nyx.cloud import CloudError
from nyx.verification import CloudVerifier


def primary(visibility="visible"):
    return json.dumps(
        {
            "visibility": visibility,
            "location": "on the round table" if visibility == "visible" else "",
            "description": "A bottle or soda container is on the table.",
            "matching_count": 1 if visibility == "visible" else 0,
            "ambiguous": False,
        }
    )


@pytest.mark.parametrize(
    "confirmation",
    [
        {"supported": False, "ambiguous": False, "reason": "The table has a can, not a bottle."},
        {"supported": True, "ambiguous": True, "reason": "The container shape is unclear."},
        {"supported": "true", "ambiguous": False, "reason": "Wrong type."},
        {"supported": True, "ambiguous": False},
        [],
    ],
)
def test_unconfirmed_positive_cannot_supply_a_location(monkeypatch, confirmation):
    monkeypatch.setenv("NYX_VISUAL_CONFIRMATION", "1")

    class Client:
        def generate(self, messages, model, max_tokens, **kwargs):
            if not kwargs.get("schema"):
                return primary()
            context = {
                "scene_description": "A room with a table and a container.",
                "target_context": "physical",
                "matches_requested_context": True,
            }
            return json.dumps(
                {**context, **confirmation} if isinstance(confirmation, dict) else confirmation
            )

    result = CloudVerifier(Client()).inspect(Image.new("RGB", (10, 10)), "a bottle")
    assert result["visibility"] == "uncertain"
    assert result["location"] is None
    assert result["confirmation_requests"] == 1


def test_supported_positive_preserves_location_and_uses_existing_reference_model(monkeypatch):
    monkeypatch.setenv("NYX_VISUAL_CONFIRMATION", "1")
    monkeypatch.setenv("NYX_REFERENCE_MODEL", "existing-reference")
    calls = []

    class Client:
        def generate(self, messages, model, max_tokens, **kwargs):
            calls.append((messages, model, kwargs))
            return (
                json.dumps(
                    {
                        "scene_description": "A bottle on a table.",
                        "target_context": "physical",
                        "matches_requested_context": True,
                        "supported": True,
                        "ambiguous": False,
                        "reason": "Bottle shape visible.",
                    }
                )
                if kwargs.get("schema")
                else primary()
            )

    result = CloudVerifier(Client()).inspect(Image.new("RGB", (10, 10)), "a bottle")
    assert result["visibility"] == "visible"
    assert result["location"] == "on the round table"
    assert calls[1][1] == "existing-reference"
    assert calls[1][2]["schema"]["additionalProperties"] is False
    assert result["confirmation_requests"] == 1


def test_confirmation_outage_propagates_without_reusing_positive(monkeypatch):
    monkeypatch.setenv("NYX_VISUAL_CONFIRMATION", "1")

    class Client:
        def generate(self, messages, model, max_tokens, **kwargs):
            if kwargs.get("schema"):
                raise CloudError("offline")
            return primary()

    with pytest.raises(CloudError, match="offline"):
        CloudVerifier(Client()).inspect(Image.new("RGB", (10, 10)), "a bottle")


def test_negative_inspection_needs_no_confirmation(monkeypatch):
    monkeypatch.setenv("NYX_VISUAL_CONFIRMATION", "1")
    calls = []

    class Client:
        def generate(self, messages, model, max_tokens, **kwargs):
            calls.append(model)
            return primary("not_visible")

    result = CloudVerifier(Client()).inspect(Image.new("RGB", (10, 10)), "a bottle")
    assert result["visibility"] == "not_visible"
    assert len(calls) == 1


def test_confirmation_stays_opt_in_after_mixed_replay(monkeypatch):
    monkeypatch.delenv("NYX_VISUAL_CONFIRMATION", raising=False)

    class Client:
        def generate(self, messages, model, max_tokens):
            return primary()

    verifier = CloudVerifier(Client())
    assert verifier.fingerprint["positive_confirmation"] == "off"
    assert verifier.inspect(Image.new("RGB", (10, 10)), "a bottle")["visibility"] == "visible"


def test_corroboration_accepts_a_supported_physical_scene_context(monkeypatch):
    monkeypatch.setenv("NYX_VISUAL_CONFIRMATION", "1")

    class Client:
        def generate(self, messages, model, max_tokens, **kwargs):
            return (
                json.dumps(
                    {
                        "scene_description": "A room with a table and a bottle.",
                        "target_context": "physical",
                        "matches_requested_context": True,
                        "supported": True,
                        "ambiguous": False,
                        "reason": "The bottle is on the actual table.",
                    }
                )
                if kwargs.get("schema")
                else primary()
            )

    result = CloudVerifier(Client()).inspect(Image.new("RGB", (10, 10)), "a bottle")
    assert result["visibility"] == "visible" and result["target_context"] == "physical"


def test_reference_candidate_also_withholds_an_embedded_depiction(monkeypatch):
    monkeypatch.setenv("NYX_VISUAL_CONFIRMATION", "1")

    class Client:
        def generate(self, messages, model, max_tokens, **kwargs):
            return (
                json.dumps(
                    {
                        "scene_description": "A framed photograph showing a bottle.",
                        "target_context": "depicted",
                        "matches_requested_context": False,
                        "supported": False,
                        "ambiguous": False,
                        "reason": "The item is only inside the photograph.",
                    }
                )
                if kwargs.get("schema")
                else primary()
            )

    result = CloudVerifier(Client()).inspect_reference(
        Image.new("RGB", (10, 10)), Image.new("RGB", (10, 10)), "a bottle"
    )
    assert result["visibility"] == "uncertain" and result["location"] is None


@pytest.mark.parametrize("context, matches", [("unclear", True), ("depicted", False), ([], True)])
def test_context_cannot_be_overridden_by_a_supported_boolean(monkeypatch, context, matches):
    monkeypatch.setenv("NYX_VISUAL_CONFIRMATION", "1")

    class Client:
        def generate(self, messages, model, max_tokens, **kwargs):
            if not kwargs.get("schema"):
                return primary()
            return json.dumps(
                {
                    "scene_description": "A displayed image includes a bottle.",
                    "target_context": context,
                    "matches_requested_context": matches,
                    "supported": True,
                    "ambiguous": False,
                    "reason": "The inner photograph has a bottle.",
                }
            )

    result = CloudVerifier(Client()).inspect(Image.new("RGB", (10, 10)), "a bottle")
    assert result["visibility"] == "uncertain" and result["location"] is None
