import json
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
