"""Reusable local acknowledgement clips; LiveKit owns streaming speech."""

import base64
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
    voice = (
        ("ritu_hi_conversation" if re.search(r"[\u0900-\u097f]", text) else "ritu_en_reels")
        if model == "bulbul:v4-flash"
        else "Kore"
    )
    key = hashlib.sha256(f"{model}/{voice}/24000/v1/{text}".encode()).hexdigest()[:24]
    return Path(root) / "voice-acknowledgements" / f"{key}.wav"


def prepare_acknowledgements(root):
    from nyx.voice import CloudVoice

    provider = CloudVoice()

    def prepare(text):
        path = acknowledgement_path(root, provider.tts_model, text)
        if not path.exists():
            audio = base64.b64decode(provider.speak(text))
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(audio)
            temporary.replace(path)
        return str(path)

    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(
            pool.map(prepare, [text for texts in ACKNOWLEDGEMENTS.values() for text in texts])
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", required=True, metavar="DATA_DIR")
    args = parser.parse_args()
    print(f"Prepared {len(prepare_acknowledgements(args.prepare))} acknowledgement clips.")
