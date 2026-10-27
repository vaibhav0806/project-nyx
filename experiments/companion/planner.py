"""Real local planner and agent loop with explicit controlled tool observations.

This tests query construction and decision paths, not real image retrieval/vision.
"""

import argparse
import json
import platform
import time
from importlib.metadata import version
from pathlib import Path

from nyx.agent import agent_steps
from nyx.verification import LocalVerifier

CASES = [
    {
        "name": "history-after-correction",
        "message": "Where did you last see it?",
        "context": [
            {
                "transcript": "Where is the television remote control?",
                "answer": "Which one do you mean?",
            },
            {
                "transcript": "I mean the remote on the right of the picture.",
                "answer": "Between the two cats",
            },
        ],
        "concepts": ["remote", "right"],
        "forbidden": ["cats"],
        "path": ["search_history", "finish"],
    },
    {
        "name": "answered-clarification",
        "message": "The one on the right",
        "context": [
            {
                "transcript": "Where is the television remote control?",
                "answer": "Which one do you mean? Please describe its color, position, or another distinguishing detail.",
            }
        ],
        "concepts": ["remote", "right"],
        "path": ["inspect_current", "finish"],
    },
    {
        "name": "answered-material",
        "message": "The leather one",
        "context": [{"transcript": "Find my backpack", "answer": "Which backpack do you mean?"}],
        "concepts": ["leather", "backpack"],
        "path": ["inspect_current", "finish"],
    },
    {
        "name": "spatial-correction-right",
        "message": "I mean the remote on the right of the picture.",
        "context": [
            {
                "transcript": "Where is the television remote control?",
                "answer": "On the left beside a cat",
            }
        ],
        "concepts": ["remote", "right"],
        "forbidden": ["left"],
        "path": ["inspect_current", "finish"],
    },
    {
        "name": "spatial-correction-under",
        "message": "No, the one underneath the desk",
        "context": [{"transcript": "Find my backpack", "answer": "Beside the door"}],
        "concepts": ["backpack", "under", "desk"],
        "forbidden": ["door"],
        "path": ["inspect_current", "finish"],
    },
    {
        "name": "changed-object",
        "message": "Actually find my red mug instead",
        "context": [{"transcript": "Find my blue water bottle", "answer": "Unclear"}],
        "concepts": ["red", "mug"],
        "forbidden": ["blue", "bottle"],
        "path": ["inspect_current", "finish"],
    },
    {
        "name": "descriptive-current",
        "message": "Where is my blue water bottle?",
        "concepts": ["blue", "bottle"],
        "path": ["inspect_current", "finish"],
    },
    {
        "name": "corrected-attributes",
        "message": "No, the thin silver reading ones",
        "context": [{"transcript": "Where are my black glasses?", "answer": "Unclear"}],
        "concepts": ["thin", "silver", "reading", "glasses"],
        "forbidden": ["black"],
        "path": ["inspect_current", "finish"],
    },
    {
        "name": "historical-pronoun",
        "message": "Where did you last see it?",
        "context": [{"transcript": "Find my blue water bottle", "answer": "Unclear"}],
        "concepts": ["blue", "bottle"],
        "path": ["search_history", "finish"],
    },
    {
        "name": "widen-after-inconclusive",
        "message": "Where are my reading glasses?",
        "concepts": ["reading", "glasses"],
        "fixture": "widen",
        "path": ["inspect_current", "search_history", "search_history", "finish"],
        "hours": [2, 24],
    },
    {
        "name": "undated-import",
        "message": "Find the red mug in my imported clip",
        "concepts": ["red", "mug"],
        "fixture": "import",
        "current_view": False,
        "path": ["search_matches", "finish"],
    },
    {
        "name": "previous-answer-is-not-current-evidence",
        "message": "Is it still there?",
        "context": [
            {
                "transcript": "Find my television remote",
                "answer": "Seen yesterday by a drawer",
                "sources_available": True,
            }
        ],
        "concepts": ["remote"],
        "path": ["inspect_current", "finish"],
    },
    {
        "name": "no-camera-fallback",
        "message": "Where is my blue water bottle?",
        "concepts": ["blue", "bottle"],
        "fixture": "no-camera",
        "current_view": False,
        "status": "seen",
        "hours": [2],
    },
    {
        "name": "all-tools-inconclusive",
        "message": "Find my silver reading glasses",
        "concepts": ["silver", "reading", "glasses"],
        "fixture": "uncertain",
        "status": "uncertain",
        "min_history_windows": 2,
    },
    {
        "name": "cancel-exact-request",
        "message": "Cancel my water bottle reminder",
        "concepts": [],
        "fixture": "cancel",
        "path": ["cancel_reminder", "finish"],
        "status": "cancelled",
        "reminders": [
            {"id": "bottle-request", "message": "Take your water bottle", "state": "armed"}
        ],
    },
    {
        "name": "gratitude-no-search",
        "message": "Thanks!",
        "concepts": [],
        "path": ["chat"],
        "status": "chat",
    },
]


