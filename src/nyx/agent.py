"""A bounded observe/act loop. Visual claims come from tool results, never final prose."""

import json
import time
from datetime import UTC, datetime
from types import GeneratorType


def validate_action(value):
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        value = json.loads(text)
    if not isinstance(value, dict):
        raise TypeError("Expected one tool decision")
    action = value.get("action")
    fields = {
        "inspect_current": {"query"},
        "search_history": {"query", "hours"},
        "remind_on_departure": {"message"},
        "list_reminders": set(),
        "cancel_reminder": {"id"},
        "finish": {"observation"},
        "clarify": {"message"},
        "chat": {"message"},
    }
    if action not in fields or set(value) != fields[action] | {"action"}:
        raise ValueError("Unknown tool or unexpected decision fields")
    for key in fields[action] - {"hours", "observation"}:
        if not isinstance(value[key], str) or not 1 <= len(value[key].strip()) <= 240:
            raise ValueError("Tool text must be 1–240 characters")
    if action == "search_history" and (
        type(value["hours"]) is not int or value["hours"] not in {0, 2, 24, 168}
    ):
        raise ValueError("Choose recent 2/24/168 hours, or 0 for all dated history")
    if action == "finish" and (type(value["observation"]) is not int or value["observation"] < 0):
        raise ValueError("Completion must identify a tool observation")
    return value


def agent_steps(message, context, decide, tool, *, cancelled=lambda: False, max_steps=6):
    started = time.monotonic()
    observations = []
    trace = []
    result = {
        "kind": "agent",
        "status": "uncertain",
        "answer": "I couldn't finish that check. Please try a more specific request.",
        "sources": [],
        "steps": trace,
    }
    state = {
        "message": message,
        "conversation": context[-12:],
        "observations": observations,
        "now": datetime.now(UTC).isoformat(),
    }
    for _ in range(max_steps):
        if cancelled():
            raise ValueError("Request cancelled")
        if time.monotonic() - started > 90:
            break
        try:
            action = validate_action(decide(state))
        except (ValueError, TypeError, KeyError):
            result["answer"] = (
                "I couldn't interpret the next step reliably. Please clarify your request."
            )
            break
        if cancelled():
            raise ValueError("Request cancelled")
        if action in trace:
            result["answer"] = (
                "I couldn't find more evidence with that search. Try describing the object or time more precisely."
            )
            break
        trace.append(action)
        if action["action"] == "finish":
            index = action["observation"]
            if index < len(observations):
                selected = observations[index]
                result.update(
                    answer=selected["answer"],
                    status=selected.get("status", "complete"),
                    visual=selected if selected.get("kind") in {"snapshot", "history"} else None,
                )
            break
        if action["action"] in {"chat", "clarify"}:
            # After tools, completion must cite a result rather than inventing a replacement.
            if observations and action["action"] == "chat":
                break
            result.update(status=action["action"], answer=action["message"])
            break
        try:
            observation = tool(action)
            if isinstance(observation, GeneratorType):
                observation = yield from observation
        except ValueError as exc:
            observation = {"status": "uncertain", "answer": str(exc)}
        observations.append(observation)
        # Only compact evidence summaries are sent back to the deciding model.
        state["observations"] = [
            {
                "index": i,
                "status": row.get("status"),
                "answer": row["answer"][:700],
                "kind": row.get("kind"),
            }
            for i, row in enumerate(observations)
        ]
        yield {"step": len(trace), "action": action["action"], "status": observation.get("status")}
    if cancelled():
        raise ValueError("Request cancelled")
    result["sources"] = sorted(
        {row["video_id"] for observation in observations for row in observation.get("checked", [])}
    )
    result["checked"] = [
        row for observation in observations for row in observation.get("checked", [])
    ]
    result["observations"] = observations
    return result
