from nyx.cloud import CloudError

"""A bounded observe/act loop. Visual claims come from tool results, never final prose."""

import json
import re
import time
from datetime import UTC, datetime
from types import GeneratorType

from nyx.conversation_context import recent_context

HISTORY_WINDOWS = (2, 24, 168, 240, 0)


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
        "remember_statement": set(),
        "identify_shown_object": set(),
        "search_statements": {"query"},
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
    if action == "finish":
        optional.add("statement_observation")
    if action == "remember_statement":
        optional.add("supersedes_turn_id")
    if action == "search_statements":
        optional.update({"as_of", "selection"})
    if "selection" in value and (
        not isinstance(value["selection"], str)
        or value["selection"] not in {"all", "latest_report"}
    ):
        raise ValueError("Choose all reports or latest_report")
    if "supersedes_turn_id" in value and (
        not isinstance(value["supersedes_turn_id"], str)
        or not 1 <= len(value["supersedes_turn_id"]) <= 128
        or value["supersedes_turn_id"].strip() != value["supersedes_turn_id"]
    ):
        raise ValueError("Correction must identify an existing saved report")
    if "as_of" in value:
        if not isinstance(value["as_of"], str) or not 1 <= len(value["as_of"]) <= 64:
            raise ValueError("Historical report lookup needs an aware ISO timestamp")
        if datetime.fromisoformat(value["as_of"]).tzinfo is None:
            raise ValueError("Historical report lookup needs a timezone")
    if "statement_observation" in value and (
        type(value["statement_observation"]) is not int or value["statement_observation"] < 0
    ):
        raise ValueError("Statement completion must identify a tool observation")
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
        type(value["hours"]) is not int or value["hours"] not in HISTORY_WINDOWS
    ):
        raise ValueError("Choose recent 2/24/168/240 hours, or 0 for all dated history")
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
        "conversation": recent_context(context),
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
            statement_index = action.get("statement_observation")
            if statement_index is not None and (
                statement_index >= len(observations)
                or observations[statement_index].get("kind") != "statements"
            ):
                raise ValueError("Completion must cite a saved-statement observation")
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
                windows = HISTORY_WINDOWS
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
        except CloudError:
            raise
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
                statement_index = action.get("statement_observation")
                if statement_index is not None:
                    statement = observations[statement_index]
                    if selected.get("kind") == "reference":
                        if selected.get("status") == "complete":
                            selected = statement
                        result["policy_adjustments"].append(
                            {"reason": "reference_is_not_location_evidence"}
                        )
                    else:
                        selected = {
                            **selected,
                            "answer": selected["answer"] + " " + statement["answer"],
                        }
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
        except CloudError:
            raise
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
                **(
                    {
                        "statement_refs": [
                            {
                                key: match.get(key)
                                for key in ["turn_id", "at", "object_description", "kind"]
                            }
                            for match in row.get("matches", [])[:3]
                        ]
                    }
                    if row.get("kind") == "statements"
                    else {}
                ),
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
    sources = {
        row["video_id"] for observation in observations for row in observation.get("checked", [])
    }
    for observation in observations:
        dependencies = observation.get("sources", [])
        if not isinstance(dependencies, list) or any(not isinstance(s, str) for s in dependencies):
            raise ValueError("Tool returned invalid source references")
        sources.update(dependencies)
    result["sources"] = sorted(sources)
    result["checked"] = [
        row for observation in observations for row in observation.get("checked", [])
    ]
    result["observations"] = observations
    return result


def _model_tool_result(value):
    """Send evidence metadata to the agent, without raw media or storage payloads."""
    if isinstance(value, dict):
        return {
            key: _model_tool_result(item)
            for key, item in value.items()
            if key not in {"snapshot_url", "image", "embedding", "thumbnail", "path"}
        }
    if isinstance(value, list):
        return [_model_tool_result(item) for item in value]
    return value


