"""Paid first-tool-choice evaluation using the actual nested Companion's SDK schemas."""

import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path

import pytest
from livekit.agents import llm

from experiments.companion.correction_replay import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.spoken_policy_cases import CASES, score
from nyx.realtime import INSTRUCTIONS


def schemas(root):
    path = Path(__file__).resolve().parents[2] / "tests/test_realtime.py"
    spec = importlib.util.spec_from_file_location("nyx_realtime_replay_helpers", path)
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    captured = {}

    async def scenario(session, socket, voice):
        context = llm.ToolContext(session.agent.tools)
        captured["schemas"] = context.parse_function_tools("openai")
        captured["tools"] = context.function_tools

    with pytest.MonkeyPatch.context() as monkeypatch:
        helpers.replay_voice_tools(root, monkeypatch, scenario)
    return captured


def run(output, split, max_spend):
    output.mkdir(parents=True, exist_ok=False)
    captured = schemas(output / "schema-session")
    client = BudgetedClient(max_spend, max_requests=32)
    result = {
        "status": "running",
        "split": split,
        "model": "google/gemini-3.5-flash",
        "instructions_sha256": hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
        "schemas": captured["schemas"],
        "budget_before": client.initial,
        "cases": [{**case, "status": "not_run"} for case in CASES if case["split"] == split],
        "limitations": "Actual spoken model/instructions/SDK schemas with synthetic household transcripts. First tool choice and schema validity, not acoustic STT/TTS, backend semantic tool results or free-form final-answer quality. No forced model actions; failures count.",
    }

    def checkpoint():
        result["provider_usage"] = client.usage
        (output / "results.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        )

    checkpoint()
    try:
        for case in result["cases"]:
            began = time.perf_counter()
            response = client.request(
                "chat/completions",
                {
                    "model": result["model"],
                    "temperature": 0,
                    "max_tokens": 1024,
                    "reasoning": {"effort": "low", "exclude": True},
                    "messages": [
                        {"role": "system", "content": INSTRUCTIONS},
                        {"role": "user", "content": case["text"]},
                    ],
                    "tools": captured["schemas"],
                    "tool_choice": "auto",
                    "parallel_tool_calls": True,
                },
            )
            choice = response["choices"][0]
            message = choice["message"]
            calls = []
            valid = choice["finish_reason"] in {"stop", "tool_calls"}
            for call in message.get("tool_calls", []):
                function = call["function"]
                name = function["name"]
                try:
                    args = llm.utils.parse_function_arguments(function["arguments"])
                    tool = captured["tools"][name]
                    validated = llm.utils.function_arguments_to_pydantic_model(tool).model_validate(
                        args
                    )
                    args = validated.model_dump()
                except (ValueError, KeyError, TypeError):
                    valid = False
                    args = {}
                calls.append({"name": name, "arguments": args})
            valid = valid and bool(calls or message.get("content"))
            case.update(
                status="complete",
                schema_valid=valid,
                calls=calls,
                message=message,
                correct=valid and score(case, calls),
                elapsed_ms=round((time.perf_counter() - began) * 1000),
            )
            checkpoint()
        result["status"] = "complete"
    finally:
        if result["status"] != "complete":
            result["status"] = "failed"
        result["budget_after"] = budget_snapshot(client)
        checkpoint()
    return {
        "correct": sum(case.get("correct", False) for case in result["cases"]),
        "total": len(result["cases"]),
        "incomplete": sum(case["status"] != "complete" for case in result["cases"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--max-spend", type=float, default=0.06)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.split, args.max_spend)))