# These are controlled planner cases, not object-recognition evidence.
REVIEW_CONTEXT = [
    {
        "transcript": "Where did you last see my blue mug?",
        "answer": "Is this the item you mean?",
        "sources_available": True,
        "plan": {
            "steps": [
                {
                    "action": "search_history",
                    "query": "blue mug",
                    "hours": 2,
                    "excluded_frame_ids": [40],
                }
            ],
            "candidate": {"frame_id": 42, "object_query": "blue mug", "excluded_frame_ids": [40]},
        },
    }
]
CASES.extend(
    [
        {
            "name": "casual-candidate-rejection",
            "message": "nah man its not this item",
            "context": REVIEW_CONTEXT,
            "concepts": ["blue", "mug"],
            "required_exclusions": [40, 42],
            "history_only": True,
        },
        {
            "name": "candidate-rejection-with-detail",
            "message": "No, mine has a white handle. Look further back.",
            "context": REVIEW_CONTEXT,
            "concepts": ["mug", "white", "handle"],
            "required_exclusions": [40, 42],
            "history_only": True,
        },
        {
            "name": "new-object-after-candidate",
            "no_exclusions": True,
            "message": "Actually find my red backpack in the camera view instead",
            "context": REVIEW_CONTEXT,
            "concepts": ["red", "backpack"],
            "path": ["inspect_current", "finish"],
        },
    ]
)

CASES.extend(
    [
        {
            "name": "another-casual-rejection",
            "message": "That's somebody else's. Keep looking please.",
            "context": REVIEW_CONTEXT,
            "concepts": ["blue", "mug"],
            "required_exclusions": [40, 42],
            "history_only": True,
        },
        {
            "name": "candidate-thanks",
            "message": "Thanks for checking",
            "context": REVIEW_CONTEXT,
            "concepts": [],
            "path": ["chat"],
            "status": "chat",
        },
    ]
)


