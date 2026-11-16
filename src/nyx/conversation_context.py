"""Bound provider context without rewriting durable transcripts or summarizing evidence."""

import json

from nyx.cloud import CloudError


def _reference(value):
    if not isinstance(value, dict):
        return None
    result = {}
    for key in ["frame_id", "before_frame_id", "hours"]:
        if type(value.get(key)) is int and value[key] >= 0:
            result[key] = value[key]
    for key, length in [
        ("action", 64),
        ("query", 240),
        ("object_query", 240),
        ("observed_at", 64),
        ("video_id", 128),
        ("turn_id", 128),
        ("at", 64),
        ("as_of", 64),
        ("selection", 32),
        ("object_description", 240),
        ("kind", 64),
    ]:
        if isinstance(value.get(key), str):
            result[key] = value[key][:length]
    if isinstance(value.get("excluded_frame_ids"), list):
        result["excluded_frame_ids"] = [
            i for i in value["excluded_frame_ids"] if type(i) is int and i >= 0
        ][-32:]
    return result


def recent_context(turns, *, max_turns=12, max_chars=12000):
    if not 1 <= max_turns <= 12 or not 1000 <= max_chars <= 32000:
        raise ValueError("Invalid conversation context budget")
    selected = []
    for source in reversed(turns):
        if source.get("status", "complete") != "complete":
            continue
        available = source.get("sources_available", True)
        text = source.get("transcript") or ""
        answer = (source.get("answer") or "") if available else ""
        row = {
            "status": "complete",
            "transcript": text[:1500],
            "answer": answer[:1200],
            "sources_available": bool(available),
            "plan": {},
        }
        for key in ["id", "at"]:
            if isinstance(source.get(key), str):
                row[key] = source[key][:128]
        if len(text) > 1500 or len(answer) > 1200 or source.get("context_truncated"):
            row["context_truncated"] = True
        plan = source.get("plan") or {}
        row["plan"]["mode"] = str(plan.get("mode", ""))[:64]
        query = next(
            (
                step
                for step in reversed(plan.get("steps", []))
                if isinstance(step, dict) and step.get("query")
            ),
            None,
        )
        row["plan"]["steps"] = [_reference(query)] if query else []
        if available:
            for key in ["candidate", "presented_candidate"]:
                if plan.get(key):
                    row["plan"][key] = _reference(plan[key])
            row["plan"]["statement_refs"] = [
                _reference(ref)
                for ref in plan.get("statement_refs", [])[-3:]
                if isinstance(ref, dict)
            ]
        trial = [row, *selected]
        if len(json.dumps(trial, ensure_ascii=False)) > max_chars:
            # Never skip a recent turn then silently reconnect a pronoun to an older one.
            break
        selected = trial
        if len(selected) == max_turns:
            break
    return selected


def bounded_live_context(chat_ctx, *, max_chars=24000, max_items=48, source_availability=None):
    """Keep whole user/tool exchanges. Budget counts text, not media or model tokens."""
    from livekit.agents import llm

    if max_chars < 1000 or max_items < 3:
        raise ValueError("Invalid spoken context budget")
    instructions, groups = [], []
    for item in chat_ctx.items:
        if not groups and item.type == "message" and item.role in {"system", "developer"}:
            instructions.append(item)
            continue
        if not groups or (item.type == "message" and item.role == "user"):
            groups.append([])
        groups[-1].append(item)

    def size(items):
        return sum(
            len(getattr(item, "text_content", "") or "")
            + len(getattr(item, "arguments", "") or "")
            + len(getattr(item, "output", "") or "")
            for item in items
        )

    if len(instructions) > max_items or size(instructions) > max_chars:
        raise CloudError("I couldn't finish that request. Please try a more specific question.")
    kept = []
    for group in reversed(groups):
        if (source_availability or {}).get(group[0].id) is False:
            # Retain the user query but withhold stale answers, tool results and candidate metadata.
            group = [
                group[0],
                llm.ChatMessage(
                    role="assistant",
                    content=[
                        'Earlier turn source state: {"sources_available": false}. Its assistant/tool evidence is withheld; retrieve available records or clarify.'
                    ],
                ),
                *[
                    item
                    for item in group[1:]
                    if item.type == "message" and item.role in {"system", "developer"}
                ],
            ]
        trial = [*instructions, *group, *kept]
        if len(trial) > max_items or size(trial) > max_chars:
            if not kept:
                raise CloudError(
                    "I couldn't finish that request. Please try a more specific question."
                )
            break
        kept = [*group, *kept]
    return llm.ChatContext(items=[*instructions, *kept])
