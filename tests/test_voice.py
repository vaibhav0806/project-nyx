import base64
import json
import time
from io import BytesIO
from typing import ClassVar

import numpy as np
import pytest

from nyx.voice import Conversations, Voice, VoiceError, wake_command


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Hey Nyx, where are my glasses?", "where are my glasses?"),
        ("Nix.", ""),
        ("Hey Nicks", ""),
        ("next question", None),
        ("I spoke to Nick yesterday", None),
        ("", None),
        ("a phoenix", None),
    ],
)
def test_wake_is_a_prefix_not_arbitrary_conversation(text, expected):
    assert wake_command(text) == expected


class Provider:
    def __init__(self):
        self.calls = []

    def transcribe(self, pcm):
        self.calls.append("stt")
        return "where are my glasses?"

    def route(self, transcript, context):
        self.calls.append(("route", context))
        return {
            "mode": "current",
            "object_query": "glasses",
            "seen_after": None,
            "seen_before": None,
        }

    def speak(self, text):
        self.calls.append(("tts", text))
        return base64.b64encode(b"RIFFtest").decode()


def audio():
    return (np.sin(np.arange(16000) / 20) * 3000).astype("<i2").tobytes()


def test_local_agent_voice_mode_does_not_call_cloud_intent_router(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda pcm: "Hey Nyx where are my glasses?", agent_mode=True)
    token = voice.start()["token"]
    turn = voice.utterance(token, audio())
    assert turn["plan"]["mode"] == "agent"
    assert provider.calls == ["stt"]


def test_idle_stays_local_wake_only_and_next_question(tmp_path):
    provider = Provider()
    heard = iter(["hello there", "Hey Nyx", "where are my glasses?"])
    voice = Voice(tmp_path, provider, lambda pcm: next(heard))
    token = voice.start()["token"]
    assert voice.utterance(token, audio())["state"] == "listening"
    assert not provider.calls
    assert voice.utterance(token, audio())["state"] == "activated"
    assert not provider.calls
    turn = voice.utterance(token, audio())
    assert turn["plan"]["mode"] == "current"
    assert provider.calls[0] == "stt"
    voice.cancel(token)
    with pytest.raises(VoiceError):
        voice.reply(token, turn["id"], {"answer": "stale"})
    assert not any(isinstance(x, tuple) and x[0] == "tts" for x in provider.calls)


def test_wake_question_same_utterance_exclusive_session_and_expiry(tmp_path):
    voice = Voice(tmp_path, Provider(), lambda pcm: "Hey Nyx where are my glasses?")
    token = voice.start()["token"]
    with pytest.raises(VoiceError):
        voice.start()
    turn = voice.utterance(token, audio())
    assert turn["plan"]["object_query"] == "glasses"
    voice.stop(token)
    with pytest.raises(VoiceError):
        voice.utterance(token, audio())
    assert voice.start()["token"] != token


def test_silence_size_limits_and_expired_name_never_reach_cloud(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda pcm: "hi there")
    token = voice.start()["token"]
    assert voice.utterance(token, b"\0" * 32000)["state"] == "listening"
    for invalid in [b"x", b"x" * (800001), b"xx"]:
        with pytest.raises(VoiceError):
            voice.utterance(token, invalid)
    voice.awake_until = time.monotonic() - 1
    assert voice.utterance(token, audio())["state"] == "listening"
    assert not provider.calls


def test_conversations_reopen_interrupt_and_invalidate_sources(tmp_path):
    db = Conversations(tmp_path)
    turn = db.begin("where?", {"mode": "latest", "object_query": "glasses"})
    db.finish(turn, "I saw glasses.", ["abc"])
    pending = db.begin("and now?", {"mode": "current", "object_query": "glasses"})
    reopened = Conversations(tmp_path)
    rows = reopened.recent()
    assert rows[0]["status"] == "complete"
    assert rows[1]["id"] == pending and rows[1]["status"] == "interrupted"
    reopened.invalidate("abc")
    assert reopened.recent()[0]["sources_available"] is False


