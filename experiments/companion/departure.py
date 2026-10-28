"""Local sequence judgments on explicitly labelled, permitted evaluation clips."""

import argparse
import json
import platform
import resource
import time
from importlib.metadata import version
from pathlib import Path

from PIL import Image

from nyx.attention import sequence_changed
from nyx.verification import LocalVerifier


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reverse-check",
        action="store_true",
        help="Diagnose direction sensitivity by also inspecting every sequence backwards",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.manifest.read_text())
    model = LocalVerifier()
    results = {
        "platform": platform.platform(),
        "runtime": {name: version(name) for name in ["torch", "transformers", "pillow"]},
        "model": model.fingerprint,
        "load_seconds": model.load_seconds,
        "manifest": manifest,
        "reverse_check": args.reverse_check,
        "cases": [],
    }
    original = model.generate_json

    def record(messages, max_tokens=180):
        raw = original(messages, max_tokens)
        with (args.output / "raw.jsonl").open("a") as file:
            file.write(json.dumps({"raw": raw}) + "\n")
        return raw

    model.generate_json = record
    for case in manifest["cases"]:
        folder = Path(case["frames"])
        paths = sorted(folder.glob("*.jpg"))
        images = [Image.open(paths[index]).convert("RGB") for index in case["indices"]]
        for image in images:
            image.thumbnail((640, 360))
        started = time.perf_counter()
        judgment = model.inspect_departure(images)
        row = {
            **case,
            "judgment": judgment,
            "seconds": time.perf_counter() - started,
            "motion_selected": sequence_changed(images),
        }
        if args.reverse_check:
            started = time.perf_counter()
            row["reversed_judgment"] = model.inspect_departure(list(reversed(images)))
            row["reversed_seconds"] = time.perf_counter() - started
            # A diagnostic only: a temporal classifier should change its decision on
            # reversed exits. Do not silently turn this into another runtime call.
            row["direction_sensitive_positive"] = (
                judgment["departure"]
                and not judgment["uncertain"]
                and not row["reversed_judgment"]["departure"]
                and not row["reversed_judgment"]["uncertain"]
            )
        if case["expected"] != "uncertain":
            row["matched"] = judgment["departure"] == (case["expected"] == "departure")
        results["cases"].append(row)
        results["process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(json.dumps(row), flush=True)
        (args.output / "results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
