import base64
import json
import wave
from io import BytesIO
from urllib.error import HTTPError

import numpy as np
import pytest
from PIL import Image

from nyx.cloud import CloudError, OpenRouter
from nyx.memory import Store
from nyx.perception import CloudEncoder
from nyx.retrieval import rebuild_embeddings
from nyx.voice import CloudVoice, VoiceError


def response(value):
    return BytesIO(json.dumps(value).encode())


def test_cloud_generation_preserves_image_order_and_bounds_output():
    def transport(request, timeout):
        payload = json.loads(request.data)
        assert request.get_header("Authorization") == "Bearer test-secret"
        assert timeout == 45
        assert payload["max_tokens"] == 1024
        assert payload["provider"]["data_collection"] == "deny"
        content = payload["messages"][0]["content"]
        assert [p["type"] for p in content] == ["image_url", "text", "image_url"]
        for part, expected in [(content[0], (255, 0, 0)), (content[2], (0, 0, 255))]:
            raw = base64.b64decode(part["image_url"]["url"].split(",")[1])
            with Image.open(BytesIO(raw)) as image:
                assert max(image.size) == 768
                assert sum(abs(a - b) for a, b in zip(image.getpixel((0, 0)), expected)) < 5
        return response(
            {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}]}
        )

    client = OpenRouter("test-secret", transport)
    raw = client.generate(
        [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": Image.new("RGB", (1200, 800), "red")},
                    {"type": "text", "text": "compare"},
                    {"type": "image", "image": Image.new("RGB", (1200, 800), "blue")},
                ],
            }
        ],
        "model",
        180,
    )
    assert json.loads(raw) == {"ok": True}


@pytest.mark.parametrize("status", [401, 402, 429, 503])
def test_cloud_errors_do_not_leak_secrets_or_retry(status):
    calls = []

    def transport(request, timeout):
        calls.append(request)
        raise HTTPError(request.full_url, status, "test-secret private content", {}, None)

    with pytest.raises(CloudError, match=str(status)) as error:
        OpenRouter("test-secret", transport).request("embeddings", {})
    assert "test-secret" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "result",
    [
        [],
        {"error": "secret"},
        {"choices": []},
        {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
        {"choices": [{"finish_reason": "stop", "message": {"content": None}}]},
    ],
)
def test_invalid_cloud_generation_is_not_a_success(result):
    client = OpenRouter("fake", lambda *a, **k: response(result))
    with pytest.raises(CloudError):
        client.generate([], "model", 100)


def test_missing_key_is_actionable(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(CloudError, match="OPENROUTER_API_KEY"):
        OpenRouter()


def test_embeddings_are_normalized_and_restored_to_input_order(monkeypatch):
    monkeypatch.setenv("NYX_EMBEDDING_DIMENSIONS", "2")

    def transport(request, timeout):
        payload = json.loads(request.data)
        assert payload["dimensions"] == 2
        assert len(payload["input"]) == 2
        assert payload["input"][0]["content"][0]["type"] == "image_url"
        return response(
            {"data": [{"index": 1, "embedding": [0, 5]}, {"index": 0, "embedding": [3, 4]}]}
        )

    encoder = CloudEncoder(OpenRouter("fake", transport))
    np.testing.assert_allclose(
        encoder.encode_images([Image.new("RGB", (8, 8))] * 2), [[0.6, 0.8], [0, 1]]
    )


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"index": 0, "embedding": [0, 0]}],
        [{"index": 0, "embedding": [1, 2, 3]}],
        [{"index": 0, "embedding": [float("nan"), 1]}],
        [{"index": 1, "embedding": [1, 0]}],
    ],
)
def test_bad_embeddings_cannot_enter_index(monkeypatch, rows):
    monkeypatch.setenv("NYX_EMBEDDING_DIMENSIONS", "2")
    encoder = CloudEncoder(OpenRouter("fake", lambda *a, **k: response({"data": rows})))
    with pytest.raises(CloudError):
        encoder.encode_text("glasses")


def test_voice_wire_formats_cache_and_safe_failure():
    calls = []

    def transport(request, timeout):
        payload = json.loads(request.data)
        calls.append(payload)
        if request.full_url.endswith("transcriptions"):
            with wave.open(BytesIO(base64.b64decode(payload["input_audio"]["data"]))) as wav:
                assert wav.getframerate() == 16000 and wav.getnchannels() == 1
            return response({"text": "Where are my glasses?"})
        assert payload["response_format"] == "pcm" and payload["voice"] == "Kore"
        return BytesIO(b"\0\0" * 24000)

    provider = CloudVoice(OpenRouter("fake", transport))
    assert provider.transcribe(b"\0\0" * 16000) == "Where are my glasses?"
    audio = provider.speak("hello")
    assert provider.speak("hello") == audio and len(calls) == 2
    with wave.open(BytesIO(base64.b64decode(audio))) as wav:
        assert wav.getframerate() == 24000 and wav.getnframes() == 24000
    provider.client = OpenRouter("fake", lambda *a, **k: response({"error": "private"}))
    with pytest.raises(VoiceError):
        provider.transcribe(b"\0\0" * 16000)


