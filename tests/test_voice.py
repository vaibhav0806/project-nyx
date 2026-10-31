import base64
import json

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


def test_unknown_or_future_sightings_do_not_invent_elapsed_time():
    from datetime import datetime

    from nyx.voice import relative_time

    now = datetime.fromisoformat("2026-10-31T12:00:00+00:00")
    assert relative_time(None, now) is None
    assert relative_time("2026-10-31T13:00:00+00:00", now) is None
    assert relative_time("2026-10-31T11:00:00", now) is None


@pytest.mark.parametrize(
    "location, expected",
    [
        ("held in the right hand near the center of the image", "in your right hand"),
        ("on the table, in the lower right corner of the frame", "on the table"),
        ("near the center of the image, beside the laptop", "beside the laptop"),
        ("on the right side of the table", "on the right side of the table"),
        ("at the center of the image", ""),
        ("center", ""),
        ("in the center", ""),
        ("near the center", ""),
        ("on the center table", "on the center table"),
    ],
)
def test_spoken_locations_keep_landmarks_not_image_coordinates(location, expected):
    from nyx.voice import spoken_answer, spoken_location

    assert spoken_location(location) == expected
    result = {
        "kind": "snapshot",
        "status": "seen",
        "object_query": "a phone",
        "judgment": {"location": location},
    }
    answer = spoken_answer(result)
    assert "image" not in answer and "frame" not in answer
    if expected:
        assert expected in answer
    else:
        assert answer == "I can see a phone."


@pytest.mark.parametrize(
    "query, location, expected",
    [
        (
            "the user using a phone",
            "in front of the user",
            "you using a phone about 50 minutes ago.",
        ),
        (
            "the user's phone",
            "in the user's hand",
            "your phone about 50 minutes ago, in your hand.",
        ),
        ("your phone", "in the person's hand", "your phone about 50 minutes ago, in your hand."),
        (
            "the person’s phone",
            "in the person’s right hand",
            "your phone about 50 minutes ago, in your right hand.",
        ),
        (
            "the person using a phone",
            "in front of the person",
            "you using a phone about 50 minutes ago.",
        ),
        ("a phone", "held in the right hand", "a phone about 50 minutes ago, in your right hand."),
        ("a visitor", "beside the table", "a visitor about 50 minutes ago, beside the table."),
        ("a phone", "in a visitor's hand", "a phone about 50 minutes ago, in a visitor's hand."),
    ],
)
def test_personal_demo_speaks_to_listener_without_changing_evidence(query, location, expected):
    from datetime import datetime

    from nyx.voice import spoken_answer

    result = {
        "kind": "history",
        "object_query": query,
        "evidence": {
            "observed_at": "2026-10-31T12:00:00+00:00",
            "judgment": {"location": location},
        },
    }
    answer = spoken_answer(result, now=datetime.fromisoformat("2026-10-31T12:50:00+00:00"))
    assert answer == "I think I saw " + expected
    assert result["object_query"] == query
    assert result["evidence"]["judgment"]["location"] == location
