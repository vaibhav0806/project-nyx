"""Paid, opt-in synthetic report-to-answer evaluation using real API/planner/storage."""

import argparse
import hashlib
import json
import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path


def validate_cases(cases):
    ids, groups, texts = set(), {}, {}
    if not isinstance(cases, list) or not cases:
        raise ValueError("Nonempty workflow cases required")
    for case in cases:
        identifier, split, group = case["id"], case["split"], case["group"]
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[a-z0-9-]{1,80}", identifier)
            or identifier in ids
            or split not in {"development", "holdout"}
            or not group
        ):
            raise ValueError("Invalid workflow identity/split")
        ids.add(identifier)
        if group in groups and groups[group] != split:
            raise ValueError("Source group leakage")
        groups[group] = split
        reports = set()
        for report in case["reports"]:
            if report["id"] in reports or report.get("corrects") not in reports | {None}:
                raise ValueError("Invalid report identity/correction")
            reports.add(report["id"])
            text = report["text"].strip().casefold()
            if text in texts and texts[text] != split:
                raise ValueError("Report text leakage")
            texts[text] = split
        if not set(case["expected_reports"]) <= reports or not case["query"].strip():
            raise ValueError("Invalid expected report/query")
    return cases


def score_answer(case, result, identifiers):
    if not result:
        return {"correct": False, "reason": "failed_or_missing_output"}
    observations = result.get("observations", [])
    selected = {
        match["turn_id"]
        for row in observations
        if row.get("kind") in {"memory", "memories"}
        for match in row.get("records", row.get("matches", []))
    }
    expected = {identifiers[key] for key in case["expected_reports"]}
    attributed = all(
        "transcript:" + identifier in result.get("sources", []) for identifier in selected
    )
    negative_checked = result.get("status") in {"clarify", "uncertain"} or any(
        row.get("kind") in {"memory", "memories"} and not row.get("records", row.get("matches", []))
        for row in observations
    )
    visual_claim = bool((result.get("visual") or {}).get("evidence"))
    correct = (
        selected == expected and attributed and bool(result.get("answer")) and not visual_claim
    )
    if not expected:
        correct = correct and negative_checked
    return {
        "correct": correct,
        "selected_ids": sorted(selected),
        "expected_ids": sorted(expected),
        "attributed": attributed,
        "negative_checked": negative_checked,
    }


