"""Reusable local acknowledgement clips; LiveKit owns streaming speech."""

import asyncio
import hashlib
import json
import re
import wave
from pathlib import Path

VOICES = {"en": "sanchita_en_companion", "hi": "shalini_hi_companion"}


def speech_options(language):
    """One synthesis configuration for replies and prepared lookup audio."""
    return {
        "model": "bulbul:v4-flash",
        "speaker": VOICES[language],
        "target_language_code": "hi-IN" if language == "hi" else "en-IN",
        "speech_sample_rate": 24000,
        "output_audio_codec": "linear16",
        "enable_preprocessing": True,
        "pitch": 0.0,
        "pace": 1.0,
        "loudness": 1.0,
        "temperature": 0.6,
    }


ACKNOWLEDGEMENTS = {
    "en": (
        "Let me check that for you.",
        "Let me take a look.",
        "One moment, I’ll check.",
        "I’ll look back for you.",
        "Let me see what I can find.",
        "Just a moment, I’m looking.",
    ),
    "hi": (
        "एक पल, मैं देखती हूँ।",
        "अभी देखकर बताती हूँ।",
        "ज़रा देखने दीजिए।",
        "एक मिनट, मैं ढूँढती हूँ।",
        "रुकिए, मैं देख लेती हूँ।",
        "मैं पिछली रिकॉर्डिंग देखती हूँ।",
    ),
}


def acknowledgement_path(root, model, text):
    if model == "bulbul:v4-flash":
        language = "hi" if re.search(r"[\u0900-\u097f]", text) else "en"
        identity = json.dumps(
            {**speech_options(language), "transport": "livekit-sarvam-websocket-v2"},
            sort_keys=True,
        )
    else:
        identity = f"{model}/Kore/24000/v1"
    key = hashlib.sha256(f"{identity}/{text}".encode()).hexdigest()[:24]
    return Path(root) / "voice-acknowledgements" / f"{key}.wav"


def prepare_acknowledgements(root):
    return asyncio.run(_prepare_acknowledgements(root))


async def _prepare_acknowledgements(root):
    import aiohttp
    from livekit.agents import APIConnectOptions
    from livekit.plugins import sarvam

    paths = []
    async with aiohttp.ClientSession() as http:
        for language, texts in ACKNOWLEDGEMENTS.items():
            options = speech_options(language)
            tts = sarvam.TTS(http_session=http, **options)
            try:
                for text in texts:
                    path = acknowledgement_path(root, options["model"], text)
                    if not path.exists():
                        stream = tts.stream(conn_options=APIConnectOptions(max_retry=0))
                        try:
                            stream.push_text(text)
                            stream.end_input()
                            pcm = bytearray()
                            async with asyncio.timeout(25):
                                async for event in stream:
                                    frame = event.frame
                                    if frame.sample_rate != 24000 or frame.num_channels != 1:
                                        raise ValueError("Unexpected acknowledgement audio format")
                                    pcm.extend(frame.data.cast("B"))
                                    if len(pcm) > 4 * 1024**2:
                                        raise ValueError("Acknowledgement audio exceeds limit")
                            if not pcm or len(pcm) % 2:
                                raise ValueError("Invalid acknowledgement audio")
                            path.parent.mkdir(parents=True, exist_ok=True)
                            temporary = path.with_suffix(".tmp")
                            with wave.open(str(temporary), "wb") as audio:
                                audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                                audio.writeframes(pcm)
                            temporary.replace(path)
                        finally:
                            await stream.aclose()
                    paths.append(str(path))
            finally:
                await tts.aclose()
    return paths


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", required=True, metavar="DATA_DIR")
    args = parser.parse_args()
    print(f"Prepared {len(prepare_acknowledgements(args.prepare))} acknowledgement clips.")
