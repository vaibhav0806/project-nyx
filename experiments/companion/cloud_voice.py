"""Paid, opt-in cloud voice API smoke using supplied synthetic audio and a drawn image."""

import argparse
import base64
import json
import time
import wave
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from nyx.app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audio", type=Path, required=True, help="Synthetic Hey Nyx glasses question"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with wave.open(str(args.audio)) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2)
        pcm = wav.readframes(wav.getnframes())
    image = Image.new("RGB", (512, 384), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((100, 150, 230, 240), outline="black", width=8)
    draw.ellipse((260, 150, 390, 240), outline="black", width=8)
    draw.line((230, 185, 260, 185), fill="black", width=8)
    draw.line((100, 180, 60, 130), fill="black", width=8)
    draw.line((390, 180, 430, 130), fill="black", width=8)
    encoded = BytesIO()
    image.save(encoded, "PNG")
    started = time.monotonic()
    with TestClient(create_app(args.output / "workspace")) as client:
        token = client.post("/api/voice/session").json()["token"]
        headers = {"x-nyx-voice": token}
        response = client.post("/api/voice/utterance", headers=headers, content=pcm)
        response.raise_for_status()
        turn = response.json()
        assert turn["state"] == "question", turn
        response = client.post(
            "/api/agent",
            headers=headers,
            json={
                "message": turn["transcript"],
                "request_id": "cloud-voice-smoke",
                "voice_turn_id": turn["id"],
                "snapshot": base64.b64encode(encoded.getvalue()).decode(),
                "captured_at": datetime.now(UTC).isoformat(),
            },
        )
        response.raise_for_status()
        job_id = response.json()["id"]
        until = time.monotonic() + 90
        while time.monotonic() < until:
            job = client.get("/api/jobs/" + job_id).json()
            if job["status"] in {"succeeded", "failed"}:
                break
            client.post("/api/voice/heartbeat", headers=headers)
            time.sleep(0.2)
        assert job["status"] == "succeeded", job
        response = client.post(
            "/api/voice/reply", headers=headers, json={"turn_id": turn["id"], "job_id": job_id}
        )
        response.raise_for_status()
        reply = response.json()
        raw = base64.b64decode(reply.pop("audio"))
        with wave.open(BytesIO(raw)) as wav:
            duration = wav.getnframes() / wav.getframerate()
            assert duration > 0.1
        (args.output / "reply.wav").write_bytes(raw)
        response = client.delete("/api/voice/session", headers=headers)
        response.raise_for_status()
        result = {
            "passed": True,
            "turn": turn,
            "job": job,
            "reply": reply,
            "seconds": time.monotonic() - started,
            "audio_seconds": duration,
            "limits": "Synthetic audio/image, real local wake and cloud STT/agent/vision/TTS. No devices or playback; not household accuracy.",
        }
        (args.output / "results.json").write_text(json.dumps(result, indent=2))
        print(
            json.dumps(
                {
                    "passed": True,
                    "transcript": turn["transcript"],
                    "answer": reply["answer"],
                    "seconds": result["seconds"],
                }
            )
        )


if __name__ == "__main__":
    main()
