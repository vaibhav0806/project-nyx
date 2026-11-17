"""Full native API → cached public embeddings → actual source verification → reply."""

import argparse
import json
import shutil
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from experiments.companion.budget import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.household_workflows import digest, request_turn
from nyx.perception import CloudEncoder
from nyx.verification import CloudVerifier


def verified_public_index(fixture, embedded):
    manifest = fixture / "dataset.json"
    if (
        json.loads(manifest.read_text()).get("description")
        != "Twelve edited scenes from four public still images, two seconds each."
    ):
        raise ValueError("Only the documented four-source public fixture is permitted")
    prior = json.loads((embedded / "results.json").read_text())
    if prior["fixture_manifest_sha256"] != digest(manifest):
        raise ValueError("Embedding provenance differs from the public fixture")
    source = embedded / "index"
    with sqlite3.connect(
        f"{(source / 'index.sqlite3').resolve().as_uri()}?mode=ro", uri=True
    ) as db:
        identity = json.loads(
            db.execute("SELECT value FROM meta WHERE key='encoder'").fetchone()[0]
        )
        paths = [row[0] for row in db.execute("SELECT path FROM videos")]
        paths += [row[0] for row in db.execute("SELECT thumbnail FROM frames")]
    for relative in paths:
        path, original = (source / relative).resolve(), (fixture / "index" / relative).resolve()
        if (
            not path.is_relative_to(source.resolve())
            or not original.is_relative_to((fixture / "index").resolve())
            or digest(path) != digest(original)
        ):
            raise ValueError("Media is not the declared public source")
    return source, paths, identity


def run(args):
    source, paths, identity = verified_public_index(args.fixture, args.embedded)
    cases = json.loads(args.cases.read_text())
    if len(cases) != 4:
        raise ValueError("Frozen four-condition evaluation required")
    args.output.mkdir(parents=True, exist_ok=False)
    client = BudgetedClient(args.max_spend, max_requests=96)
    encoder, verifier = CloudEncoder(client), CloudVerifier(client)
    if identity != {"encoder": encoder.fingerprint, "dimensions": encoder.dimensions}:
        raise ValueError("Cached embedding space is incompatible; do not silently rebuild")
    if verifier.history_concurrency != 1:
        raise ValueError("Set NYX_HISTORY_CONCURRENCY=1 for sequential bounded paid evaluation")
    report = {
        "status": "running",
        "cases_sha256": digest(args.cases),
        "fixture_manifest_sha256": digest(args.fixture / "dataset.json"),
        "verifier": verifier.fingerprint,
        "encoder": encoder.fingerprint,
        "budget_before": client.initial,
        "cases": [{**c, "status": "not_run"} for c in cases],
        "limitations": "Reused four-public-photo edited video, cached compatible vectors and actual native API/vision. Copy-only simulated recording dates, no private media/hardware, no recognition or human-acceptance claim from job completion. Inline source/answer audit required.",
    }

    def checkpoint():
        report["provider_usage"] = client.usage
        (args.output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )

    checkpoint()
    try:
        for case in report["cases"]:
            root = args.output / case["id"]
            root.mkdir()
            with (
                sqlite3.connect(
                    f"{(source / 'index.sqlite3').resolve().as_uri()}?mode=ro", uri=True
                ) as original,
                sqlite3.connect(root / "index.sqlite3") as copied,
            ):
                original.backup(copied)
                at = (
                    (datetime.now(UTC) - timedelta(days=case["days_ago"])).isoformat()
                    if case["days_ago"] is not None
                    else None
                )
                copied.execute("UPDATE videos SET recorded_at=?", (at,))
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / relative, target)
            case["job"] = request_turn(root, encoder, verifier, case["message"])
            case["status"] = case["job"]["status"]
            checkpoint()
            if case["status"] != "succeeded":
                raise ValueError("Transport failed; inspect before more paid calls")
        report["status"] = "complete"
    finally:
        if report["status"] != "complete":
            report["status"] = "failed"
        report["budget_after"] = budget_snapshot(client)
        checkpoint()
    return {"status": report["status"], "cases": len(cases), "semantic_audit": "required"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--embedded", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_suffix(".json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.20)
    print(json.dumps(run(parser.parse_args())))