def native_agent_steps(
    message,
    context,
    generate,
    tool,
    *,
    cancelled=lambda: False,
    max_steps=6,
    available=None,
    validate_tool=None,
    initial_action=None,
    now=None,
):
    """Native tool calls and final replies; execution guards never choose the next task."""
    from livekit.agents import ToolError

    from nyx.agent_policy import AGENT_INSTRUCTIONS
    from nyx.agent_tools import bind_tool_action, tool_schemas

    started = time.monotonic()
    observations, actions = [], []
    result = {
        "kind": "agent",
        "status": "uncertain",
        "answer": "I couldn't finish that request.",
        "sources": [],
        "checked": [],
        "steps": actions,
        "decision_errors": [],
        "policy_adjustments": [],
        "visual": None,
        "observations": observations,
    }
    messages = [{"role": "system", "content": AGENT_INSTRUCTIONS}]
    for row in recent_context(context):
        messages.append({"role": "user", "content": row["transcript"]})
        if row.get("answer"):
            messages.append({"role": "assistant", "content": row["answer"]})
        metadata = {key: row.get(key) for key in ["at", "sources_available", "context_truncated"]}
        metadata["previous_tools"] = row.get("plan", {}).get("steps", [])
        metadata["candidate"] = row.get("plan", {}).get("candidate")
        metadata["statement_refs"] = row.get("plan", {}).get("statement_refs", [])
        messages.append(
            {"role": "assistant", "content": "Saved context metadata: " + json.dumps(metadata)}
        )
    messages.append(
        {
            "role": "system",
            "content": json.dumps(
                {"now": now or datetime.now(UTC).isoformat(), "available": available or {}}
            ),
        }
    )
    messages.append({"role": "user", "content": message})
    schemas = tool_schemas()
    cached = {}
    history_boundary = None

    def check_active():
        if cancelled():
            raise ValueError("Request cancelled")
        if time.monotonic() - started > 90:
            raise ValueError("Request time budget exceeded")

    def execute(action):
        nonlocal history_boundary
        check_active()
        action = validate_action(action)
        if validate_tool is not None:
            validate_tool(action)
        if (
            action["action"] in {"search_history", "search_matches", "inspect_current"}
            and history_boundary is not None
            and action.get("before_frame_id") != history_boundary
        ):
            raise ValueError(f"Retain before_frame_id={history_boundary} for this search")
        key = json.dumps(action, sort_keys=True)
        if key in cached:
            return cached[key]
        actions.append(action)
        observation = tool(action)
        if isinstance(observation, GeneratorType):
            try:
                while True:
                    check_active()
                    try:
                        yield next(observation)
                    except StopIteration as done:
                        observation = done.value
                        break
            finally:
                if isinstance(observation, GeneratorType):
                    observation.close()
        check_active()
        if not isinstance(observation, dict):
            raise TypeError("Tool returned an invalid result")
        observations.append(observation)
        cached[key] = observation
        if observation.get("scope", {}).get("before_frame_id") is not None:
            history_boundary = observation["scope"]["before_frame_id"]
        if observation.get("kind") in {"snapshot", "history"}:
            result["visual"] = observation
        result["status"] = observation.get("status", "uncertain")
        result["answer"] = observation.get("answer", "I couldn't finish that request.")
        yield {"step": len(actions), "action": action["action"], "status": result["status"]}
        return observation

    check_active()
    if initial_action is not None:
        initial_action = validate_action(initial_action)
        if initial_action["action"] in {"chat", "clarify"}:
            result.update(status=initial_action["action"], answer=initial_action["message"])
        else:
            yield from execute(initial_action)
    else:
        for _ in range(max_steps):
            check_active()
            reply = generate(messages, schemas)
            check_active()
            if not isinstance(reply, dict):
                raise CloudError("Agent returned an invalid reply")
            calls = reply.get("tool_calls") or []
            if not isinstance(calls, list) or len(calls) > 6:
                raise CloudError("Agent returned invalid tool calls")
            messages.append(reply)
            if not calls:
                answer = reply.get("content")
                if not isinstance(answer, str) or not answer.strip():
                    raise CloudError("Agent did not finish a usable answer")
                result["answer"] = answer.strip()
                if not observations:
                    result["status"] = "answered"
                break
            for call in calls:
                check_active()
                if not isinstance(call, dict) or not isinstance(call.get("id"), str):
                    raise CloudError("Agent tool call is missing its identifier")
                try:
                    function = call["function"]
                    action = bind_tool_action(function["name"], function["arguments"])
                    observation = yield from execute(action)
                except CloudError:
                    raise
                except (ValueError, TypeError, KeyError, ToolError) as exc:
                    check_active()
                    observation = {"status": "error", "answer": str(exc)[:240]}
                    result["decision_errors"].append(str(exc)[:240])
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(_model_tool_result(observation)),
                    }
                )
    check_active()
    sources = set()
    for observation in observations:
        dependencies = observation.get("sources", [])
        if not isinstance(dependencies, list) or any(
            not isinstance(item, str) for item in dependencies
        ):
            raise ValueError("Tool returned invalid source references")
        sources.update(dependencies)
        result["checked"].extend(observation.get("checked", []))
    sources.update(row["video_id"] for row in result["checked"] if row.get("video_id"))
    result["sources"] = sorted(sources)
    return result
