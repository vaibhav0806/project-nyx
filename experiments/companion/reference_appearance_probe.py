"""Single-call appearance controls using two explicitly sourced public bottle photographs."""

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
    for source in manifest["sources"].values():
        path = (args.data / source["file"]).resolve()
        if not path.is_relative_to(args.data.resolve()) or digest(path) != source["sha256"]:
            raise ValueError("Frozen public appearance source changed")
    args.output.mkdir(parents=True, exist_ok=False)
    client = BudgetedClient(0.08, max_requests=4)
    verifier = (SceneVerifier if args.contract == "scene" else CloudVerifier)(client)
    report = {
        "status": "running",
        "contract": args.contract,
        "verifier": verifier.fingerprint,
        "manifest_sha256": digest(args.data / "manifest.json"),
        "budget_before": client.initial,
        "candidate_source_sha256": digest(Path(__file__).with_name("scene_contract_probe.py")),
        "cases": [],
        "limitations": "Same-photo positives and visibly different same-category negatives. Exact appearance controls, not cross-day identity accuracy or natural user acceptance; source capture times unknown.",
    }
    try:
        for case in manifest["cases"]:
            with (
                Image.open(args.data / manifest["sources"][case["candidate"]]["file"]) as candidate,
                Image.open(args.data / manifest["sources"][case["reference"]]["file"]) as reference,
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
        "cases": 4,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contract", choices=["current", "scene"], required=True)
    print(json.dumps(run(parser.parse_args())))
