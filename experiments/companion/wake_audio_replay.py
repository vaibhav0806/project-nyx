"""Offline macOS-generated speech through the actual cached wake recognizer; no hardware."""

import argparse
import json
import platform
import subprocess
import time
from pathlib import Path

from nyx.voice import WAKE_MODEL, WAKE_REVISION, Voice, WakeRecognizer

CASES = [
    ("wake-keys", "Hey Nyx, where are my keys?", True),
    ("wake-glasses", "Nyx, can you see my glasses?", True),
    ("ordinary-question", "Hello, where is my phone?", False),
    ("ordinary-statement", "Please put the keys on the table.", False),
    ("near-name", "Hey Nick, are you coming?", False),
]


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "model": WAKE_MODEL,
        "revision": WAKE_REVISION,
        "platform": platform.platform(),
        "tts": "macOS installed default voice via say -o, no speaker playback",
        "cases": [],
        "limitations": "Generated English speech at two rates, first three-second window, not humans/accents, acoustic echo, noise or Hindi STT. Near-name confusion is measured without changing aliases. Cached local inference only; no camera/microphone or cloud upload.",
    }
    recognizer = WakeRecognizer()
    for rate in [160, 210]:
        for name, text, expected in CASES:
            identifier = f"{name}-{rate}"
            audio = output / (identifier + ".aiff")
            pcm = output / (identifier + ".pcm")
            subprocess.run(["say", "-r", str(rate), "-o", str(audio), text], check=True, timeout=30)
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-n",
                    "-i",
                    str(audio),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-f",
                    "s16le",
                    str(pcm),
                ],
                check=True,
                timeout=30,
            )
            samples = pcm.read_bytes()
            window = samples[:96000]
            transcript = []

            def recognize(data, transcript=transcript):
                transcript.append(recognizer(data))
                return transcript[-1]

            voice = Voice(output / identifier, None, recognizer=recognize)
            token = voice.start()["token"]
            began = time.perf_counter()
            response = voice.probe(token, window)
            detected = response.get("state") == "activated"
            result["cases"].append(
                {
                    "id": identifier,
                    "text": text,
                    "expected_wake": expected,
                    "detected": detected,
                    "correct": detected == expected,
                    "recognized": transcript,
                    "source_seconds": len(samples) / 32000,
                    "window_seconds": len(window) / 32000,
                    "elapsed_ms": round((time.perf_counter() - began) * 1000),
                    "response_state": response.get("state"),
                }
            )
            voice.stop(token)
            (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    return {
        "correct": sum(row["correct"] for row in result["cases"]),
        "total": len(result["cases"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output)))
