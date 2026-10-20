"""Probe whether two-image comparison can distinguish the selected remote from a lookalike.

Research only: a failure rejects automatic identity claims, not parsing strictness.
"""

import argparse
import json
import time
from pathlib import Path

from PIL import Image

from nyx.verification import LocalVerifier, parse_judgment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=False)
    fixture = args.fixture / "input_frames"
    model = LocalVerifier()
    prompt = """Compare two images. Image 1 is a reference: the user selected the television remote control on the RIGHT of that image. Image 2 is a historical candidate. Look for that selected object's distinctive appearance in image 2. Its position can change; do not require it to remain on the right. Category similarity alone is not enough. If there are indistinguishable lookalikes, or the visible detail cannot distinguish them, answer uncertain. Never choose the OTHER object from image 1. Return only JSON: description (observed distinguishing features/comparison), matching_count (integer), ambiguous (boolean), visibility (visible/not_visible/uncertain), location (location in image 2 only, or empty string). visible requires enough visible distinctive detail to distinguish the selected object from the other remote. Do not claim physical identity from generic similarity."""
    results = []
    for name, frame in [
        ("same-scene", "000.png"),
        ("mirrored-scene", "004.png"),
        ("other-remote-crop", "007.png"),
    ]:
        start = time.perf_counter()
        with Image.open(fixture / "000.png") as a, Image.open(fixture / frame) as b:
            raw = model.generate_json(
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "REFERENCE IMAGE 1"},
                            {"type": "image", "image": a.convert("RGB")},
                            {"type": "text", "text": "HISTORICAL CANDIDATE IMAGE 2"},
                            {"type": "image", "image": b.convert("RGB")},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                240,
            )
        row = {
            "case": name,
            "raw": raw,
            "judgment": parse_judgment(raw),
            "seconds": time.perf_counter() - start,
        }
        results.append(row)
        (root / "results.json").write_text(
            json.dumps({"model": model.fingerprint, "cases": results}, indent=2)
        )
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
