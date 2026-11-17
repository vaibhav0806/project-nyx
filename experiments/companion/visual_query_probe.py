"""Paired public-frame diagnostic: visual description versus workflow/provenance in a query."""

import argparse
import json
from pathlib import Path

from experiments.companion.budget import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.public_history_workflows import verified_public_index
from nyx.capture import frame_image
from nyx.verification import CloudVerifier


def run(args):
    source, paths, _ = verified_public_index(args.fixture, args.embedded)
    video = next(source / p for p in paths if Path(p).suffix == ".mp4")
    scenes = json.loads((args.fixture / "dataset.json").read_text())["scenes"]
    for offset in [2, 10, 20]:
        scene = next(s for s in scenes if s["start"] <= offset < s["end"])
        if "coffee" not in scene["objects"]:
            raise ValueError("Declared public positive frame changed")
    args.output.mkdir(parents=True, exist_ok=False)

    class AuditedClient(BudgetedClient):
        def generate(self, *arguments, **kwargs):
            self.last_raw = super().generate(*arguments, **kwargs)
            return self.last_raw

    client = AuditedClient(0.08, max_requests=8)
    verifier = CloudVerifier(client)
    queries = [
        {"query": "cup of coffee", "offsets": [2, 10, 20]},
        {
            "query": "cup of coffee in the user's imported clip; locate it and describe surroundings/position",
            "offsets": [2, 10, 20],
        },
        {"query": "purple walking cane", "offsets": [2]},
        {
            "query": "purple walking cane in the user's imported clip; locate it and describe surroundings/position",
            "offsets": [2],
        },
    ]
    report = {
        "status": "running",
        "budget_before": client.initial,
        "verifier": verifier.fingerprint,
        "frozen_queries": queries,
        "cases": [],
        "limitations": "Paired opened development diagnostic on verified public still-frame video. Isolates query wording; not household accuracy, independent holdout or hardware use. Original capture date unknown.",
    }
    try:
        for group in queries:
            for offset in group["offsets"]:
                result = verifier.inspect(frame_image(video, offset), group["query"])
                report["cases"].append(
                    {
                        "query": group["query"],
                        "offset": offset,
                        "judgment": result,
                        "raw": client.last_raw,
                    }
                )
        report["status"] = "complete"
    finally:
        if report["status"] != "complete":
            report["status"] = "failed"
        report["provider_usage"] = client.usage
        report["budget_after"] = budget_snapshot(client)
        (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    return {"status": report["status"], "cases": len(report["cases"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--embedded", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args())))