@pytest.mark.parametrize(
    "plan",
    [
        {"mode": "delete", "object_query": "glasses"},
        {"mode": "current", "object_query": ""},
        {"mode": "latest", "object_query": "keys", "seen_after": "2026-10-19T12:00:00"},
        {"mode": "current", "object_query": "keys", "seen_after": "2026-10-19T12:00:00Z"},
        {
            "mode": "latest",
            "object_query": "keys",
            "seen_after": "2026-10-20T12:00:00Z",
            "seen_before": "2026-10-19T12:00:00Z",
        },
        {"mode": "latest", "object_query": "keys", "extra": "execute"},
    ],
)
def test_router_rejects_actions_and_ambiguous_times(plan):
    from nyx.voice import validate_plan

    with pytest.raises(VoiceError):
        validate_plan(plan)


def test_cancel_during_transcription_blocks_followup_cloud_work(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda pcm: "Hey Nyx, where are my glasses?")
    token = voice.start()["token"]

    def transcribe(pcm):
        voice.cancel(token)
        return "where are my glasses?"

    provider.transcribe = transcribe
    with pytest.raises(VoiceError):
        voice.utterance(token, audio())
    assert provider.calls == []


def test_voice_api_uses_existing_visual_result_and_persists(tmp_path):
    pytest.importorskip("fastapi")
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient
    from PIL import Image
    from test_nyx import ColorEncoder

    from nyx.app import create_app

    class Verifier:
        fingerprint: ClassVar = {"model": "fake-verifier"}

        def inspect(self, image, query):
            return {
                "visibility": "visible",
                "location": "beside the laptop",
                "description": "glasses",
                "ambiguous": False,
            }

    provider = Provider()
    service = Voice(tmp_path, provider, lambda pcm: "Hey Nyx where are my glasses?")
    factory = lambda root: service
    with TestClient(
        create_app(
            tmp_path, encoder_factory=ColorEncoder, verifier_factory=Verifier, voice_factory=factory
        )
    ) as client:
        assert client.get("/api/voice").json()["configured"] is True
        assert "test-secret" not in client.get("/api/voice").text
        assert (
            client.post(
                "/api/voice/session", headers={"origin": "https://evil.example"}
            ).status_code
            == 403
        )
        token = client.post("/api/voice/session").json()["token"]
        headers = {"x-nyx-voice": token}
        assert (
            client.post("/api/voice/utterance", headers=headers, content=b"x" * 800001).status_code
            == 413
        )
        turn = client.post("/api/voice/utterance", headers=headers, content=audio()).json()
        assert turn["state"] == "question"
        assert (
            client.post(
                "/api/voice/reply",
                headers=headers,
                json={"turn_id": turn["id"], "job_id": "invented"},
            ).status_code
            == 400
        )
        image = BytesIO()
        Image.new("RGB", (10, 10), "blue").save(image, format="PNG")
        response = client.post(
            "/api/inspect",
            params={"object_query": "glasses", "captured_at": datetime.now(UTC).isoformat()},
            content=image.getvalue(),
        )
        job_id = response.json()["id"]
        for _ in range(100):
            if client.get("/api/jobs/" + job_id).json()["status"] == "succeeded":
                break
            time.sleep(0.01)
        reply = client.post(
            "/api/voice/reply", headers=headers, json={"turn_id": turn["id"], "job_id": job_id}
        )
        assert reply.status_code == 200
        assert "beside the laptop" in reply.json()["answer"]
        assert client.get("/api/voice").json()["conversations"][-1]["status"] == "complete"
        assert (
            client.post(
                "/api/voice/reply", headers=headers, json={"turn_id": turn["id"], "job_id": job_id}
            ).status_code
            == 400
        )
        assert client.delete("/api/voice/session", headers=headers).status_code == 200
        assert (
            client.post("/api/voice/utterance", headers=headers, content=audio()).status_code == 400
        )
    assert Conversations(tmp_path).recent()[0]["status"] == "complete"


