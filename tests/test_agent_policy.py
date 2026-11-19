from nyx.agent_policy import (
    AGENT_INSTRUCTIONS,
    AGENT_MODEL,
    AGENT_REASONING_EFFORT,
    VISION_MODEL,
    VOICE_REASONING_EFFORT,
)


def test_voice_uses_shared_policy_and_approved_model():
    from nyx import realtime

    assert realtime.INSTRUCTIONS is AGENT_INSTRUCTIONS
    assert realtime.AGENT_MODEL == AGENT_MODEL == "openai/gpt-6-luna"
    assert VISION_MODEL == "google/gemini-3.5-flash-lite"
    assert AGENT_REASONING_EFFORT == "medium"
    assert realtime.VOICE_REASONING_EFFORT == VOICE_REASONING_EFFORT == "low"
    assert realtime.VOICE_PROVIDER_ORDER == ["openai/fast"]


def test_shared_policy_keeps_personality_and_evidence_distinctions():
    assert "demo" not in AGENT_INSTRUCTIONS.lower()
    assert "warm" in AGENT_INSTRUCTIONS
    assert "English" in AGENT_INSTRUCTIONS and "Hindi" in AGENT_INSTRUCTIONS
    assert "Describe past observations as past observations" in AGENT_INSTRUCTIONS
    assert "supersedes_turn_id" not in AGENT_INSTRUCTIONS
    assert "departure" not in AGENT_INSTRUCTIONS


def test_runtime_model_defaults_use_the_shared_role_configuration(monkeypatch):
    from nyx.verification import CloudVerifier

    monkeypatch.delenv("NYX_AGENT_MODEL", raising=False)
    monkeypatch.delenv("NYX_VISION_MODEL", raising=False)
    verifier = CloudVerifier(client=object())
    assert verifier.model == AGENT_MODEL and verifier.vision_model == VISION_MODEL
    assert verifier.fingerprint["agent_reasoning_effort"] == AGENT_REASONING_EFFORT
