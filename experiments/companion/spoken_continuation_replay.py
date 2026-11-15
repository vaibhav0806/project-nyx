"""Four synthetic-evidence continuations of actual native model tool choices; manual audit."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from experiments.companion.correction_replay import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from nyx.realtime import INSTRUCTIONS, INSTRUCTIONS_VERSION

# These are explicit synthetic evidence fixtures, never application reply templates.
CASES = [
    {
        "id": "reported-not-current",
        "source": "development",
        "case": "latest-keys-report",
        "criterion": "Attribute the desk to a past user report; do not claim current visual confirmation.",
        "results": {
            "search_statements": {
                "status": "complete",
                "matches": [
                    {
                        "turn_id": "1" * 32,
                        "kind": "reported_placement",
                        "at": "2026-11-14T10:00:00Z",
                        "transcript": "I put my keys on the desk.",
                    }
                ],
                "answer": "You reported putting your keys on the desk yesterday. This is not visual confirmation of their current location.",
            }
        },
    },
    {
        "id": "failed-save-hi",
        "source": "holdout",
        "case": "plan-wallet-hi",
        "criterion": "Ask for clarification in Hindi; never say the plan was saved.",
        "results": {
            "remember_statement": {
                "status": "clarify",
                "answer": "I couldn't reliably identify the object for this memory. Please show it or describe it more clearly. No memory was saved.",
            }
        },
    },
    {
        "id": "visual-and-intention",
        "source": "development",
        "case": "historical-phone",
        "criterion": "Keep yesterday's visual desk candidate separate from a planned bag placement; no current certainty.",
        "results": {
            "look_for_object": {
                "status": "candidate",
                "evidence": {
                    "video_id": "2" * 32,
                    "observed_at": "2026-11-14T10:00:00Z",
                    "judgment": {"visibility": "visible", "location": "on the desk"},
                },
                "answer": "Visual candidate recorded yesterday on the desk. Identity and current location are unverified.",
            },
            "search_statements": {
                "status": "complete",
                "matches": [
                    {
                        "turn_id": "3" * 32,
                        "kind": "intention",
                        "at": "2026-11-14T11:00:00Z",
                        "transcript": "I will put my phone in my bag, but I have not done it yet.",
                    }
                ],
                "answer": "You planned to put your phone in your bag; this does not establish completion.",
            },
        },
    },
    {
        "id": "correction-source-id",
        "source": "holdout",
        "case": "explicit-correction",
        "criterion": "If requesting the correction, use exactly the returned report turn ID; do not invent one or claim a successful save yet.",
        "results": {
            "search_statements": {
                "status": "complete",
                "statement_refs": [{"turn_id": "4" * 32, "kind": "reported_placement"}],
                "matches": [
                    {
                        "turn_id": "4" * 32,
                        "transcript": "My TV remote is on the sofa.",
                        "at": "2026-11-14T09:00:00Z",
                    }
                ],
                "answer": "Found your saved report about the TV remote on the sofa. It has not been corrected yet.",
            }
        },
    },
]


def run(development, holdout, output, max_spend):
    sources = {
        "development": json.loads(development.read_text()),
        "holdout": json.loads(holdout.read_text()),
    }
    output.mkdir(parents=True, exist_ok=False)
    client = BudgetedClient(max_spend, max_requests=8)
    report = {
        "total_cases": len(CASES),
        "status": "running",
        "instructions_version": INSTRUCTIONS_VERSION,
        "instructions_sha256": hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
        "budget_before": client.initial,
        "cases": [],
        "limitations": "Actual spoken-model continuations with explicitly synthetic tool evidence and original model-selected calls. Manual author audit of four predeclared criteria, not acoustic or end-to-end backend acceptance. No evidence was uploaded from a household.",
    }
    try:
        for case in CASES:
            source = sources[case["source"]]
            original = next(row for row in source["cases"] if row["id"] == case["case"])
            messages = [
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": original["text"]},
                original["message"],
            ]
            for call in original["message"]["tool_calls"]:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(case["results"][call["function"]["name"]]),
                    }
                )
            began = time.perf_counter()
            response = client.request(
                "chat/completions",
                {
                    "model": source["model"],
                    "temperature": 0,
                    "max_tokens": 1024,
                    "reasoning": {"effort": "low", "exclude": True},
                    "messages": messages,
                    "tools": source["schemas"],
                    "tool_choice": "auto",
                },
            )
            report["cases"].append(
                {
                    **case,
                    "response": response["choices"][0],
                    "elapsed_ms": round((time.perf_counter() - began) * 1000),
                }
            )
            (output / "results.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            )
    finally:
        report["status"] = "complete" if len(report["cases"]) == len(CASES) else "incomplete"
        report["budget_after"] = budget_snapshot(client)
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
    return {"complete": len(report["cases"]), "total": len(CASES)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.06)
    args = parser.parse_args()
    print(json.dumps(run(args.development, args.holdout, args.output, args.max_spend)))