def test_cancel_during_speech_discards_audio_and_does_not_complete_turn(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda pcm: "Hey Nyx where are my glasses?")
    token = voice.start()["token"]
    turn = voice.utterance(token, audio())

    def speak(text):
        voice.cancel(token)
        return base64.b64encode(b"RIFFtest").decode()

    provider.speak = speak
    with pytest.raises(VoiceError):
        voice.reply(token, turn["id"], {"answer": "Glasses are here."})
    assert voice.conversations.recent()[-1]["status"] == "interrupted"


def test_followup_context_contains_queries_not_claims(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda pcm: "Hey Nyx where are my glasses?")
    token = voice.start()["token"]
    turn = voice.utterance(token, audio())
    voice.reply(
        token, turn["id"], {"answer": "A historical claim", "checked": [{"video_id": "abc"}]}
    )
    voice.conversations.invalidate("abc")
    voice.utterance(token, audio())
    context = [x[1] for x in provider.calls if isinstance(x, tuple) and x[0] == "route"][-1]
    assert context == [{"question": "where are my glasses?", "object_query": "glasses"}]
    assert "historical claim" not in json.dumps(context)


def test_deletion_marks_conversation_sources_even_when_voice_not_configured(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from test_nyx import ColorEncoder

    from nyx.app import create_app
    from nyx.memory import Store

    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    store = Store(tmp_path, ColorEncoder.fingerprint, ColorEncoder.dimensions)
    source = "a" * 32
    path = tmp_path / "recordings" / (source + ".mp4")
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"source")
    store.add_video("test", str(path.relative_to(tmp_path)), None, 2, video_id=source)
    store.finish_video(source)
    conversations = Conversations(tmp_path)
    turn = conversations.begin("where are the keys?", {"mode": "latest", "object_query": "keys"})
    conversations.finish(turn, "Past answer", [source])
    with TestClient(create_app(tmp_path, encoder_factory=ColorEncoder)) as client:
        assert not client.get("/api/voice").json()["configured"]
        assert client.delete("/api/videos/" + source).status_code == 200
    assert not Conversations(tmp_path).recent()[0]["sources_available"]


def test_greeting_is_conversation_and_skips_visual_router(tmp_path):
    provider = Provider()
    provider.transcribe = lambda pcm: "Hey Nyx, what's up?"
    voice = Voice(tmp_path, provider, lambda pcm: "Hey Nyx, what is up?")
    token = voice.start()["token"]
    turn = voice.utterance(token, audio())
    assert turn["plan"]["mode"] == "chat"
    assert not any(isinstance(x, tuple) and x[0] == "route" for x in provider.calls)
    assert turn["plan"]["reply"]
    assert "snapshot" not in turn["plan"]["reply"].lower()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Hey Nick, where are my keys?", "where are my keys?"),
        ("Nick came over", None),
        ("Hey, next question", None),
    ],
)
def test_pronunciation_alias_is_restricted_to_direct_address(text, expected):
    assert wake_command(text) == expected


def test_partial_probe_activates_locally_and_full_question_reaches_cloud_only_after_wake(tmp_path):
    provider = Provider()
    calls = []

    def recognize(pcm):
        calls.append(1)
        return "Hey Nyx, where"

    voice = Voice(tmp_path, provider, recognize)
    token = voice.start()["token"]
    assert voice.probe(token, audio())["state"] == "activated"
    assert not provider.calls
    assert voice.utterance(token, audio())["state"] == "question"
    assert len(calls) == 2