def run(cases_path, output, split, max_spend):
    from fastapi.testclient import TestClient

    from experiments.companion.budget import BudgetedClient
    from experiments.companion.embedding_replay import budget_snapshot
    from nyx.app import create_app
    from nyx.perception import CloudEncoder
    from nyx.personal_memory import PersonalMemory
    from nyx.verification import CloudVerifier
    from nyx.voice import Conversations

    cases = validate_cases(json.loads(cases_path.read_text()))
    chosen = [case for case in cases if case["split"] == split]
    output.mkdir(parents=True, exist_ok=False)
    client = BudgetedClient(max_spend, max_requests=96)
    encoder, verifier = CloudEncoder(client=client), CloudVerifier(client=client)
    clock = datetime.now(UTC)
    report = {
        "status": "running",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "split": split,
        "clock": clock.isoformat(),
        "scorer_version": 3,
        "cases": [],
        "manifest_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "encoder": encoder.fingerprint,
        "verifier": verifier.fingerprint,
        "budget_before": client.initial,
        "limitations": "Synthetic attributed reports and backdated fixture report clocks, no captured footage/audio. Real general-memory interpretation, embedding, native agent and citations. Exact report attribution score is not free-form semantic or speech accuracy.",
    }

    def checkpoint():
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )

    try:
        for case in chosen:
            row = {"id": case["id"], "status": "running", "setup": []}
            report["cases"].append(row)
            root = output / case["id"]
            conversations = Conversations(root)
            memory = PersonalMemory(conversations, encoder, verifier.memory_reply)
            identifiers = {}
            started = time.perf_counter()
            try:
                for source in case["reports"]:
                    identifier = conversations.begin(source["text"], {})
                    identifiers[source["id"]] = identifier
                    with conversations.connect() as db:
                        db.execute(
                            "UPDATE turns SET at=? WHERE id=?",
                            ((clock - timedelta(days=source["days_ago"])).isoformat(), identifier),
                        )
                    saved = memory.process(identifier)
                    conversations.finish(identifier, saved["answer"], saved.get("sources", []))
                    row["setup"].append(
                        {
                            "id": source["id"],
                            "status": saved["status"],
                            "correct": saved["status"]
                            in (
                                {"noop", "clarify"}
                                if source.get("expected_link") == "clarify"
                                else {"saved"}
                            ),
                        }
                    )
                    if source.get("expected_kind"):
                        with conversations.connect() as db:
                            linked = db.execute(
                                "SELECT kind FROM memories WHERE turn_id=?", (identifier,)
                            ).fetchone()
                        row["setup"][-1]["kind"] = linked[0] if linked else None
                        row["setup"][-1]["correct"] &= bool(
                            linked
                            and linked[0]
                            == {"intention": "plan", "reported_placement": "report"}.get(
                                source["expected_kind"], source["expected_kind"]
                            )
                        )
                    if source.get("invalidate"):
                        conversations.finish(
                            identifier, saved["answer"], ["synthetic-deleted-source"]
                        )
                        conversations.invalidate("synthetic-deleted-source")
                for index in range(case.get("filler_turns", 0)):
                    filler = conversations.begin(f"Unrelated conversation about number {index}", {})
                    conversations.finish(filler, "Okay.")
                # Fresh app reopens durable state for every case, including chat eviction cases.
                query = case["query"].replace(
                    "{as_of}", (clock - timedelta(days=case.get("as_of_days", 0))).isoformat()
                )
                with TestClient(
                    create_app(
                        root,
                        encoder_factory=lambda: encoder,
                        verifier_factory=lambda: verifier,
                        voice_factory=lambda root: None,
                    )
                ) as api:
                    query_started = time.perf_counter()
                    response = api.post(
                        "/api/agent",
                        json={
                            "message": query,
                            "request_id": case["id"],
                            "timezone": "Asia/Kolkata",
                        },
                    )
                    response.raise_for_status()
                    deadline = time.monotonic() + 180
                    while time.monotonic() < deadline:
                        job = api.get("/api/jobs/" + response.json()["id"]).json()
                        if job["status"] in {"succeeded", "failed"}:
                            break
                        time.sleep(0.1)
                    else:
                        raise ValueError("Workflow timed out")
                    row["query_ms"] = round((time.perf_counter() - query_started) * 1000)
                result = job.get("result") if job["status"] == "succeeded" else None
                row.update(
                    status=job["status"],
                    failure=job.get("error"),
                    query=query,
                    result=result,
                    score=score_answer(case, result, identifiers),
                )
                row["workflow_correct"] = row["score"]["correct"] and all(
                    r["correct"] for r in row["setup"]
                )
            except (ValueError, OSError, RuntimeError) as error:
                row.update(status="failed", error_type=type(error).__name__, workflow_correct=False)
            row["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
            checkpoint()
            if row.get("error_type"):
                raise ValueError(
                    "Workflow transport/setup failure; inspect artifact before more spending"
                )
        report["status"] = "complete"
    except (ValueError, OSError, RuntimeError):
        report["status"] = "failed"
        raise
    finally:
        report["budget_after"] = budget_snapshot(client)
        report["run_spend_usd"] = report["budget_after"]["usage"] - client.initial["usage"]
        checkpoint()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases", type=Path, default=Path(__file__).with_name("recall_workflows.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--max-spend", type=float, default=0.20)
    args = parser.parse_args()
    report = run(args.cases, args.output, args.split, args.max_spend)
    print(
        json.dumps(
            {
                "status": report["status"],
                "cases": len(report["cases"]),
                "correct": sum(row["workflow_correct"] for row in report["cases"]),
                "incomplete": sum(row["status"] != "succeeded" for row in report["cases"]),
                "run_spend_usd": report["run_spend_usd"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
