import json
import wave
from io import BytesIO
from typing import ClassVar

import pytest

from nyx.cloud import CloudError, OpenRouter


def test_truncated_llm_stream_is_not_success():
    raw = b'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}\n\n'
    client = OpenRouter("fake", lambda *a, **k: BytesIO(raw))
    with pytest.raises(CloudError, match="ended"):
        list(client.stream_text([], "model"))


def test_sse_ignores_comments_and_keeps_usage_and_errors():
    chunks = [
        ": keepalive\n",
        "data: " + json.dumps({"choices": [{"delta": {"content": "Hi."}, "finish_reason": None}]}),
        "data: "
        + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"cost": 0.1}}),
        "data: [DONE]",
    ]

    def transport(request, timeout):
        assert json.loads(request.data)["stream"] is True
        assert json.loads(request.data)["provider"]["data_collection"] == "deny"
        return BytesIO(("\n\n".join(chunks) + "\n\n").encode())

    client = OpenRouter("fake", transport)
    assert list(client.stream_text([], "model")) == ["Hi."]
    assert client.usage[-1]["cost"] == 0.1


def test_pcm_stream_preserves_samples_across_odd_chunk_boundaries():
    class Audio(BytesIO):
        headers: ClassVar[dict] = {"Content-Type": "audio/pcm;rate=24000;channels=1"}

        def read1(self, _):
            return self.read(3)

    client = OpenRouter("fake", lambda *a, **k: Audio(b"\x01\x02\x03\x04\x05\x06"))
    chunks = list(client.stream_pcm({}))
    assert all(len(chunk) % 2 == 0 for chunk in chunks)
    assert b"".join(chunks) == b"\x01\x02\x03\x04\x05\x06"


@pytest.mark.parametrize("rate", [24000, 16000])
def test_acknowledgements_use_reply_stream_settings_and_cache_valid_pcm(
    tmp_path, monkeypatch, rate
):
    from types import SimpleNamespace

    from livekit import rtc
    from livekit.plugins import sarvam

    from nyx import realtime, speech

    monkeypatch.setattr(speech, "ACKNOWLEDGEMENTS", {"en": ("Let me check.",), "hi": ("एक पल।",)})
    created, requests, closed = [], [], []

    class Stream:
        def push_text(self, text):
            requests.append(text)

        def end_input(self):
            pass

        async def __aiter__(self):
            yield SimpleNamespace(frame=rtc.AudioFrame(b"\x01\x02" * 100, rate, 1, 100))

        async def aclose(self):
            closed.append("stream")

    class TTS:
        def __init__(self, *, http_session, **options):
            created.append(options)

        def stream(self, *, conn_options):
            assert conn_options.max_retry == 0
            return Stream()

        async def aclose(self):
            closed.append("tts")

    monkeypatch.setattr(sarvam, "TTS", TTS)
    if rate != 24000:
        with pytest.raises(ValueError, match="audio format"):
            speech.prepare_acknowledgements(tmp_path)
        assert not list(tmp_path.rglob("*.wav")) and closed == ["stream", "tts"]
        return
    paths = speech.prepare_acknowledgements(tmp_path)
    assert created == [realtime.speech_options("en"), realtime.speech_options("hi")]
    assert requests == ["Let me check.", "एक पल।"]
    assert len(paths) == 2 and closed == ["stream", "tts", "stream", "tts"]
    for path in paths:
        with wave.open(path) as audio:
            assert audio.getparams()[:3] == (1, 2, 24000)
            assert audio.readframes(100) == b"\x01\x02" * 100
    assert speech.prepare_acknowledgements(tmp_path) == paths
    assert len(requests) == 2  # Warm preparation makes no provider requests.


def test_acknowledgement_cache_changes_with_voice_settings(tmp_path, monkeypatch):
    import hashlib

    from nyx import speech

    text = "Let me check that for you."
    original = speech.acknowledgement_path(tmp_path, "bulbul:v4-flash", text)
    old = hashlib.sha256(
        f"bulbul:v4-flash/shalini_en_companion/24000/v1/{text}".encode()
    ).hexdigest()[:24]
    assert original.name != old + ".wav"
    options = speech.speech_options
    monkeypatch.setattr(
        speech, "speech_options", lambda language: {**options(language), "pace": 1.1}
    )
    assert speech.acknowledgement_path(tmp_path, "bulbul:v4-flash", text) != original
