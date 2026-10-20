"""Small Apple Silicon generation boundary; imports/weights load only on construction."""

import platform

MODEL = "mlx-community/Qwen3.5-2B-8bit"
REVISION = "562fb8ea19bbe7565a3ddf5b7d49899ea2c88d2b"


class MlxRuntime:
    def __init__(self):
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise ValueError("The selected MLX model requires Apple Silicon")
        from mlx_vlm import load

        self.model, self.processor = load(MODEL, revision=REVISION, trust_remote_code=False)

    def generate(self, messages, max_tokens):
        from mlx_vlm import generate

        images, prepared = [], []
        for message in messages:
            content = message["content"]
            if isinstance(content, str):
                prepared.append(message)
                continue
            parts = []
            for part in content:
                if part["type"] == "image":
                    image = part["image"].convert("RGB")
                    image.thumbnail((768, 768))
                    images.append(image)
                    parts.append({"type": "image"})
                elif part["type"] == "text":
                    parts.append({"type": "text", "text": part["text"]})
                else:
                    raise ValueError("Unsupported local model input")
            prepared.append({**message, "content": parts})
        prompt = self.processor.apply_chat_template(
            prepared, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        return generate(
            self.model,
            self.processor,
            prompt,
            image=images or None,
            max_tokens=max_tokens,
            temperature=0.0,
            enable_thinking=False,
            verbose=False,
        ).text
