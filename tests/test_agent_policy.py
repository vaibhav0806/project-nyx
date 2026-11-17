from nyx.agent_policy import AGENT_INSTRUCTIONS, AGENT_MODEL, VISION_MODEL


def test_voice_uses_shared_policy_and_approved_model():
    from nyx import realtime

    assert realtime.INSTRUCTIONS is AGENT_INSTRUCTIONS
    assert realtime.AGENT_MODEL == AGENT_MODEL == "openai/gpt-6-luna"
    assert VISION_MODEL == "google/gemini-3.5-flash-lite"


def test_shared_policy_is_short_and_keeps_personality_and_evidence_distinctions():
    assert len(AGENT_INSTRUCTIONS.split()) <= 100
    assert "warm" in AGENT_INSTRUCTIONS
    assert "English" in AGENT_INSTRUCTIONS and "Hindi" in AGENT_INSTRUCTIONS
    assert "reports, plans and observations" in AGENT_INSTRUCTIONS
    assert "supersedes_turn_id" not in AGENT_INSTRUCTIONS
    assert "departure" not in AGENT_INSTRUCTIONS


def test_runtime_model_defaults_use_the_shared_role_configuration(monkeypatch):
    from nyx.verification import CloudVerifier

    monkeypatch.delenv("NYX_AGENT_MODEL", raising=False)
    monkeypatch.delenv("NYX_VISION_MODEL", raising=False)
    verifier = CloudVerifier(client=object())
    assert verifier.model == AGENT_MODEL and verifier.vision_model == VISION_MODEL
