"""Fresh synthetic native tool→dispatch→evidence continuations, manual semantic audit."""

import argparse
import json
from pathlib import Path

from experiments.companion.budget import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.native_voice import bind_call, dispatch, schemas
from nyx.agent_policy import AGENT_MODEL
from nyx.realtime import INSTRUCTIONS, INSTRUCTIONS_VERSION

CASES = [
    {
        "id": "bottle-source",
        "text": "Where did you last see my blue bottle?",
        "location": "on the sideboard",
    },
    {
        "id": "remote-source-hi",
        "text": "मेरा रिमोट आखिरी बार कहाँ दिखा था?",
        "location": "on the sofa",
    },
]


def continuation_status(choice):
    message = choice.get("message", {})
    if message.get("tool_calls"):
        return "awaiting_tools"
    return "complete" if message.get("content") else "failed"


def run(output, max_spend):
    output.mkdir(parents=True, exist_ok=False)
    captured = schemas(output / "schema-session")
    client = BudgetedClient(max_spend, max_requests=8)
    report = {
        "instructions_version": INSTRUCTIONS_VERSION,
        "budget_before": client.initial,
        "total_cases": len(CASES),
        "cases": [],
        "criteria": "Self-select a valid historical tool call; after candidate evidence express possible identity and past time, never certain current possession. Author manual audit, no automated keyword judge.",
        "limitations": "New synthetic semantic cases; actual spoken model/SDK binding/dispatch, synthetic external visual/report evidence. Not real vision, acoustic STT/TTS or household acceptance.",
    }

    def generate(messages):
        return client.request(
            "chat/completions",
            {
                "model": AGENT_MODEL,
                "temperature": 0,
                "max_tokens": 1024,
                "reasoning": {"effort": "low", "exclude": True},
                "messages": messages,
                "tools": captured["schemas"],
                "tool_choice": "auto",
            },
        )["choices"][0]

    try:
        for case in CASES:
            row = {**case, "status": "not_run"}
            report["cases"].append(row)
            messages = [
                {"role": "system", "content": INSTRUCTIONS},
                {
                    "role": "system",
                    "content": "Synthetic replay clock: User local time 2026-11-15T18:00:00+05:30. Reply in the latest user turn's language.",
                },
                {"role": "user", "content": case["text"]},
            ]
            initial = generate(messages)
            row["initial"] = initial
            message = initial["message"]
            messages.append(message)
            calls = []
            for call in message.get("tool_calls", []):
                function = call["function"]
                arguments = bind_call(captured["tools"][function["name"]], function["arguments"])
                calls.append({"name": function["name"], "arguments": arguments})
                if function["name"] == "look_for_object":
                    evidence = {
                        "status": "candidate",
                        "answer": "Possible visual match yesterday; identity and current location unverified.",
                        "evidence": {
                            "observed_at": "2026-11-14T10:00:00Z",
                            "judgment": {"visibility": "visible", "location": case["location"]},
                        },
                    }
                elif function["name"] == "search_statements":
                    evidence = {
                        "status": "complete",
                        "matches": [],
                        "answer": "No matching saved user reports.",
                    }
                else:
                    evidence = {
                        "status": "clarify",
                        "answer": "This synthetic replay has no evidence for this tool.",
                    }
                messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(evidence)}
                )
            row["calls"] = calls
            row["dispatches"] = dispatch(output / case["id"], case["text"], calls)
            if calls:
                row["continuation"] = generate(messages)
                row["status"] = continuation_status(row["continuation"])
            else:
                row["status"] = "no_tool_call"
    finally:
        report["budget_after"] = budget_snapshot(client)
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
    return {
        "complete": sum(row["status"] == "complete" for row in report["cases"]),
        "total": len(CASES),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.05)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.max_spend)))
