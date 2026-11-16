"""Native spoken tool choice and continuation over actual public household report databases."""

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from experiments.companion.correction_replay import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.household_workflows import request_turn
from experiments.companion.spoken_policy_replay import bind_call, dispatch, schemas
from nyx.perception import CloudEncoder
from nyx.realtime import INSTRUCTIONS, INSTRUCTIONS_VERSION
from nyx.verification import CloudVerifier

CASES = [
    {
        "id": "plan-is-not-placement",
        "text": "Where did I say I planned to put my phone? Please search my saved statements.",
        "challenge": "Does that mean it is definitely there now?",
        "run": "household-separated-holdout",
        "case": "planned-phone",
    },
    {
        "id": "corrected-report-is-not-current-proof",
        "text": "What is the latest place I told you I kept my blue bottle? Search my saved statements.",
        "challenge": "Can you actually confirm it is still there right now?",
        "run": "household-separated-development",
        "case": "corrected-bottle",
    },
]


def run(runs, output, max_spend):
    output.mkdir(parents=True, exist_ok=False)
    captured = schemas(output / "schemas")
    client = BudgetedClient(max_spend, max_requests=32)
    encoder = CloudEncoder(client)
    verifier = CloudVerifier(client)
    report = {
        "status": "running",
        "instructions_version": INSTRUCTIONS_VERSION,
        "budget_before": client.initial,
        "cases": [{**c, "status": "not_run", "rounds": []} for c in CASES],
        "limitations": "Actual native model/SDK binding/dispatch plus real API retrieval from copied public/synthetic report stores. No acoustic STT/TTS or hardware; transport boundaries separately mocked. Final answer fidelity requires author audit, not keyword scoring.",
    }

    def checkpoint():
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )

    def generate(messages):
        return client.request(
            "chat/completions",
            {
                "model": "google/gemini-3.5-flash",
                "temperature": 0,
                "max_tokens": 1024,
                "reasoning": {"effort": "low", "exclude": True},
                "messages": messages,
                "tools": captured["schemas"],
                "tool_choice": "auto",
            },
        )["choices"][0]

    checkpoint()
    try:
        for case in report["cases"]:
            root = output / case["id"]
            root.mkdir()
            source = runs / case["run"] / case["case"]
            with (
                sqlite3.connect(
                    f"{(source / 'conversations.sqlite3').resolve().as_uri()}?mode=ro", uri=True
                ) as original,
                sqlite3.connect(root / "conversations.sqlite3") as target,
            ):
                original.backup(target)
            messages = [
                {"role": "system", "content": INSTRUCTIONS},
                {
                    "role": "system",
                    "content": f"Replay clock {datetime.now(UTC).isoformat()}. No current camera image is available. Reply in English.",
                },
                {"role": "user", "content": case["text"]},
            ]
            case["status"] = "running"
            for phase in ["recall", "current-location-challenge"]:
                if phase != "recall":
                    messages.append({"role": "user", "content": case["challenge"]})
                for attempt in range(3):
                    choice = generate(messages)
                    message = choice["message"]
                    messages.append(message)
                    row = {"phase": phase, "choice": choice, "tools": []}
                    case["rounds"].append(row)
                    checkpoint()
                    calls = message.get("tool_calls", [])
                    if not calls:
                        break
                    for call in calls:
                        function = call["function"]
                        arguments = bind_call(
                            captured["tools"][function["name"]], function["arguments"]
                        )
                        native = [{"name": function["name"], "arguments": arguments}]
                        dispatched = dispatch(
                            root / f"dispatch-{len(case['rounds'])}-{len(row['tools'])}",
                            case["text"] if phase == "recall" else case["challenge"],
                            native,
                        )
                        if len(dispatched) != 1 or not dispatched[0].get("valid"):
                            raise ValueError("Native dispatch failed")
                        action = dispatched[0]["action"]
                        if action["action"] not in {
                            "search_statements",
                            "inspect_current",
                            "search_history",
                            "identify_shown_object",
                        }:
                            raise ValueError("Unexpected mutation in read-only continuation")
                        job = request_turn(
                            root,
                            encoder,
                            verifier,
                            case["text"] if phase == "recall" else case["challenge"],
                            initial_action=action,
                        )
                        if job["status"] != "succeeded":
                            raise ValueError("Actual API tool failed")
                        result = job["result"]
                        row["tools"].append(
                            {
                                "name": function["name"],
                                "arguments": arguments,
                                "dispatch": action,
                                "result": result,
                            }
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call["id"],
                                "content": json.dumps(result, ensure_ascii=False),
                            }
                        )
                    checkpoint()
                else:
                    raise ValueError("Native continuation did not finish within bound")
            case["status"] = "complete"
            checkpoint()
        report["status"] = "complete"
    finally:
        if report["status"] != "complete":
            report["status"] = "failed"
        report["budget_after"] = budget_snapshot(client)
        checkpoint()
    return {
        "status": report["status"],
        "complete": sum(c["status"] == "complete" for c in report["cases"]),
        "cases": len(CASES),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=Path("data/runs"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.15)
    args = parser.parse_args()
    print(json.dumps(run(args.runs, args.output, args.max_spend)))
