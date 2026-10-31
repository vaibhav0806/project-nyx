"""Synthetic streaming tool-selection comparison; no camera, audio or tool execution.

uv run --env-file .env --no-sync python experiments/companion/voice_routing.py
"""

import ast
import json
import os
import random
import time
from pathlib import Path
from urllib.request import Request, urlopen

from nyx.realtime import INSTRUCTIONS

MODELS = [
    "openai/gpt-6-luna",
    "openai/gpt-4.1-mini",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "google/gemini-3.5-flash-lite",
]
CASES = [
    ("pronoun", "Where did I put this?", {"identify_shown_object"}),
    ("placement", "I am going to keep this in the kitchen.", {"remember_statement"}),
    (
        "history",
        "Where was my phone last seen yesterday?",
        {"look_for_object", "search_statements"},
    ),
    ("current", "Can you see my glasses right now?", {"look_for_object"}),
    ("reminder", "Remind me to take my bottle when I leave.", {"departure_reminder"}),
    ("greeting", "Hi Nyx, how are you?", set()),
]


def tool_schemas():
    """Use the actual runtime function names, descriptions and parameter defaults."""
    result = []
    tree = ast.parse(Path("src/nyx/realtime.py").read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef) or not any(
            isinstance(d, ast.Name) and d.id == "function_tool" for d in node.decorator_list
        ):
            continue
        props, required = {}, []
        args = node.args.args[1:]
        defaults = (
            dict(zip([a.arg for a in args[-len(node.args.defaults) :]], node.args.defaults))
            if node.args.defaults
            else {}
        )
        for arg in args:
            props[arg.arg] = {
                "type": {"str": "string", "int": "integer", "bool": "boolean"}[arg.annotation.id]
            }
            if arg.arg in defaults:
                props[arg.arg]["default"] = ast.literal_eval(defaults[arg.arg])
            else:
                required.append(arg.arg)
        result.append(
            {
                "type": "function",
                "function": {
                    "name": node.name,
                    "description": ast.get_docstring(node),
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                        "additionalProperties": False,
                    },
                },
            }
        )
    return result


def measure(model, case, tools):
    name, text, expected = case[:3]
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": text},
        ],
        "tools": tools,
        "stream": True,
        "max_tokens": 700,
        "stream_options": {"include_usage": True},
        "provider": {"data_collection": "deny"},
    }
    if len(case) > 3:
        payload["messages"] += case[3]
    if model in {"openai/gpt-6-luna", "google/gemini-3.5-flash-lite", "google/gemini-3.5-flash"}:
        payload["reasoning"] = {"effort": "low", "exclude": True}
    started = time.perf_counter()
    row = {"model": model, "case": name, "first_output_ms": None, "first_tool_ms": None}
    calls, output, usage = {}, "", {}
    req = Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    with urlopen(req, timeout=40) as response:
        for line in response:
            if not line.startswith(b"data:"):
                continue
            raw = line[5:].strip()
            if raw == b"[DONE]":
                break
            event = json.loads(raw)
            if "error" in event:
                raise ValueError("Provider stream failed")
            usage = event.get("usage") or usage
            for choice in event.get("choices", []):
                delta = choice.get("delta", {})
                elapsed = round((time.perf_counter() - started) * 1000)
                if (delta.get("content") or delta.get("tool_calls")) and row[
                    "first_output_ms"
                ] is None:
                    row["first_output_ms"] = elapsed
                output += delta.get("content") or ""
                for call in delta.get("tool_calls", []):
                    if row["first_tool_ms"] is None:
                        row["first_tool_ms"] = elapsed
                    entry = calls.setdefault(call["index"], {"name": "", "arguments": ""})
                    for key in ("name", "arguments"):
                        entry[key] += call.get("function", {}).get(key) or ""
                if choice.get("finish_reason"):
                    row["decision_ready_ms"] = elapsed
                    row["finish_reason"] = choice["finish_reason"]
    row.update(calls=list(calls.values()), text=output, usage=usage)
    names = {c["name"] for c in calls.values()}
    row["passed"] = bool(names & expected) if expected else not names and bool(output)
    for call in calls.values():
        args = json.loads(call["arguments"])
        schema = next(
            (t["function"]["parameters"] for t in tools if t["function"]["name"] == call["name"]),
            None,
        )
        if (
            schema is None
            or not isinstance(args, dict)
            or set(args) - set(schema["properties"])
            or set(schema["required"]) - set(args)
        ):
            row["passed"] = False
            row["schema_error"] = True
        if name == "pronoun" and call["name"] != "identify_shown_object":
            row["passed"] = False
        if call["name"] == "look_for_object":
            if name == "history" and (not args.get("history") or args.get("hours", 2) == 2):
                row["passed"] = False
            if name == "current" and args.get("history", False):
                row["passed"] = False
    return row


def main():
    target = Path("data/runs/voice-routing/results.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    tools = tool_schemas()
    jobs = [(m, c) for _ in range(2) for c in CASES for m in MODELS]
    random.Random(31).shuffle(jobs)
    rows = []
    for model, case in jobs:
        try:
            row = measure(model, case, tools)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row = {"model": model, "case": case[0], "passed": False, "error": type(exc).__name__}
        rows.append(row)
        target.write_text(json.dumps({"tools": tools, "results": rows}, indent=2))
        print(
            json.dumps({k: v for k, v in row.items() if k not in {"text", "usage", "calls"}}),
            flush=True,
        )
    print("Results:", target)


if __name__ == "__main__":
    main()
