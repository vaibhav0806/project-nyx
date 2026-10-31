import json
import time
from io import BytesIO
from threading import Event
from typing import ClassVar

import pytest

from nyx.cloud import CloudError, OpenRouter
from nyx.speech import SentenceBuffer, speech_events


def test_sentences_preserve_decimals_abbreviations_and_hindi():
    buffer = SentenceBuffer()
    output = []
    for token in [
        "Dr.",
        " Rao paid 3.",
        "50 rupees. ",
        "फोन मेज़ पर है। ",
        "ठीक है? ",
        "Last fragment",
    ]:
        output.extend(buffer.feed(token))
    output.extend(buffer.finish())
    assert output == ["Dr. Rao paid 3.50 rupees.", "फोन मेज़ पर है।", "ठीक है?", "Last fragment"]


def test_audio_starts_while_later_text_is_still_generating():
    spoke = Event()

    def tokens():
        yield "First sentence. "
        assert spoke.wait(2), "TTS waited for the whole answer"
        yield "Second sentence."

    def synthesize(text):
        spoke.set()
        yield b"\x00\x00" * 20

    events = list(speech_events(tokens(), synthesize, Event()))
    assert [e["text"] for e in events if e["type"] == "sentence"] == [
        "First sentence.",
        "Second sentence.",
    ]
    assert sum(e["type"] == "audio" for e in events) == 2
    assert events[-1]["type"] == "done"


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


def test_tts_failure_terminates_pipeline_instead_of_hanging():
    def broken(_):
        raise CloudError("provider unavailable")
        yield b""

    events = list(speech_events(iter(["A complete sentence. "]), broken, Event()))
    assert events[-1]["type"] == "error"
    assert not any(e["type"] == "done" for e in events)


def test_stream_api_preserves_auth_and_completes_transcript(tmp_path):
    from fastapi.testclient import TestClient
    from test_voice import Provider, audio

    from nyx.app import create_app
    from nyx.voice import Voice

    class StreamProvider(Provider):
        def route(self, transcript, context):
            return {"mode": "direct", "language": "en", "lookup": False}

        def answer_tokens(self, turn, result, cancelled):
            assert result is None
            yield "A short answer. "
            yield "One more sentence."

        def speech_chunks(self, text, cancelled):
            yield b"\x00\x00" * 100

    voice = Voice(tmp_path, StreamProvider(), lambda _: "Hey Nyx hello")
    with TestClient(
        create_app(tmp_path, voice_factory=lambda _: voice, verifier_factory=lambda: object())
    ) as client:
        token = voice.start()["token"]
        turn = voice.utterance(token, audio())
        body = {"turn_id": turn["id"], "stream": True}
        assert client.post("/api/voice/reply", json=body).status_code == 400
        response = client.post("/api/voice/reply", headers={"x-nyx-voice": token}, json=body)
        assert response.headers["content-type"].startswith("application/x-ndjson")
        events = [json.loads(line) for line in response.text.splitlines()]
        assert events[-1]["type"] == "done"
        assert events[-1]["answer"] == "A short answer. One more sentence."
        assert sum(e["type"] == "audio" for e in events) == 2
        assert voice.conversations.recent()[-1]["status"] == "complete"
        assert voice.turn is None
        assert (
            client.post("/api/voice/reply", headers={"x-nyx-voice": token}, json=body).status_code
            == 400
        )


def test_cancelled_stream_never_completes_or_emits_late_audio(tmp_path):
    from test_voice import Provider, audio

    from nyx.voice import Voice

    class StreamProvider(Provider):
        def answer_tokens(self, turn, result, cancelled):
            yield "One sentence. "

        def speech_chunks(self, text, cancelled):
            yield b"\x00\x00" * 10

    voice = Voice(tmp_path, StreamProvider(), lambda _: "Hey Nyx find glasses", agent_mode=True)
    token = voice.start()["token"]
    turn = voice.utterance(token, audio())
    stream = voice.reply_stream(token, turn["id"], {"answer": "One sentence."})
    assert next(stream)["type"] == "text"
    voice.cancel(token)
    assert list(stream) == []
    assert voice.conversations.recent()[-1]["status"] == "interrupted"


def test_english_and_hindi_acknowledgements_are_local_and_varied(tmp_path):
    from test_voice import Provider, audio

    from nyx.speech import ACKNOWLEDGEMENTS, acknowledgement_path
    from nyx.voice import Voice

    voice = Voice(tmp_path, Provider(), lambda _: "Hey Nyx find glasses", agent_mode=True)
    token = voice.start()["token"]
    turn = voice.utterance(token, audio())
    for language, lines in ACKNOWLEDGEMENTS.items():
        assert len(lines) == 6
        for line in lines:
            path = acknowledgement_path(tmp_path, "", line)
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(line.encode())
        voice.turn["plan"]["language"] = language
        clips = {voice.acknowledgement(token, turn["id"])["audio"] for _ in lines}
        assert len(clips) == 6
    assert voice.provider.calls == ["stt"]


