import sys
from types import SimpleNamespace

from PIL import Image

from nyx.mlx_runtime import MODEL, REVISION, MlxRuntime


def test_mlx_messages_preserve_image_order_and_disable_thinking(monkeypatch):
    seen = {}

    class Processor:
        def apply_chat_template(self, messages, **kwargs):
            seen["messages"], seen["template"] = messages, kwargs
            return "formatted"

    def generate(model, processor, prompt, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(text='{"ok":true}')

    monkeypatch.setitem(sys.modules, "mlx_vlm", SimpleNamespace(generate=generate))
    runtime = MlxRuntime.__new__(MlxRuntime)
    runtime.model, runtime.processor = object(), Processor()
    images = [Image.new("RGB", (900, 450), c) for c in ["red", "blue"]]
    result = runtime.generate(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "First"},
                    {"type": "image", "image": images[0]},
                    {"type": "text", "text": "Second"},
                    {"type": "image", "image": images[1]},
                ],
            }
        ],
        32,
    )
    assert result == '{"ok":true}'
    assert [p["type"] for p in seen["messages"][0]["content"]] == ["text", "image", "text", "image"]
    assert [im.getpixel((0, 0)) for im in seen["image"]] == [(255, 0, 0), (0, 0, 255)]
    assert seen["image"][0].size == (768, 384)
    assert images[0].size == (900, 450)
    assert seen["template"]["enable_thinking"] is False
    assert seen["max_tokens"] == 32 and seen["temperature"] == 0


def test_mlx_load_pins_model_revision_and_text_only_generation(monkeypatch):
    seen = {}
    processor = SimpleNamespace(apply_chat_template=lambda *a, **k: "text prompt")

    def load(name, **kwargs):
        seen.update(name=name, **kwargs)
        return object(), processor

    def generate(*args, **kwargs):
        assert kwargs["image"] is None
        return SimpleNamespace(text="hello")

    monkeypatch.setattr("nyx.mlx_runtime.platform.system", lambda: "Darwin")
    monkeypatch.setattr("nyx.mlx_runtime.platform.machine", lambda: "arm64")
    monkeypatch.setitem(sys.modules, "mlx_vlm", SimpleNamespace(load=load, generate=generate))
    runtime = MlxRuntime()
    assert seen == {"name": MODEL, "revision": REVISION, "trust_remote_code": False}
    assert runtime.generate([{"role": "user", "content": "Hi"}], 8) == "hello"