def score_case(case, result):
    queries = [step["query"].lower() for step in result["steps"] if "query" in step]
    path = [step["action"] for step in result["steps"]]
    hours = [step["hours"] for step in result["steps"] if "hours" in step]
    searches = [
        step for step in result["steps"] if step["action"] in {"search_history", "search_matches"}
    ]
    checks = {
        "status": result["status"] == case.get("status", "seen"),
        "query_concepts": all(all(word in query for word in case["concepts"]) for query in queries)
        and (bool(queries) or not case["concepts"]),
        "no_contradictory_attributes": all(
            not any(word in query for word in case.get("forbidden", [])) for query in queries
        ),
        "path": "path" not in case or path == case["path"],
        "hours": "hours" not in case or hours == case["hours"],
        "bounded": len(path) <= 6,
        "earlier_than_evidence": "before_frame_id" not in case
        or (
            bool(searches)
            and all(step.get("before_frame_id") == case["before_frame_id"] for step in searches)
        ),
        "rejected_frames": (not case.get("required_exclusions") or bool(searches))
        and all(
            set(case.get("required_exclusions", [])).issubset(step.get("excluded_frame_ids", []))
            for step in result["steps"]
            if step["action"] in {"search_history", "search_matches"}
        ),
        "no_stale_exclusions": not case.get("no_exclusions")
        or all(not step.get("excluded_frame_ids") for step in searches),
        "no_unrequested_rejection": all(
            not set(case.get("forbidden_exclusions", [])).intersection(
                step.get("excluded_frame_ids", [])
            )
            for step in searches
        ),
        "history_feedback": not case.get("history_only")
        or (
            bool(path)
            and path[0] in {"search_history", "search_matches"}
            and "inspect_current" not in path
        ),
        "requested_wider_window": "wider_than_hours" not in case
        or bool(hours)
        and (hours[0] == 0 or hours[0] > case["wider_than_hours"]),
        "history_coverage": len(set(hours)) >= case.get("min_history_windows", 0),
    }
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+")
    parser.add_argument("--case-file", type=Path, help="Separate JSON list of evaluation cases")
    parser.add_argument(
        "--natural-user-turn",
        action="store_true",
        help="Compare putting the latest request in its own user message",
    )
    parser.add_argument(
        "--thinking-tokens", type=int, default=0, help="Experimental MLX reasoning token budget"
    )
    parser.add_argument(
        "--model-id", help="Experimental MLX model override; requires a pinned revision"
    )
    parser.add_argument("--revision", help="Exact 40-character model commit")
    args = parser.parse_args()
    if bool(args.model_id) != bool(args.revision):
        parser.error("--model-id and --revision must be supplied together")
    if args.revision and (
        len(args.revision) != 40 or any(c not in "0123456789abcdef" for c in args.revision)
    ):
        parser.error("--revision must be an exact lowercase hexadecimal commit")
    if args.model_id:
        # Override only in this experiment process; application defaults stay pinned.
        from nyx import mlx_runtime

        mlx_runtime.MODEL, mlx_runtime.REVISION = args.model_id, args.revision
    cases = json.loads(args.case_file.read_text()) if args.case_file else CASES
    selected = [case for case in cases if not args.cases or case["name"] in args.cases]
    if args.cases and len(selected) != len(set(args.cases)):
        parser.error("Every requested case must exist")
    args.output.mkdir(parents=True, exist_ok=False)
    model = LocalVerifier()
    original = model.generate_json
    if args.thinking_tokens:
        from mlx_vlm import generate

        def thinking_generate(messages, max_tokens=240):
            prompt = model.runtime.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=True
            )
            result = generate(
                model.runtime.model,
                model.runtime.processor,
                prompt,
                max_tokens=args.thinking_tokens + max_tokens,
                thinking_budget=args.thinking_tokens,
                thinking_start_token="<think>",
                thinking_end_token="</think>",
                temperature=0.0,
                enable_thinking=True,
                verbose=False,
            ).text
            with (args.output / "thinking.jsonl").open("a") as file:
                file.write(json.dumps({"raw": result}) + "\n")
            if "</think>" not in result:
                raise ValueError("Reasoning did not finish within its token budget")
            return result.split("</think>", 1)[1].strip()

        original = thinking_generate

    def record(messages, max_tokens=240):
        if args.natural_user_turn:
            state = json.loads(messages[1]["content"])
            latest = state.pop("message")
            messages = [
                {
                    "role": "system",
                    "content": messages[0]["content"]
                    + "\nThe first user message is background context. The final user message is the current request.",
                },
                {"role": "user", "content": json.dumps(state)},
                {"role": "user", "content": latest},
            ]
        raw = original(messages, max_tokens)
        with (args.output / "raw.jsonl").open("a") as file:
            file.write(json.dumps({"messages": messages, "raw": raw}) + "\n")
        return raw

    model.generate_json = record
    results = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "runtime": {name: version(name) for name in ["torch", "transformers"]},
        "model": model.fingerprint,
        "load_seconds": model.load_seconds,
        "natural_user_turn": args.natural_user_turn,
        "thinking_tokens": args.thinking_tokens,
        "tools": "controlled observations; no actual retrieval or mutations",
        "scoring": "Query concept/contradiction checks and expected tool paths; manual review still required",
        "cases": [],
    }
    for case in selected:
        fixture = case.get("fixture")

        def tool(action, fixture=fixture):
            name = action["action"]
            if name == "cancel_reminder" and fixture == "cancel":
                if action["id"] != "bottle-request":
                    raise ValueError("Wrong request ID")
                return {"status": "cancelled", "answer": "Controlled tool: request cancelled"}
            if name not in {"inspect_current", "search_history", "search_matches"}:
                raise ValueError("Unexpected tool for this scenario")
            uncertain = (
                fixture == "uncertain"
                or (fixture == "widen" and not (name == "search_history" and action["hours"] == 24))
                or (fixture == "import" and name != "search_matches")
                or (fixture == "no-camera" and name == "inspect_current")
            )
            return {
                "kind": "snapshot" if name == "inspect_current" else "history",
                "status": "uncertain" if uncertain else "seen",
                "answer": "Controlled tool: inconclusive"
                if uncertain
                else "Controlled tool: sighting confirmed",
                "checked": [],
            }

        started = time.perf_counter()
        steps = agent_steps(
            case["message"],
            case.get("context", []),
            lambda state, case=case: model.decide(
                {**state, "reminders": case.get("reminders", [])}
            ),
            tool,
            available={
                "current_view": case.get("current_view", True),
                "history": True,
                "dated_history": fixture != "import",
                "undated_history": True,
            },
        )
        try:
            while True:
                next(steps)
        except StopIteration as done:
            result = done.value
        checks = score_case(case, result)
        row = {
            "case": case,
            "result": result,
            "checks": checks,
            "passed": all(checks.values()),
            "seconds": time.perf_counter() - started,
        }
        if model.device == "mlx":
            import mlx.core as mx

            results["mlx_peak_bytes"] = mx.get_peak_memory()
        results["cases"].append(row)
        (args.output / "results.json").write_text(json.dumps(results, indent=2))
        print(
            json.dumps(
                {
                    "name": case["name"],
                    "passed": row["passed"],
                    "checks": checks,
                    "steps": result["steps"],
                    "decision_errors": result["decision_errors"],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
