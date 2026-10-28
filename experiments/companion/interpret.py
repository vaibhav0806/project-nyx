"""Diagnostic: resolve a follow-up separately from tool execution. No application writes."""

import argparse
import json
import time
from pathlib import Path

from nyx.verification import LocalVerifier

PROMPT = """Interpret the latest user request using the previous conversation as context.
Return JSON with exactly these fields:
query: the object description, combining new details with previous ones; null for chat or unclear object.
relation: "new" for a different object, "reject" if the displayed candidate is wrong,
"continue" for the same object without rejection, "chat" for thanks/stop, "clarify" if unclear.
view: "current" for explicit live view, "history" for recorded/older sightings or feedback on a saved candidate, "none" for chat/clarify.
older: true ONLY when the user asks to search further back than before, otherwise false.
A new object has relation new. Asking for older footage alone is NOT a rejection.
Preserve newly supplied color/material/shape attributes. Do not include time instructions in query.
Do not perform a search or claim findings. Interpret only what the user is asking now."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chat-history", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    model = LocalVerifier()
    rows = []
    for case in json.loads(args.case_file.read_text()):
        context = []
        for turn in case.get("context", []):
            context.append(
                {
                    "user": turn["transcript"],
                    "assistant": turn["answer"],
                    "candidate": (turn.get("plan", {}).get("candidate") or {}).get("object_query"),
                }
            )
        messages = [{"role": "system", "content": PROMPT}]
        for turn in context:
            messages.extend(
                [
                    {"role": "user", "content": turn["user"]},
                    {
                        "role": "assistant",
                        "content": turn["assistant"]
                        + "\nCandidate description: "
                        + str(turn["candidate"]),
                    },
                ]
            )
        messages.append({"role": "user", "content": case["message"]})
        started = time.perf_counter()
        raw = model.generate_json(
            messages
            if args.chat_history
            else [
                {"role": "system", "content": PROMPT},
                {
                    "role": "user",
                    "content": "Previous conversation:\n"
                    + json.dumps(context)
                    + "\nLatest user request:\n"
                    + case["message"],
                },
            ],
            180,
        )
        rows.append({"name": case["name"], "raw": raw, "seconds": time.perf_counter() - started})
        print(json.dumps(rows[-1]), flush=True)
        (args.output / "results.json").write_text(
            json.dumps(
                {
                    "model": model.fingerprint,
                    "prompt": PROMPT,
                    "chat_history": args.chat_history,
                    "cases": rows,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
