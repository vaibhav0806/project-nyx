"""Small public-fixture visual checks, separate from planner and device capture."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from PIL import Image

from nyx.verification import LocalVerifier


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    model = LocalVerifier()
    cases = [
        ("multiple-generic", "000.png", "television remote control", "ambiguous"),
        (
            "multiple-right",
            "000.png",
            "television remote control on the right of the picture",
            "visible",
        ),
        ("single-crop", "007.png", "television remote control", "visible"),
        ("empty", "009.png", "television remote control", "not_visible"),
    ]
    results = {
        "model": model.fingerprint,
        "scope": "Reused public development images; no planner, devices or cloud",
        "cases": [],
    }
    generate = model.generate_json
    raw = []

    def record(messages, max_tokens=240):
        text = generate(messages, max_tokens)
        raw.append(text)
        return text

    model.generate_json = record
    for name, filename, query, expected in cases:
        path = args.fixture / "input_frames" / filename
        started = time.perf_counter()
        with Image.open(path) as source:
            judgment = model.inspect(source.convert("RGB"), query)
        actual = "ambiguous" if judgment.get("ambiguous") else judgment["visibility"]
        row = {
            "name": name,
            "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "query": query,
            "expected": expected,
            "judgment": judgment,
            "raw": raw[-1],
            "passed": actual == expected,
            "seconds": time.perf_counter() - started,
        }
        results["cases"].append(row)
        (args.output / "results.json").write_text(json.dumps(results, indent=2))
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