def test_grounded_english_answers_skip_rewriting_and_keep_hand_identity():
    from nyx.voice import CloudVoice

    provider = CloudVoice(client=object())
    result = {"answer": "I think I saw your phone about 20 minutes ago, in the right hand."}
    turn = {"transcript": "Where is my phone?", "plan": {"mode": "agent", "language": "en"}}
    assert "".join(provider.answer_tokens(turn, result, lambda: False)) == result["answer"]


def test_wake_interrupts_active_stream_and_drops_pending_audio(tmp_path):
    from test_voice import Provider, audio

    from nyx.voice import Voice, VoiceError

    class StreamProvider(Provider):
        def answer_tokens(self, turn, result, cancelled):
            yield "One sentence. "

        def speech_chunks(self, text, cancelled):
            yield b"\x00\x00" * 10

    voice = Voice(tmp_path, StreamProvider(), lambda _: "Hey Nyx", agent_mode=True)
    token = voice.start()["token"]
    voice.awake_until = time.monotonic() + 10
    turn = voice.utterance(token, audio())
    stream = voice.reply_stream(token, turn["id"], {"answer": "One sentence."})
    assert next(stream)["type"] == "text"
    with pytest.raises(VoiceError):
        next(voice.reply_stream(token, turn["id"], {"answer": "duplicate"}))
    assert voice.probe(token, audio())["state"] == "activated"
    assert list(stream) == []
    assert voice.turn is None
    assert voice.conversations.recent()[-1]["status"] == "interrupted"


def test_second_sentence_synthesizes_in_parallel_but_audio_stays_ordered():
    second_started = Event()

    def synthesize(sentence):
        if sentence.startswith("First"):
            assert second_started.wait(2), "Second sentence synthesis was serialized"
            yield b"\x01\x00"
        else:
            second_started.set()
            yield b"\x02\x00"

    events = list(speech_events(iter(["First sentence. Second sentence."]), synthesize, Event()))
    assert [e["pcm"] for e in events if e["type"] == "audio"] == ["AQA=", "AgA="]
    assert events[-1]["type"] == "done"


def test_real_http_stream_delivers_early_and_disconnect_cancels(tmp_path):
    import socket
    from threading import Thread
    from urllib.request import Request, urlopen

    import uvicorn
    from test_voice import Provider, audio

    from nyx.app import create_app
    from nyx.voice import Voice

    received_audio = Event()
    disconnect_case = Event()

    class StreamProvider(Provider):
        def route(self, transcript, context):
            return {"mode": "direct", "language": "en", "lookup": False}

        def answer_tokens(self, turn, result, cancelled):
            yield "First sentence. "
            if disconnect_case.is_set():
                while not cancelled():
                    time.sleep(0.01)
                return
            assert received_audio.wait(3), "HTTP buffered audio until text generation completed"
            yield "Second sentence."

        def speech_chunks(self, text, cancelled):
            yield b"\x00\x00" * 100

    voice = Voice(tmp_path, StreamProvider(), lambda _: "Hey Nyx hello")
    app = create_app(tmp_path, voice_factory=lambda _: voice, verifier_factory=lambda: object())
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 3
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        token = voice.start()["token"]
        for disconnect in [False, True]:
            if disconnect:
                disconnect_case.set()
            turn = voice.utterance(token, audio())
            request = Request(
                f"http://127.0.0.1:{port}/api/voice/reply",
                data=json.dumps({"turn_id": turn["id"], "stream": True}).encode(),
                headers={"content-type": "application/json", "x-nyx-voice": token},
            )
            with urlopen(request, timeout=5) as response:
                while True:
                    line = response.readline()
                    if not line:
                        break
                    event = json.loads(line)
                    if disconnect and event["type"] == "text":
                        break
                    assert event["type"] != "error", event
                    if event["type"] == "audio":
                        received_audio.set()
                    if event["type"] == "done":
                        break
            deadline = time.monotonic() + 3
            while voice.turn is not None and time.monotonic() < deadline:
                time.sleep(0.01)
            assert voice.turn is None
            assert voice.conversations.recent()[-1]["status"] == (
                "interrupted" if disconnect else "complete"
            )
    finally:
        server.should_exit = True
        thread.join(timeout=3)
        sock.close()


def test_streamed_speech_reuses_cache_without_another_provider_call():
    from nyx.voice import CloudVoice

    calls = []

    class Client:
        def stream_pcm(self, payload, cancelled):
            calls.append(payload)
            yield b"\x01\x00" * 10
            yield b"\x02\x00" * 10

    provider = CloudVoice(Client())
    first = b"".join(provider.speech_chunks("Hello.", lambda: False))
    assert b"".join(provider.speech_chunks("Hello.", lambda: False)) == first
    assert len(calls) == 1