@pytest.mark.parametrize("fail", [False, True])
def test_index_rebuild_preserves_sources_and_rolls_back_failed_batch(tmp_path, fail):
    store = Store(tmp_path, {"model": "old"}, 2)
    video = store.add_video("clip", "recordings/clip.mp4", "2026-10-20T10:00:00Z", 2)
    for n in range(2):
        Image.new("RGB", (8, 8)).save(tmp_path / f"{n}.jpg")
    store.add_frames(video, [(0, "0.jpg"), (2, "1.jpg")], [[1, 0], [0, 1]])
    store.finish_video(video)
    original = store.video(video)

    class Encoder:
        dimensions = 3
        calls = 0

        def __init__(self):
            self.fingerprint = {"model": "new"}

        def encode_images(self, images):
            self.calls += 1
            if fail and self.calls == 2:
                raise CloudError("offline")
            return [[0, 0, 1]] * len(images)

    if fail:
        with pytest.raises(CloudError):
            rebuild_embeddings(store, Encoder(), batch_size=1)
        assert store.fingerprint == {"model": "old"}
        assert Store(tmp_path, {"model": "old"}, 2).search([1, 0])[0]["offset_seconds"] == 0
    else:
        assert rebuild_embeddings(store, Encoder(), batch_size=1)["reembedded_frames"] == 2
        assert len(Store(tmp_path, {"model": "new"}, 3).search([0, 0, 1])) == 2
    assert store.video(video) == original
    assert (tmp_path / "0.jpg").exists()


@pytest.mark.parametrize("stage", ["decision", "tool"])
def test_agent_does_not_retry_provider_failure(stage):
    from nyx.agent import agent_steps

    calls = []

    def decide(state):
        calls.append("decide")
        if stage == "decision":
            raise CloudError("credits exhausted")
        return {"action": "search_history", "query": "glasses", "hours": 2}

    def tool(action):
        calls.append("tool")
        raise CloudError("credits exhausted")

    with pytest.raises(CloudError, match="credits"):
        list(agent_steps("Find glasses in history", [], decide, tool))
    assert calls == (["decide"] if stage == "decision" else ["decide", "tool"])


def test_audio_error_body_is_not_playable_audio():
    provider = CloudVoice(
        OpenRouter("fake", lambda *a, **k: response({"error": "provider failed"}))
    )
    with pytest.raises(VoiceError):
        provider.speak("hello")


def test_planner_and_visual_calls_use_their_selected_models(monkeypatch):
    from nyx.verification import CloudVerifier

    monkeypatch.setenv("NYX_REASONING_MODEL", "planner-model")
    monkeypatch.setenv("NYX_VISION_MODEL", "vision-model")
    calls = []

    class Client:
        def generate(self, messages, model, max_tokens):
            calls.append(model)
            if model == "planner-model":
                return '{"action":"chat","message":"Hello"}'
            return json.dumps(
                {
                    "visibility": "visible",
                    "location": "center",
                    "description": "red square",
                    "matching_count": 1,
                    "ambiguous": False,
                }
            )

    verifier = CloudVerifier(Client())
    assert (
        verifier.decide(
            {"message": "Hello", "conversation": [], "observations": [], "actions": []}
        )["action"]
        == "chat"
    )
    assert (
        verifier.inspect(Image.new("RGB", (8, 8), "red"), "red square")["visibility"] == "visible"
    )
    assert calls == ["planner-model", "vision-model"]


def test_query_embedding_cache_is_bounded_and_returns_independent_vectors():
    class Client:
        calls = 0

        def request(self, path, payload):
            self.calls += 1
            return {"data": [{"index": 0, "embedding": [1.0] * 768}]}

    client = Client()
    encoder = CloudEncoder(client)
    original = encoder.encode_text("phone")
    original[:] = 0
    assert encoder.encode_text("phone").any()
    assert client.calls == 1
    for i in range(64):
        encoder.encode_text(str(i))
    assert len(encoder.text_cache) == 64
    encoder.encode_text("phone")
    assert client.calls == 66