def test_conversation_reply_and_short_visual_answer_preserve_evidence(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda pcm: "Hey Nyx, hi")
    token = voice.start()["token"]
    provider.transcribe = lambda pcm: "Hey Nyx, hi"
    turn = voice.utterance(token, audio())
    reply = voice.reply(token, turn["id"], {"answer": turn["plan"]["reply"]})
    assert reply["answer"] == turn["plan"]["reply"]
    assert "tts_ms" in reply["timings"]
    assert not voice.awake_until
    voice.listen(token, turn["id"])
    assert voice.awake_until > time.monotonic()
    with pytest.raises(VoiceError):
        voice.listen(token, "invented")


def test_spoken_answer_is_brief_but_keeps_historical_uncertainty():
    from nyx.voice import spoken_answer

    result = {
        "kind": "history",
        "status": "seen",
        "object_query": "glasses",
        "answer": "verbose evidence text",
        "evidence": {
            "observed_at": "2026-10-19T12:00:00+00:00",
            "judgment": {"location": "beside the laptop"},
        },
    }
    text = spoken_answer(result)
    assert "beside the laptop" in text
    assert "I think I saw" in text
    assert "not verified" not in text
    assert "check the image" not in text
    assert "2026-10-19T" not in text
    assert len(text) < 240
    assert "can't clearly see" in spoken_answer(
        {"kind": "snapshot", "status": "uncertain", "object_query": "glasses"}
    )


def test_chat_reply_needs_no_visual_job_and_followup_window_is_explicit(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from test_nyx import ColorEncoder

    from nyx.app import create_app

    provider = Provider()
    provider.transcribe = lambda pcm: "Hey Nyx, what's up?"
    voice = Voice(tmp_path, provider, lambda pcm: "Hey Nyx what is up")

    class Verifier:
        def inspect(self, image, query):
            raise AssertionError("Greeting must never inspect an image")

    with TestClient(
        create_app(
            tmp_path,
            encoder_factory=ColorEncoder,
            verifier_factory=Verifier,
            voice_factory=lambda root: voice,
        )
    ) as client:
        token = client.post("/api/voice/session").json()["token"]
        headers = {"x-nyx-voice": token}
        assert (
            client.post("/api/voice/probe", headers=headers, content=b"x" * 96001).status_code
            == 413
        )
        assert (
            client.post(
                "/api/voice/probe",
                headers={**headers, "origin": "https://example.com"},
                content=audio(),
            ).status_code
            == 403
        )
        turn = client.post("/api/voice/utterance", headers=headers, content=audio()).json()
        assert turn["plan"]["mode"] == "chat"
        reply = client.post("/api/voice/reply", headers=headers, json={"turn_id": turn["id"]})
        assert reply.status_code == 200
        assert reply.json()["answer"] == "Hey! I'm here. What can I help with?"
        assert voice.awake_until == 0
        assert (
            client.post("/api/voice/listen", headers=headers, json={"turn_id": turn["id"]}).json()[
                "seconds"
            ]
            == 10
        )
        assert (
            client.post(
                "/api/voice/listen", headers=headers, json={"turn_id": "invented"}
            ).status_code
            == 400
        )
        client.delete("/api/voice/session", headers=headers)
        assert client.post("/api/voice/probe", headers=headers, content=audio()).status_code == 400


def test_probe_silence_and_nonwake_are_local_and_mute_invalidates_probe(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda pcm: "what is next")
    token = voice.start()["token"]
    assert voice.probe(token, b"\0" * 32000)["state"] == "listening"
    assert voice.probe(token, audio())["state"] == "listening"
    assert not provider.calls

    def recognize(pcm):
        voice.stop(token)
        return "Hey Nyx"

    voice.recognizer = recognize
    with pytest.raises(VoiceError):
        voice.probe(token, audio())
    assert not provider.calls and voice.awake_until == 0


def test_probe_name_only_does_not_upload_name_to_cloud(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda pcm: "Hey Nyx")
    token = voice.start()["token"]
    assert voice.probe(token, audio())["state"] == "activated"
    assert voice.utterance(token, audio())["state"] == "activated"
    assert not provider.calls


def test_spoken_replies_keep_unknown_clock_and_current_uncertainty():
    from nyx.voice import spoken_answer

    result = {
        "kind": "history",
        "status": "seen",
        "object_query": "pen",
        "evidence": {
            "observed_at": None,
            "offset_seconds": 12,
            "judgment": {"location": "on the table"},
        },
    }
    assert "don't know when" in spoken_answer(result)
    assert "on the table" in spoken_answer(result)
    assert (
        "look further back"
        in spoken_answer(
            {"kind": "history", "status": "uncertain", "object_query": "pen", "evidence": None}
        ).lower()
    )


def test_followup_after_playback_does_not_need_another_wake_decode(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda pcm: "Hey Nyx where are my glasses?")
    token = voice.start()["token"]
    turn = voice.utterance(token, audio())
    voice.reply(token, turn["id"], {"answer": "I found a candidate."})
    voice.listen(token, turn["id"])

    def no_second_wake(pcm):
        raise AssertionError("An active followup should go directly to STT")

    voice.recognizer = no_second_wake
    assert voice.utterance(token, audio())["state"] == "question"


def test_wake_loads_only_documented_cached_files(monkeypatch):
    import sys
    from types import SimpleNamespace

    from nyx.voice import WAKE_MODEL, WAKE_REVISION, WakeRecognizer

    required = {"config.json", "model.bin", "tokenizer.json", "vocabulary.txt"}

    def snapshot(model, *, revision, local_files_only, allow_patterns=None):
        assert model == WAKE_MODEL and revision == WAKE_REVISION
        assert local_files_only
        # A partial offline snapshot must not require model-card/repository files.
        assert set(allow_patterns or ()) == required
        return "/cached/wake"

    def whisper(path, **options):
        assert path == "/cached/wake"
        assert options["device"] == "cpu" and options["compute_type"] == "int8"
        return "loaded"

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=snapshot))
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=whisper))
    assert WakeRecognizer().model == "loaded"


