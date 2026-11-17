"""Bounded synthetic reply-style comparison; supplied receipts, not persistence acceptance."""

import argparse
import hashlib
import json
from pathlib import Path

from experiments.companion.budget import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.native_voice import bind_call, schemas
from nyx.agent_policy import AGENT_INSTRUCTIONS
from nyx.verification import CloudVerifier


def run(output, candidate_policy, max_spend, cases_path):
    output.mkdir(parents=True, exist_ok=False)
    cases = json.loads(cases_path.read_text())
    captured = schemas(output / "schema-session")
    tools = captured["schemas"]
    client = BudgetedClient(max_spend, max_requests=40)
    verifier = CloudVerifier(client)
    report = {
        "status": "running",
        "model": verifier.model,
        "budget_before": client.initial,
        "limitations": "Synthetic text and supplied memory receipts. Actual shared native schemas/binding and model; one controlled unavailable-evidence tool continuation at most. No real persistence, vision, acoustics or hardware. All replies need manual semantic review.",
        "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "policies": {},
    }
    try:
        for name, policy in [
            ("baseline", AGENT_INSTRUCTIONS),
            ("candidate", candidate_policy.read_text().strip()),
        ]:
            rows = []
            report["policies"][name] = {
                "sha256": hashlib.sha256(policy.encode()).hexdigest(),
                "words": len(policy.split()),
                "cases": rows,
            }
            for case in cases:
                context = {
                    "kind": "memory",
                    "status": "saved",
                    "saved_ids": ["synthetic-memory"],
                    "records": [
                        {"id": "synthetic-memory", "kind": case["kind"], "content": case["memory"]}
                    ],
                    "sources": ["transcript:synthetic-input"],
                }
                messages = [
                    {"role": "system", "content": policy},
                    {
                        "role": "system",
                        "content": 'Available context: {"current_view": false, "turn_visual_context": false, "history": false, "scheduled_reminders": false, "proactive_notifications": false}',
                    },
                    {"role": "system", "content": "Memory context: " + json.dumps(context)},
                    {"role": "user", "content": case["text"]},
                ]
                reply = verifier.agent_reply(messages, tools)
                initial = reply
                if reply.get("tool_calls"):
                    messages.append(reply)
                    for call in reply["tool_calls"]:
                        function = call["function"]
                        bind_call(captured["tools"][function["name"]], function["arguments"])
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call["id"],
                                "content": json.dumps(
                                    {
                                        "status": "uncertain",
                                        "answer": "No additional visual evidence is available. Appearance does not establish identity or current location.",
                                        "identity_verified": False,
                                    }
                                ),
                            }
                        )
                    reply = verifier.agent_reply(messages, tools)
                rows.append({**case, "initial_reply": initial, "reply": reply})
                (output / "results.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
                )
        report["status"] = "complete"
    finally:
        report["provider_usage"] = client.usage
        report["response_reported_cost"] = sum(row.get("cost") or 0 for row in client.usage)
        report["budget_after"] = budget_snapshot(client)
        (output / "results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-policy", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.05)
    parser.add_argument(
        "--cases", type=Path, default=Path(__file__).with_name("reply_style_cases.json")
    )
    args = parser.parse_args()
    result = run(args.output, args.candidate_policy, args.max_spend, args.cases)
    print(
        json.dumps(
            {key: result[key] for key in ["status", "response_reported_cost", "budget_after"]}
        )
    )
