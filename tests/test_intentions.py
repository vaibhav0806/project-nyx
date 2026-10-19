from datetime import UTC, datetime, timedelta

import pytest


def test_next_departure_request_survives_restart_and_creation_replay(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    first = tasks.create("turn-1", "Take your water bottle")
    second = Intentions(tmp_path).create("turn-1", "Take your water bottle")
    assert first["id"] == second["id"]
    assert second["state"] == "armed"
    assert len(tasks.active()) == 1


def test_delivery_claim_is_atomic_and_cannot_replay_or_resurrect_cancelled_task(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("turn-1", "Take your water bottle")
    event_at = datetime.now(UTC).isoformat()
    delivery = tasks.trigger("event-1", event_at, {"cue": "approaching exit"})
    assert len(delivery) == 1
    assert tasks.trigger("event-1", event_at, {}) == []
    assert tasks.trigger("event-2", event_at, {}) == []
    tasks.cancel(item["id"])
    assert tasks.deliver(delivery[0]["id"]) is None
    assert tasks.get(item["id"])["state"] == "cancelled"


def test_old_or_pre_request_events_never_trigger_a_reminder(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("turn-1", "Take your water bottle")
    old = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
    assert tasks.trigger("old-event", old, {}) == []
    assert tasks.get(item["id"])["state"] == "armed"
    with pytest.raises(ValueError):
        tasks.trigger("future-event", (datetime.now(UTC) + timedelta(minutes=1)).isoformat(), {})


def test_restart_does_not_silently_repeat_a_partially_delivered_reminder(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("turn-1", "Take your water bottle")
    delivery = tasks.trigger("event-1", datetime.now(UTC).isoformat(), {})[0]
    assert tasks.deliver(delivery["id"])["state"] == "delivering"
    reopened = Intentions(tmp_path)
    assert reopened.get(item["id"])["state"] == "interrupted"
    assert reopened.pending() == []
    assert reopened.trigger("event-2", datetime.now(UTC).isoformat(), {}) == []


def test_playback_and_acknowledgement_are_distinct(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("turn-1", "Take your water bottle")
    delivery = tasks.trigger("event-1", datetime.now(UTC).isoformat(), {})[0]
    tasks.deliver(delivery["id"])
    tasks.finish(delivery["id"], "played")
    assert tasks.get(item["id"])["state"] == "delivered"
    tasks.acknowledge(item["id"])
    assert tasks.get(item["id"])["state"] == "acknowledged"