def test_transcript_survives_routing_failure_without_logging_provider_secrets(tmp_path):
    class Broken(Provider):
        def transcribe(self, pcm):
            return "Hey Nix, I will put this bottle on the centre table."

        def route(self, transcript, context):
            raise ValueError("secret-provider-payload")

    voice = Voice(
        tmp_path, Broken(), lambda _: "Hey Nix, I will put this bottle on the centre table."
    )
    token = voice.start()["token"]
    with pytest.raises(ValueError):
        voice.utterance(token, audio(), "00000000-0000-0000-0000-000000000001")
    rows = Conversations(tmp_path).recent()
    assert rows[-1]["transcript"].endswith("centre table.")
    assert rows[-1]["status"] == "interrupted"
    events = voice.conversations.diagnostics()
    assert events[-1]["event"] == "utterance_failed"
    assert events[-1]["details"]["stage"] == "routing"
    assert events[-1]["turn_id"] == rows[-1]["id"]
    assert "secret-provider-payload" not in json.dumps(events)
    assert token not in json.dumps(events)


def test_completed_transcription_survives_cancellation_during_provider_call(tmp_path):
    class Cancelling(Provider):
        def transcribe(self, pcm):
            voice.cancel(token)
            return "I put my bottle on the centre table."

    voice = Voice(tmp_path, Cancelling(), lambda _: "Hey Nyx, remember this")
    token = voice.start()["token"]
    with pytest.raises(VoiceError, match="cancelled"):
        voice.utterance(token, audio())
    rows = voice.conversations.recent()
    assert rows[-1]["transcript"] == "I put my bottle on the centre table."
    assert rows[-1]["status"] == "interrupted"


def test_idle_speech_records_reason_but_no_content_or_cloud_call(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda _: "private unrelated conversation")
    token = voice.start()["token"]
    assert voice.utterance(token, audio())["state"] == "listening"
    events = voice.conversations.diagnostics()
    assert events[-1]["details"]["reason"] == "wake_not_recognized"
    assert "private unrelated" not in json.dumps(events)
    assert not voice.conversations.recent() and not provider.calls


