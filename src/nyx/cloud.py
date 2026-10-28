"""Bounded OpenRouter transport; credentials and raw provider errors stay server-side."""

import base64
import json
import os
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CloudError(ValueError):
    pass


def image_part(image, side=768):
    image = image.convert("RGB")
    image.thumbnail((side, side))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return {
        "type": "image_url",
        "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
        },
    }


class OpenRouter:
    def __init__(self, key=None, transport=urlopen):
        self.key = key or os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not self.key:
            raise CloudError("Configure OPENROUTER_API_KEY in the server environment.")
        self.transport = transport
        self.usage = []

    def request(self, path, payload, *, binary=False):
        body = {**payload, "provider": {"data_collection": "deny", **payload.get("provider", {})}}
        request = Request(
            "https://openrouter.ai/api/v1/" + path,
            data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"},
        )
        try:
            with self.transport(request, timeout=45) as response:
                raw = response.read(8 * 1024**2 + 1)
            if len(raw) > 8 * 1024**2:
                raise CloudError("Cloud response exceeded the size limit.")
            if binary:
                if not raw or raw.lstrip().startswith((b"{", b"<")):
                    raise CloudError("Cloud speech returned an invalid audio response.")
                return raw
            result = json.loads(raw)
            if not isinstance(result, dict) or "error" in result:
                raise CloudError("Cloud provider returned an unsuccessful response.")
            self.usage.append(result.get("usage", {}))
            self.usage = self.usage[-100:]
            return result
        except HTTPError as exc:
            raise CloudError(
                f"OpenRouter request failed ({exc.code}). Check credits, key, model availability or provider status."
            ) from None
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            if isinstance(exc, CloudError):
                raise
            raise CloudError("Cloud request failed. Check the connection and retry.") from None

    def generate(self, messages, model, max_tokens):
        converted = []
        for message in messages:
            content = message["content"]
            if isinstance(content, list):
                content = [image_part(p["image"]) if p["type"] == "image" else p for p in content]
            converted.append({**message, "content": content})
        result = self.request(
            "chat/completions",
            {
                "model": model,
                "messages": converted,
                "max_tokens": max(1024, max_tokens),
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "reasoning": {"effort": "low", "exclude": True},
            },
        )
        try:
            choice = result["choices"][0]
            raw = choice["message"]["content"]
            if choice.get("finish_reason") != "stop" or not isinstance(raw, str) or not raw.strip():
                raise ValueError
            return raw
        except (KeyError, TypeError, IndexError, ValueError):
            raise CloudError("Cloud model did not finish a usable answer. Please retry.") from None
