"""Paid category/count verification comparison on a frozen permitted public manifest."""

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from PIL import Image

from experiments.companion.correction_replay import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.visual_cases import build_cases, score
from nyx.verification import CloudVerifier

MODELS = {"lite": "google/gemini-3.5-flash-lite", "flash": "google/gemini-3.5-flash"}


def freeze(data, output):
    manifest = json.loads((data / "manifest.json").read_text())
    annotation = data / "instances_val2017.json"
    if hashlib.sha256(annotation.read_bytes()).hexdigest() != manifest["annotations_sha256"]:
        raise ValueError("Annotation revision changed")
    cases = build_cases(manifest["images"], json.loads(annotation.read_text())["annotations"])
    with output.open("x") as handle:
        json.dump({"version": 1, "cases": cases}, handle, indent=2)
        handle.write("\n")


def run(data, cases_path, output, split, model, max_spend):
    cases = [row for row in json.loads(cases_path.read_text())["cases"] if row["split"] == split]
    if not cases or len(cases) > 96:
        raise ValueError("Invalid frozen split size")
    # Validate every selected source before the first paid request.
    for case in cases:
        path = (data / "images" / case["file_name"]).resolve()
        if not path.is_relative_to((data / "images").resolve()):
            raise ValueError("Source escapes public fixture")
        if hashlib.sha256(path.read_bytes()).hexdigest() != case["sha256"]:
            raise ValueError("Source bytes changed")
    output.mkdir(parents=True, exist_ok=False)
    client = BudgetedClient(max_spend, max_requests=96)
    verifier = CloudVerifier(client=client, model=MODELS[model])
    if verifier.visual_confirmation:
        raise ValueError("Disable extra confirmation for the single-pass comparison")
    result = {
        "status": "running",
        "split": split,
        "model": verifier.fingerprint,
        "manifest_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "budget_before": client.initial,
        "cases": [{**case, "status": "not_run"} for case in cases],
        "limitations": "Previously used public photos, new verification conditions. Annotation category/count proxies may be incomplete or tiny/occluded. No instance identity, location wording, natural-video or real household acceptance score. Photo times unknown. Failures remain in denominator.",
    }

    def checkpoint():
        result["provider_usage"] = client.usage
        result["summary"] = {
            "total": len(cases),
            "complete": sum(row["status"] == "complete" for row in result["cases"]),
            "correct_proxy": sum(row.get("correct", False) for row in result["cases"]),
            "unsafe_positive_proxy": sum(
                row.get("unsafe_positive", False) for row in result["cases"]
            ),
            "outcomes": dict(
                Counter(
                    row.get("judgment", {}).get("visibility", row["status"])
                    for row in result["cases"]
                )
            ),
        }
        (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")

    checkpoint()
    try:
        for case in result["cases"]:
            began = time.perf_counter()
            with Image.open(data / "images" / case["file_name"]) as image:
                judgment = verifier.inspect(image, case["query"])
            case.update(
                status="complete",
                judgment=judgment,
                elapsed_ms=round((time.perf_counter() - began) * 1000),
                **score(case["expected"], judgment),
            )
            checkpoint()
        result["status"] = "complete"
    finally:
        if result["status"] != "complete":
            result["status"] = "failed"
        result["budget_after"] = budget_snapshot(client)
        checkpoint()
    return result["summary"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--model", choices=MODELS, default="lite")
    parser.add_argument("--max-spend", type=float, default=0.10)
    args = parser.parse_args()
    if args.freeze:
        freeze(args.data, args.cases)
    else:
        if args.output is None:
            parser.error("--output is required for evaluation")
        print(
            json.dumps(
                run(args.data, args.cases, args.output, args.split, args.model, args.max_spend)
            )
        )


if __name__ == "__main__":
    main()