def test_diagnostics_retention_does_not_delete_transcripts(tmp_path):
    store = Conversations(tmp_path)
    turn = store.begin("Keep my statement", {"mode": "agent"})
    with store.connect() as db:
        db.executemany(
            "INSERT INTO diagnostics(at,event,details) VALUES ('now','test','{}')", [()] * 2001
        )
    store.event("last")
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM diagnostics").fetchone()[0] == 2000
    assert store.recent()[-1]["id"] == turn


def test_browser_diagnostics_require_session_and_accept_only_bounded_metadata(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from nyx.app import create_app

    voice = Voice(tmp_path, Provider(), lambda _: "Hey Nyx")
    with TestClient(
        create_app(tmp_path, voice_factory=lambda root: voice, verifier_factory=lambda: object())
    ) as client:
        assert client.get("/api/voice/diagnostics").status_code == 400
        token = client.post("/api/voice/session").json()["token"]
        headers = {"x-nyx-voice": token}
        payload = {
            "event": "browser_turn_failed",
            "stage": "transcription",
            "attempt_id": "00000000-0000-0000-0000-000000000001",
        }
        assert (
            client.post("/api/voice/diagnostics", headers=headers, json=payload).status_code == 200
        )
        for bad in [
            {**payload, "attempt_id": None},
            {**payload, "stage": "arbitrary"},
            {**payload, "event": "arbitrary"},
        ]:
            assert (
                client.post("/api/voice/diagnostics", headers=headers, json=bad).status_code == 400
            )
        events = client.get("/api/voice/diagnostics", headers=headers).json()["events"]
        assert events[-1]["event"] == "browser_turn_failed"
        assert token not in json.dumps(events)


def test_explicit_listen_accepts_statement_without_wake_name(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from nyx.app import create_app

    class StatementProvider(Provider):
        def transcribe(self, pcm):
            return "I will put my glasses on the table."

    provider = StatementProvider()
    voice = Voice(tmp_path, provider, lambda _: "no wake name", agent_mode=True)
    with TestClient(
        create_app(tmp_path, voice_factory=lambda _: voice, verifier_factory=lambda: object())
    ) as client:
        token = client.post("/api/voice/session").json()["token"]
        headers = {"x-nyx-voice": token}
        assert client.post("/api/voice/activate").status_code == 400
        assert client.post("/api/voice/activate", headers=headers).json()["seconds"] == 30
        turn = client.post("/api/voice/utterance", headers=headers, content=audio()).json()
        assert turn["state"] == "question" and turn["transcript"].startswith("I will put")
        assert voice.conversations.recent()[-1]["transcript"] == turn["transcript"]


def test_failed_transcription_preserves_explicit_activation_and_cancel_reason(tmp_path):
    import time

    class RetryProvider(Provider):
        attempts = 0

        def transcribe(self, pcm):
            self.attempts += 1
            if self.attempts == 1:
                raise VoiceError("No speech recognized")
            return "I will put this on the table."

    voice = Voice(tmp_path, RetryProvider(), lambda _: "", agent_mode=True)
    token = voice.start()["token"]
    deadline = time.monotonic() + 30
    voice.awake_until = deadline
    with pytest.raises(VoiceError):
        voice.utterance(token, audio())
    assert voice.awake_until == deadline
    turn = voice.utterance(token, audio())
    assert turn["transcript"] == "I will put this on the table."
    voice.cancel(token, "user_stop")
    events = voice.conversations.diagnostics()
    assert any(
        e["event"] == "voice_cancelled"
        and e["details"]["reason"] == "user_stop"
        and e["turn_id"] == turn["id"]
        for e in events
    )


def test_checking_acknowledgement_does_not_complete_turn(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda _: "Hey Nyx find my glasses", agent_mode=True)
    token = voice.start()["token"]
    turn = voice.utterance(token, audio())
    assert voice.acknowledgement(token, turn["id"])["audio"]
    assert voice.turn["id"] == turn["id"]
    voice.cancel(token)
    with pytest.raises(VoiceError):
        voice.acknowledgement(token, turn["id"])


def test_cancel_during_acknowledgement_drops_audio(tmp_path):
    provider = Provider()
    voice = Voice(tmp_path, provider, lambda _: "Hey Nyx find my glasses", agent_mode=True)
    token = voice.start()["token"]
    turn = voice.utterance(token, audio())

    def speak(text):
        voice.cancel(token)
        return "stale-audio"

    provider.speak = speak
    with pytest.raises(VoiceError):
        voice.acknowledgement(token, turn["id"])


def test_acknowledgement_api_requires_session_and_matching_turn(tmp_path):
    from fastapi.testclient import TestClient

    from nyx.app import create_app

    voice = Voice(tmp_path, Provider(), lambda _: "Hey Nyx find glasses", agent_mode=True)
    with TestClient(
        create_app(tmp_path, voice_factory=lambda root: voice, verifier_factory=lambda: object())
    ) as client:
        token = client.post("/api/voice/session").json()["token"]
        headers = {"x-nyx-voice": token}
        turn = voice.utterance(token, audio())
        endpoint = "/api/voice/acknowledgement"
        assert client.post(endpoint, json={"turn_id": turn["id"]}).status_code == 400
        assert client.post(endpoint, headers=headers, json={"turn_id": "wrong"}).status_code == 400
        assert (
            client.post(endpoint, headers=headers, json={"turn_id": turn["id"]}).status_code == 200
        )
        assert voice.turn["id"] == turn["id"]


@pytest.mark.parametrize(
    "minutes, expected",
    [
        (0, "just now"),
        (7, "a few minutes ago"),
        (37, "about 35 minutes ago"),
        (62, "about an hour ago"),
        (125, "about 2 hours ago"),
        (1440, "about a day ago"),
    ],
)
def test_relative_sightings_use_rounded_elapsed_time(minutes, expected):
    from datetime import UTC, datetime, timedelta

    from nyx.voice import relative_time

    now = datetime.fromisoformat("2026-10-31T19:39:00+05:30")
    observed = now - timedelta(minutes=minutes)
    assert relative_time(observed.isoformat(), now) == expected
    assert relative_time(observed.astimezone(UTC).isoformat(), now) == expected


def test_clock_questions_use_local_time_and_skip_models(tmp_path):
    from datetime import datetime

    from nyx.voice import clock_reply, local_now

    now = datetime.fromisoformat("2026-10-31T19:39:00+05:30")
    assert clock_reply("What's the time right now, ma'am?", now) == "It's 7:39 pm."
    assert clock_reply("What time is it in London?", now) is None
    assert clock_reply("What time is it UTC?", now) is None
    assert str(local_now("Asia/Kolkata").tzinfo) == "Asia/Kolkata"
    with pytest.raises(VoiceError):
        local_now("invalid/place")
    provider = Provider()
    provider.transcribe = lambda _: "What time is it?"
    voice = Voice(tmp_path, provider, lambda _: "Hey Nyx what time is it?")
    token = voice.start()["token"]
    turn = voice.utterance(token, audio(), timezone="Asia/Kolkata")
    assert turn["plan"]["mode"] == "chat"
    assert "UTC" not in turn["plan"]["reply"]
    assert provider.calls == []


def test_unknown_or_future_sightings_do_not_invent_elapsed_time():
    from datetime import datetime

    from nyx.voice import relative_time

    now = datetime.fromisoformat("2026-10-31T12:00:00+00:00")
    assert relative_time(None, now) is None
    assert relative_time("2026-10-31T13:00:00+00:00", now) is None
    assert relative_time("2026-10-31T11:00:00", now) is None
