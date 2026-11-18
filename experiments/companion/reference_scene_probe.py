"""One-call paired-image physical/depiction checks on existing public scene conditions."""

import argparse
import json
from pathlib import Path

from PIL import Image

from experiments.companion.budget import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.household_workflows import digest
from experiments.companion.scene_contract_probe import SceneVerifier
from experiments.companion.visual_cases import score
from nyx.verification import CloudVerifier


def run(args):
    manifest = json.loads((args.data / "manifest.json").read_text())
    cases = [c for c in manifest["cases"] if c["split"] == args.split]
    originals = {c["source_id"]: c for c in cases if c["condition"] == "original"}
    if len(cases) != 12 or len(originals) != 4:
        raise ValueError("Expected frozen source-separated public conditions")
    for case in cases:
        path = (args.data / case["file"]).resolve()
        if not path.is_relative_to(args.data.resolve()) or digest(path) != case["sha256"]:
            raise ValueError("Public source changed")
    args.output.mkdir(parents=True, exist_ok=False)
    client = BudgetedClient(0.10, max_requests=12)
    verifier = (SceneVerifier if args.contract == "scene" else CloudVerifier)(client)
    report = {
        "status": "running",
        "contract": args.contract,
        "candidate_source_sha256": digest(Path(__file__).with_name("scene_contract_probe.py")),
        "verifier": verifier.fingerprint,
        "manifest_sha256": digest(args.data / "manifest.json"),
        "budget_before": client.initial,
        "cases": [],
        "limitations": "Same source photo as an appearance reference; candidate original or synthetic depiction. One actual model call per case, no private inputs or hardware. Scope/shape diagnostic, not cross-day instance identity or household accuracy.",
    }
    try:
        for case in cases:
            with (
                Image.open(args.data / case["file"]) as candidate,
                Image.open(args.data / originals[case["source_id"]]["file"]) as reference,
            ):
                result = verifier.inspect_reference(candidate, reference, case["query"])
            report["cases"].append({**case, "judgment": result, **score(case["expected"], result)})
        report["status"] = "complete"
    finally:
        if report["status"] != "complete":
            report["status"] = "failed"
        report["provider_usage"] = client.usage
        report["budget_after"] = budget_snapshot(client)
        (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    return {
        "status": report["status"],
        "correct": sum(c["correct"] for c in report["cases"]),
        "cases": len(cases),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "holdout"], default="holdout")
    parser.add_argument("--contract", choices=["current", "scene"], required=True)
    print(json.dumps(run(parser.parse_args())))
