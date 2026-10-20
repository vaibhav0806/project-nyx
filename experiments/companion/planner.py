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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+")
    args = parser.parse_args()
    selected = [case for case in CASES if not args.cases or case["name"] in args.cases]
    if args.cases and len(selected) != len(set(args.cases)):
        parser.error("Every requested case must exist")
    args.output.mkdir(parents=True, exist_ok=False)
    model = LocalVerifier()
    original = model.generate_json

    def record(messages, max_tokens=240):
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
        queries = [step["query"].lower() for step in result["steps"] if "query" in step]
        path = [step["action"] for step in result["steps"]]
        hours = [step["hours"] for step in result["steps"] if "hours" in step]
        checks = {
            "status": result["status"] == case.get("status", "seen"),
            "query_concepts": all(
                all(word in query for word in case["concepts"]) for query in queries
            )
            and (bool(queries) or not case["concepts"]),
            "no_contradictory_attributes": all(
                not any(word in query for word in case.get("forbidden", [])) for query in queries
            ),
            "path": "path" not in case or path == case["path"],
            "hours": "hours" not in case or hours == case["hours"],
            "bounded": len(path) <= 6,
            "history_coverage": len(set(hours)) >= case.get("min_history_windows", 0),
        }
        row = {
            "case": case,
            "result": result,
            "checks": checks,
            "passed": all(checks.values()),
            "seconds": time.perf_counter() - started,
        }
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
