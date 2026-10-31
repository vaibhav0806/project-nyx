"""Bounded OpenRouter transport; credentials and raw provider errors stay server-side."""

import base64
import json
import logging
import os
import re
import time
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

    def request(self, path, payload, *, binary=False, version="v1"):
        started = time.perf_counter()
        outcome = "failed"
        body = {**payload, "provider": {"data_collection": "deny", **payload.get("provider", {})}}
        request = Request(
            "https://openrouter.ai/api/" + version + "/" + path,
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
                outcome = "succeeded"
                return raw
            result = json.loads(raw)
            if not isinstance(result, dict) or "error" in result:
                raise CloudError("Cloud provider returned an unsuccessful response.")
            outcome = "succeeded"
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

        finally:
            logging.getLogger("uvicorn.error").info(
                "cloud_request path=%s model=%s outcome=%s elapsed_ms=%d",
                path,
                payload.get("model", "unspecified"),
                outcome,
                round((time.perf_counter() - started) * 1000),
            )

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

    def stream_text(self, messages, model, cancelled=lambda: False):
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": 700,
            "temperature": 0,
            "reasoning": {"effort": "low", "exclude": True},
            "stream_options": {"include_usage": True},
            "provider": {"data_collection": "deny"},
        }
        request = Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"},
        )
        finished = False
        size = 0
        try:
            with self.transport(request, timeout=30) as response:
                while not cancelled():
                    line = response.readline(65537)
                    if not line:
                        break
                    size += len(line)
                    if len(line) > 65536 or size > 1024**2:
                        raise CloudError("Cloud text stream exceeded its limit.")
                    if not line.startswith(b"data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == b"[DONE]":
                        break
                    event = json.loads(raw)
                    if "error" in event:
                        raise CloudError("Cloud text stream failed.")
                    if event.get("usage"):
                        self.usage.append(event["usage"])
                        self.usage = self.usage[-100:]
                    for choice in event.get("choices", []):
                        text = choice.get("delta", {}).get("content")
                        if text:
                            if not isinstance(text, str):
                                raise CloudError("Invalid cloud text stream.")
                            yield text
                        reason = choice.get("finish_reason")
                        if reason:
                            if reason != "stop":
                                raise CloudError("Cloud answer did not finish.")
                            finished = True
            if not cancelled() and not finished:
                raise CloudError("Cloud text stream ended before the answer finished.")
        except HTTPError as exc:
            raise CloudError(f"OpenRouter streaming request failed ({exc.code}).") from None
        except (URLError, TimeoutError, OSError, ValueError, TypeError, AttributeError) as exc:
            if isinstance(exc, CloudError):
                raise
            raise CloudError("Cloud text stream failed. Please retry.") from None

    def stream_pcm(self, payload, cancelled=lambda: False):
        request = Request(
            "https://openrouter.ai/api/v1/audio/speech",
            data=json.dumps({**payload, "provider": {"data_collection": "deny"}}).encode(),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"},
        )
        size, pending = 0, b""
        try:
            with self.transport(request, timeout=30) as response:
                content_type = response.headers.get("Content-Type", "").lower()
                if not content_type.startswith(("audio/pcm", "application/octet-stream")):
                    raise CloudError("Speech did not return PCM audio.")
                rate = re.search(r"rate=(\d+)", content_type)
                channels = re.search(r"channels=(\d+)", content_type)
                if (rate and rate[1] != "24000") or (channels and channels[1] != "1"):
                    raise CloudError("Speech returned an unsupported PCM format.")
                while not cancelled():
                    chunk = response.read1(4096)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > 4 * 1024**2:
                        raise CloudError("Speech stream exceeded its limit.")
                    pending += chunk
                    complete = len(pending) // 2 * 2
                    if complete:
                        yield pending[:complete]
                        pending = pending[complete:]
            if not cancelled() and (not size or pending):
                raise CloudError("Speech stream ended with invalid audio.")
        except HTTPError as exc:
            raise CloudError(f"OpenRouter speech request failed ({exc.code}).") from None
        except (URLError, TimeoutError, OSError):
            raise CloudError("Cloud speech stream failed. Please retry.") from None
