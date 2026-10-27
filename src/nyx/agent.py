"""A bounded observe/act loop. Visual claims come from tool results, never final prose."""

import json
import re
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
        "search_matches": {"query"},
        "remind_on_departure": {"message"},
        "list_reminders": set(),
        "cancel_reminder": {"id"},
        "finish": {"observation"},
        "clarify": {"message"},
        "chat": {"message"},
    }
    if action not in fields:
        raise ValueError("Unknown tool")
    optional = {"excluded_frame_ids"} if action in {"search_history", "search_matches"} else set()
    if action == "search_history":
        optional.add("before_frame_id")
    allowed = fields[action] | {"action"}
    if set(value) - optional != allowed:
        raise ValueError(
            f"Unexpected decision fields for {action}; use exactly {', '.join(sorted(allowed))}. "
            f"Remove: {', '.join(sorted(set(value) - allowed - optional)) or 'none'}. "
            f"Missing: {', '.join(sorted(allowed - set(value))) or 'none'}."
        )
    if "excluded_frame_ids" in value:
        ids = value["excluded_frame_ids"]
        if (
            not isinstance(ids, list)
            or len(ids) > 32
            or any(type(i) is not int or i < 0 for i in ids)
        ):
            raise ValueError("excluded_frame_ids must be a list of up to 32 nonnegative frame IDs")
    if "before_frame_id" in value and (
        type(value["before_frame_id"]) is not int or value["before_frame_id"] < 0
    ):
        raise ValueError("before_frame_id must be a nonnegative saved frame ID")
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


def agent_steps(
    message,
    context,
    decide,
    tool,
    *,
    cancelled=lambda: False,
    max_steps=6,
    available=None,
    validate_tool=None,
):
    started = time.monotonic()
    observations = []
    trace = []
    history_boundary = None
    result = {
        "kind": "agent",
        "status": "uncertain",
        "answer": "I couldn't finish that check. Please try a more specific request.",
        "sources": [],
        "steps": trace,
        "decision_errors": [],
        "policy_adjustments": [],
    }
    state = {
        "message": message,
        "conversation": context[-12:],
        "observations": observations,
        "actions": trace,
        "available": available or {},
        "now": datetime.now(UTC).isoformat(),
    }
    for _ in range(max_steps):
        if cancelled():
            raise ValueError("Request cancelled")
        if time.monotonic() - started > 90:
            break
        try:
            action = validate_action(decide(state))
            if validate_tool is not None:
                validate_tool(action)
            if (
                action["action"] in {"search_history", "search_matches", "inspect_current"}
                and history_boundary is not None
                and action.get("before_frame_id") != history_boundary
            ):
                raise ValueError(
                    f"This request is constrained to moments before frame {history_boundary}; retain before_frame_id when continuing the search."
                )
            if action in trace and action["action"] == "search_history":
                windows = [2, 24, 168, 0]
                next_hours = next(
                    (
                        hours
                        for hours in windows[windows.index(action["hours"]) + 1 :]
                        if {**action, "hours": hours} not in trace
                    ),
                    None,
                )
                if next_hours is not None:
                    advanced = {**action, "hours": next_hours}
                    result["policy_adjustments"].append(
                        {
                            "reason": "advance_repeated_window",
                            "from": action,
                            "to": advanced,
                        }
                    )
                    action = advanced
            if action["action"] == "finish" and action["observation"] >= len(observations):
                raise ValueError(
                    "That observation does not exist in this request; use a tool first"
                )
            if action in trace:
                raise ValueError(
                    "That tool was already checked; choose an untried search or finish"
                )
        except (ValueError, TypeError, KeyError) as exc:
            result["answer"] = (
                "I couldn't interpret the next step reliably. Please clarify your request."
            )
            if len(result["decision_errors"]) < 2:
                state["decision_error"] = (
                    f"Invalid previous decision: {str(exc)[:240]}. Choose a valid next action."
                )
                result["decision_errors"].append(state["decision_error"])
                continue
            break
        state.pop("decision_error", None)
        if cancelled():
            raise ValueError("Request cancelled")
        requested = action
        if (
            not observations
            and action["action"] == "inspect_current"
            and (available or {}).get("current_view") is False
            and (available or {}).get("history")
        ):
            action = (
                {"action": "search_matches", "query": action["query"]}
                if (available or {}).get("dated_history") is False
                else {"action": "search_history", "query": action["query"], "hours": 2}
            )
        if (
            not observations
            and action["action"] in {"inspect_current", "search_matches"}
            and re.search(
                r"\b(last (?:see|seen)|where did|historical|history)\b", message, re.IGNORECASE
            )
        ):
            # An explicit last-sighting request cannot be completed by a current view.
            action = (
                {"action": "search_matches", "query": action["query"]}
                if (available or {}).get("dated_history") is False
                and (available or {}).get("undated_history")
                else {"action": "search_history", "query": action["query"], "hours": 2}
            )
        if (
            not observations
            and (available or {}).get("current_view")
            and not action.get("excluded_frame_ids")
            and "before_frame_id" not in action
            and action["action"] in {"search_history", "search_matches"}
            and re.search(
                r"\b(where (?:is|are)|find|locate|still (?:there|here|visible)|(?:is it|are they) (?:there|here))\b",
                message,
                re.IGNORECASE,
            )
            and not re.search(
                r"\b(last|seen|ago|earlier|history|past|yesterday|before|did|recording|recorded|footage|video|clip|imported)\b",
                message,
                re.IGNORECASE,
            )
        ):
            # Product policy: present location starts with available fresh evidence.
            action = {"action": "inspect_current", "query": action["query"]}
        if (
            action != requested
            and action["action"] in {"search_history", "search_matches"}
            and "excluded_frame_ids" in requested
        ):
            action = {**action, "excluded_frame_ids": requested["excluded_frame_ids"]}
        if action != requested:
            result["policy_adjustments"].append(
                {
                    "reason": "match_evidence_to_request",
                    "from": requested,
                    "to": action,
                }
            )
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
                steps = observation
                try:
                    while True:
                        if cancelled():
                            raise ValueError("Request cancelled")
                        if time.monotonic() - started > 90:
                            raise ValueError("Request time budget exceeded")
                        try:
                            progress = next(steps)
                        except StopIteration as done:
                            observation = done.value
                            break
                        yield progress
                finally:
                    steps.close()
        except ValueError as exc:
            if cancelled():
                raise
            observation = {"status": "uncertain", "answer": str(exc)}
        observations.append(observation)
        if observation.get("scope", {}).get("before_frame_id") is not None:
            history_boundary = observation["scope"]["before_frame_id"]
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
    else:
        if observations and observations[-1].get("status") in {
            "seen",
            "candidate",
            "armed",
            "cancelled",
            "complete",
            "clarify",
        }:
            selected = observations[-1]
            result.update(
                answer=selected["answer"],
                status=selected["status"],
                visual=selected if selected.get("kind") in {"snapshot", "history"} else None,
            )
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
