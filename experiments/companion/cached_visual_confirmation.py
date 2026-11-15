"""Isolate positive corroboration on preserved real first-pass judgments; public images only."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from PIL import Image

from experiments.companion.correction_replay import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.visual_cases import score
from nyx.verification import CloudVerifier


class AuditClient(BudgetedClient):
    last_response = None

    def generate(self, *args, **kwargs):
        raw = super().generate(*args, **kwargs)
        self.last_response = raw
        return raw


def run(data, source, output, max_spend):
    original = json.loads(source.read_text())
    if original["status"] != "complete" or any(
        row["status"] != "complete" for row in original["cases"]
    ):
        raise ValueError("Require a complete preserved primary comparison")
    for row in original["cases"]:
        path = (
            (data / "images" / row["file_name"]).resolve()
            if "file_name" in row
            else (data / row["file"]).resolve()
        )
        if (
            not path.is_relative_to(data.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]
        ):
            raise ValueError("Public source identity differs")
    output.mkdir(parents=True, exist_ok=False)
    client = AuditClient(max_spend, max_requests=96)
    verifier = CloudVerifier(client=client, model=original["model"]["vision_model"])
    rows = []
    for row in original["cases"]:
        primary = row.get("primary_judgment", row["judgment"])
        rows.append(
            {
                **row,
                "primary_judgment": primary,
                "judgment": primary,
                "status": "not_run" if primary["visibility"] == "visible" else "complete",
                **score(row["expected"], primary),
            }
        )
        if primary["visibility"] == "visible":
            rows[-1]["correct"] = False
    report = {
        "status": "running",
        "primary_artifact": str(source),
        "primary_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "primary_model": original["model"],
        "confirmation_model": verifier.fingerprint["reference_model"],
        "mode": "cached-positive-only confirmation",
        "confirmation_policy": verifier.fingerprint.get("positive_confirmation_policy", 1),
        "budget_before": client.initial,
        "cases": rows,
        "limitations": "Same preserved first pass isolates the effect of an extra confirmation. No new primary inference, no relabeling or image selection from outputs. Category/count proxies do not measure precise location or instance identity. Primary/corroboration costs are separate artifacts.",
    }

    def checkpoint():
        report["provider_usage"] = client.usage
        report["summary"] = {
            "total": len(rows),
            "complete": sum(r["status"] == "complete" for r in rows),
            "correct_proxy": sum(r.get("correct", False) for r in rows),
            "unsafe_positive_proxy": sum(
                r["status"] == "complete" and score(r["expected"], r["judgment"])["unsafe_positive"]
                for r in rows
            ),
        }
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")

    checkpoint()
    try:
        for row in rows:
            if row["status"] == "complete":
                continue
            began = time.perf_counter()
            path = data / "images" / row["file_name"] if "file_name" in row else data / row["file"]
            with Image.open(path) as image:
                judged = verifier.confirm_positive(image, row["query"], row["primary_judgment"])
            row.update(
                status="complete",
                judgment=judged,
                confirmation_raw=client.last_response,
                confirmation_ms=round((time.perf_counter() - began) * 1000),
                **score(row["expected"], judged),
            )
            checkpoint()
        report["status"] = "complete"
    finally:
        if report["status"] != "complete":
            report["status"] = "failed"
        report["budget_after"] = budget_snapshot(client)
        checkpoint()
    return report["summary"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.15)
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.source, args.output, args.max_spend)))
