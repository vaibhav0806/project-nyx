"""Actual API responses to unsupported actions; predeclared criteria, inline answer audit."""

import argparse
import json
from pathlib import Path

from experiments.companion.budget import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.household_workflows import digest, request_turn
from nyx.perception import CloudEncoder
from nyx.verification import CloudVerifier


def run(cases_path, output, max_spend):
    cases = json.loads(cases_path.read_text())
    if {row["id"] for row in cases} != {
        "event-reminder",
        "time-reminder-hi",
        "contact-call",
        "camera-action",
    }:
        raise ValueError("Frozen capability conditions changed")
    output.mkdir(parents=True, exist_ok=False)
    client = BudgetedClient(max_spend, max_requests=48)
    encoder, verifier = CloudEncoder(client), CloudVerifier(client)
    report = {
        "status": "running",
        "cases_sha256": digest(cases_path),
        "budget_before": client.initial,
        "verifier": verifier.fingerprint,
        "cases": [{**case, "status": "not_run"} for case in cases],
        "limitations": "Synthetic requests through real native API/memory. No actual hardware, scheduled actions or external contacts. Job completion is not semantic success; criteria require inline answer audit.",
    }

    def checkpoint():
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )

    checkpoint()
    try:
        for row in report["cases"]:
            job = request_turn(output / row["id"], encoder, verifier, row["message"])
            row.update(status=job["status"], job=job)
            checkpoint()
            if job["status"] != "succeeded":
                raise ValueError("Capability transport failed; inspect before more spending")
        report["status"] = "complete"
    finally:
        if report["status"] != "complete":
            report["status"] = "failed"
        report["budget_after"] = budget_snapshot(client)
        checkpoint()
    return {"status": report["status"], "cases": len(cases), "semantic_audit": "required"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases", type=Path, default=Path(__file__).with_name("capability_cases.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.10)
    args = parser.parse_args()
    print(json.dumps(run(args.cases, args.output, args.max_spend)))
