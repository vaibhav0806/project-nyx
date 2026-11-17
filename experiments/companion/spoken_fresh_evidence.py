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


def run(output, max_spend, cases_path=None, effort="low"):
    cases = json.loads(cases_path.read_text()) if cases_path else CASES
    if not 1 <= len(cases) <= 8 or effort not in {"low", "medium"}:
        raise ValueError("Bounded explicit dialogue selection required")
    output.mkdir(parents=True, exist_ok=False)
    captured = schemas(output / "schema-session")
    client = BudgetedClient(max_spend, max_requests=4 * len(cases))
    report = {
        "instructions_version": INSTRUCTIONS_VERSION,
        "budget_before": client.initial,
        "total_cases": len(cases),
        "reasoning_effort": effort,
        "cases_path": str(cases_path) if cases_path else None,
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
                "reasoning": {"effort": effort, "exclude": True},
                "messages": messages,
                "tools": captured["schemas"],
                "tool_choice": "auto",
            },
        )["choices"][0]

    try:
        for case in cases:
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
            row["rounds"] = []
            for index in range(4):
                choice = generate(messages)
                step = {"choice": choice, "calls": []}
                row["rounds"].append(step)
                message = choice["message"]
                messages.append(message)
                if not message.get("tool_calls"):
                    row["status"] = (
                        "complete" if index and message.get("content") else "no_tool_call"
                    )
                    break
                for call in message["tool_calls"]:
                    function = call["function"]
                    arguments = bind_call(
                        captured["tools"][function["name"]], function["arguments"]
                    )
                    step["calls"].append({"name": function["name"], "arguments": arguments})
                    state = case.get("source_state", "possible")
                    if state == "report" and function["name"] == "recall_memory":
                        evidence = {
                            "status": "retrieved",
                            "kind": "memories",
                            "answer": "A saved user report, not a visual observation.",
                            "matches": [
                                {
                                    "content": case["report"],
                                    "kind": "report",
                                    "sources": ["transcript:synthetic-report"],
                                }
                            ],
                        }
                    elif state == "ambiguous":
                        evidence = {
                            "status": "clarify",
                            "answer": "Multiple plausible objects; no unique identity or location established.",
                        }
                    elif state == "possible" and function["name"] == "look_for_object":
                        evidence = {
                            "status": "candidate",
                            "answer": "Possible visual match yesterday; identity and current location unverified.",
                            "evidence": {
                                "observed_at": "2026-11-14T10:00:00Z",
                                "judgment": {"visibility": "visible", "location": case["location"]},
                            },
                        }
                    elif function["name"] == "recall_memory":
                        evidence = {
                            "status": "uncertain",
                            "kind": "memories",
                            "matches": [],
                            "answer": "No matching saved user reports.",
                        }
                    else:
                        evidence = {
                            "status": "clarify",
                            "answer": "This synthetic replay has no evidence for this tool.",
                        }
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": json.dumps(evidence),
                        }
                    )
                step["dispatches"] = dispatch(
                    output / case["id"] / str(index), case["text"], step["calls"]
                )
            else:
                row["status"] = "continuation_limit"
    finally:
        report["budget_after"] = budget_snapshot(client)
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
    return {
        "complete": sum(row["status"] == "complete" for row in report["cases"]),
        "total": len(cases),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.05)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--effort", choices=["low", "medium"], default="low")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.max_spend, args.cases, args.effort)))
