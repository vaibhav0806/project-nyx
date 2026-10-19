"""Opt-in local VLM comparison on the existing permitted public-image fixture."""

import argparse
import gc
import json
import time
from pathlib import Path

from PIL import Image

from nyx.verification import LocalVerifier

CASES = [
    ("000.png", "a television remote control", "visible"),
    ("001.png", "a television remote control", "not_visible"),
    ("000.png", "a set of house keys", "not_visible"),
    ("001.png", "a cup of coffee", "visible"),
    ("002.png", "a camera on a tripod", "visible"),
    ("006.png", "a television remote control", "not_visible"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output file")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for name in ["smol", "qwen"]:
        try:
            verifier = LocalVerifier(model=name)
            rows = []
            memory_samples = []
            for file, query, expected in CASES:
                with Image.open(args.frames / file) as image:
                    started = time.perf_counter()
                    result = verifier.inspect(image, query)
                row = {
                    "file": file,
                    "query": query,
                    "expected": expected,
                    "result": result,
                    "seconds": time.perf_counter() - started,
                }
                import torch

                if torch.backends.mps.is_available():
                    memory_samples.append(
                        {
                            "model_allocation_gib": torch.mps.current_allocated_memory() / 1024**3,
                            "driver_allocation_gib": torch.mps.driver_allocated_memory() / 1024**3,
                        }
                    )
                rows.append(row)
                print(json.dumps({"model": name, **row}), flush=True)
            results.append(
                {
                    "model": name,
                    "fingerprint": verifier.fingerprint,
                    "device": verifier.device,
                    "load_seconds": verifier.load_seconds,
                    "cases": rows,
                    "post_inference_mps_samples": memory_samples,
                }
            )
            del verifier
            gc.collect()
            import torch

            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception as exc:  # noqa: BLE001 — record one model failure and continue the comparison
            results.append({"model": name, "error": str(exc)})
            print(json.dumps(results[-1]), flush=True)
        args.output.write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
