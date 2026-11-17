from nyx.cloud import CloudError

"""A bounded observe/act loop. Visual claims come from tool results, never final prose."""

import json
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
        "process_memory": set(),
        "recall_memory": {"query"},
        "identify_shown_object": set(),
        "search_history": {"query", "hours"},
        "search_matches": {"query"},
        "clarify": {"message"},
        "chat": {"message"},
    }
    if action not in fields:
        raise ValueError("Unknown tool")
    optional = {"excluded_frame_ids"} if action in {"search_history", "search_matches"} else set()
    if action == "search_history":
        optional.add("before_frame_id")
    if action == "recall_memory":
        optional.add("as_of")
    if "as_of" in value:
        if not isinstance(value["as_of"], str) or not 1 <= len(value["as_of"]) <= 64:
            raise ValueError("Historical report lookup needs an aware ISO timestamp")
        if datetime.fromisoformat(value["as_of"]).tzinfo is None:
            raise ValueError("Historical report lookup needs a timezone")
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
    for key in fields[action] - {"hours"}:
        if not isinstance(value[key], str) or not 1 <= len(value[key].strip()) <= 240:
            raise ValueError("Tool text must be 1–240 characters")
    if action == "search_history" and (
        type(value["hours"]) is not int or value["hours"] not in HISTORY_WINDOWS
    ):
        raise ValueError("Choose recent 2/24/168/240 hours, or 0 for all dated history")
    return value


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
    user_timezone=None,
    memory_context=None,
    validate_sources=None,
):
    """Native tool calls and final replies; execution guards never choose the next task."""
    from livekit.agents import ToolError

    from nyx.agent_policy import AGENT_INSTRUCTIONS
    from nyx.agent_tools import bind_tool_action, tool_schemas

    started = time.monotonic()
    observations, actions = ([memory_context] if memory_context else []), []
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
                {
                    "now": now or datetime.now(UTC).isoformat(),
                    "user_timezone": user_timezone,
                    "available": available or {},
                }
            ),
        }
    )
    messages.append({"role": "user", "content": message})
    if memory_context:
        messages.append(
            {
                "role": "system",
                "content": "Memory context: " + json.dumps(_model_tool_result(memory_context)),
            }
        )
    schemas = tool_schemas()
    cached = {}
    history_boundary = None

    def check_active():
        if cancelled():
            raise ValueError("Request cancelled")
        if time.monotonic() - started > 90:
            raise ValueError("Request time budget exceeded")
        if validate_sources is not None:
            validate_sources([source for row in observations for source in row.get("sources", [])])

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
        if len(actions) >= max_steps:
            raise ValueError("Request tool budget exceeded")
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
            if not isinstance(reply, dict) or reply.get("role") != "assistant":
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
                result["status"] = next(
                    (
                        row["status"]
                        for row in reversed(observations)
                        if row.get("status") != "noop"
                    ),
                    "answered",
                )
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
                    observation = {
                        "kind": "tool_error",
                        "status": "uncertain",
                        "answer": str(exc)[:240],
                    }
                    observations.append(observation)
                    result["decision_errors"].append(str(exc)[:240])
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(_model_tool_result(observation)),
                    }
                )
        else:
            result.update(
                status="uncertain", answer="I couldn't finish that request within the tool limit."
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
