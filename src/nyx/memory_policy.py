"""Query-aware report priority and temporal eligibility; never source expiry or truth scoring."""

import math
from datetime import UTC, datetime

from nyx.memory import aware_time

POLICY_VERSION = "nyx-memory-v1"


def clock_time(value=None):
    value = value if value is not None else datetime.now(UTC)
    return aware_time(value.isoformat() if isinstance(value, datetime) else value)


def memory_priority(
    relevance, source_at, *, now=None, half_life_days=7, recency_weight=0, intent="current"
):
    if (
        not math.isfinite(relevance)
        or not math.isfinite(half_life_days)
        or half_life_days <= 0
        or not math.isfinite(recency_weight)
        or not 0 <= recency_weight <= 1
        or intent not in {"current", "historical", "last_seen", "reported"}
    ):
        raise ValueError("Invalid memory priority parameters")
    at = clock_time(source_at) if source_at is not None else None
    current = clock_time(now)
    result = {
        "policy_version": POLICY_VERSION,
        "relevance": float(relevance),
        "eligible": True,
        "freshness": None,
        "age_days": None,
        "priority": float(relevance),
    }
    if at is not None:
        age = (current - at).total_seconds() / 86400
        if age < 0:
            return {**result, "eligible": False, "priority": None, "reason": "future_report"}
        result.update(age_days=age, freshness=2 ** (-age / half_life_days))
    weight = recency_weight if intent == "current" else 0
    result["priority"] += max(0, relevance) * weight * (result["freshness"] or 0)
    return result
