"""Frozen manifest replay of automatic regions and independent entity geometry."""

import argparse
import hashlib
import json
import platform
import time
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

from PIL import Image

from nyx.events import region_motion
from nyx.observation import departure_action
from nyx.verification import LocalVerifier


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    args.output.mkdir(parents=True, exist_ok=False)
    # Freeze inputs and protocol before loading either model; no case-specific policy.
    protocol = {
        "manifest": manifest,
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "scope": "Reused staged room-exit development diagnostics, not held-out home-exit accuracy",
        "method": "Actual local detector and VLM; forward inference, reverse same-region geometry diagnostic; no hardware/cloud/voice",
        "scoring": "Report positives on three exit proxies and false actions on four labelled negatives; two ambiguous cases unscored",
        "date": datetime.now(UTC).isoformat(),
    }
    (args.output / "protocol.json").write_text(json.dumps(protocol, indent=2))
    model = LocalVerifier()
    original = model.generate_json
    case_name = None

    def record(messages, max_tokens=240):
        raw = original(messages, max_tokens)
        with (args.output / "raw.jsonl").open("a") as file:
            file.write(json.dumps({"case": case_name, "max_tokens": max_tokens, "raw": raw}) + "\n")
        return raw

    model.generate_json = record
    results = {
        "platform": platform.platform(),
        "runtime": {
            name: version(name) for name in ["torch", "torchvision", "transformers", "pillow"]
        },
        "model": model.fingerprint,
        "protocol": protocol,
        "cases": [],
    }
    # These times order the already-selected offline images; never their capture dates.
    base = datetime(2026, 10, 20, tzinfo=UTC)
    burst = {
        "activity": {"qualified": True},
        "times": [(base + timedelta(seconds=x)).isoformat() for x in [0, 2, 4]],
    }
    requests = [
        {
            "id": "offline-policy-check",
            "state": "armed",
            "created_at": (base - timedelta(seconds=1)).isoformat(),
        }
    ]
    for case in manifest["cases"]:
        case_name = case["name"]
        paths = sorted(Path(case["frames"]).glob("*.jpg"))
        chosen = [paths[index] for index in case["indices"]]
        images = [Image.open(path).convert("RGB") for path in chosen]
        for image in images:
            image.thumbnail((640, 360))
        started = time.perf_counter()
        judgment = model.inspect_departure(images)
        row = {
            **case,
            "files": [
                {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in chosen
            ],
            "judgment": judgment,
            "seconds": time.perf_counter() - started,
            "decision": departure_action(burst, judgment, requests),
        }
        region = judgment.get("region")
        row["reversed_same_region_motion"] = region_motion(
            region["box"] if region else None, list(reversed(judgment["entities"]))
        )
        results["cases"].append(row)
        print(
            json.dumps(
                {
                    "name": case_name,
                    "region": region,
                    "relation": judgment["motion"]["relation"],
                    "act": row["decision"]["act"],
                    "reason": row["decision"]["reason"],
                    "seconds": row["seconds"],
                }
            ),
            flush=True,
        )
        (args.output / "results.json").write_text(json.dumps(results, indent=2))
    results["summary"] = {
        "exit_proxy_actions": sum(
            row["decision"]["act"] for row in results["cases"] if row["expected"] == "departure"
        ),
        "negative_false_actions": sum(
            row["decision"]["act"] for row in results["cases"] if row["expected"] == "no_departure"
        ),
        "ambiguous_actions": sum(
            row["decision"]["act"] for row in results["cases"] if row["expected"] == "uncertain"
        ),
    }
    (args.output / "results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
