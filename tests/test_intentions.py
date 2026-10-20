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


def test_active_request_stays_visible_after_more_than_thirty_closed_requests(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    active = tasks.create("long-lived-request", "Take your water bottle")
    for index in range(31):
        other = tasks.create(f"closed-{index}", "Take keys")
        tasks.cancel(other["id"])
    visible = tasks.recent()
    assert any(row["id"] == active["id"] and row["state"] == "armed" for row in visible)
    assert len(visible) == 31


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


def test_event_action_gate_only_claims_the_eligible_request_ids(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    first = tasks.create("first", "Take water")
    other = tasks.create("other", "Take keys")
    deliveries = tasks.trigger(
        "event", datetime.now(UTC).isoformat(), {}, request_ids=[first["id"]]
    )
    assert [row["intention_id"] for row in deliveries] == [first["id"]]
    assert tasks.get(other["id"])["state"] == "armed"
    assert tasks.trigger("event", datetime.now(UTC).isoformat(), {}, request_ids=[]) == []


def test_old_or_pre_request_events_never_trigger_a_reminder(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("turn-1", "Take your water bottle")
    old = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
    assert tasks.trigger("old-event", old, {}) == []
    assert tasks.get(item["id"])["state"] == "armed"
    with pytest.raises(ValueError):
        tasks.trigger("future-event", (datetime.now(UTC) + timedelta(minutes=1)).isoformat(), {})


def test_sequence_started_before_request_cannot_trigger_its_next_departure(tmp_path, monkeypatch):
    from nyx.intentions import Intentions

    clock = [datetime.now(UTC)]

    class Clock:
        @staticmethod
        def now(zone):
            return clock[0]

    monkeypatch.setattr("nyx.intentions.datetime", Clock)
    tasks = Intentions(tmp_path)
    older = tasks.create("older", "Take keys")
    clock[0] += timedelta(milliseconds=100)
    before = clock[0]
    clock[0] += timedelta(milliseconds=100)
    newer = tasks.create("newer", "Take water")
    clock[0] += timedelta(milliseconds=100)
    after = clock[0]
    evidence = {"frame_times": [before.isoformat(), after.isoformat()]}
    deliveries = tasks.trigger("straddling-sequence", after.isoformat(), evidence)
    assert [row["intention_id"] for row in deliveries] == [older["id"]]
    assert tasks.get(newer["id"])["state"] == "armed"
    # A complete new sequence still works, without recreating the request.
    start = clock[0] + timedelta(milliseconds=100)
    end = start + timedelta(milliseconds=1)
    clock[0] = end
    deliveries = tasks.trigger(
        "new-sequence", end.isoformat(), {"frame_times": [start.isoformat(), end.isoformat()]}
    )
    assert [row["intention_id"] for row in deliveries] == [newer["id"]]


@pytest.mark.parametrize("times", [[], ["bad"], [None], "not-a-sequence"])
def test_malformed_sequence_times_cannot_claim_a_reminder(tmp_path, times):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("request", "Take water")
    with pytest.raises(ValueError, match="sequence"):
        tasks.trigger("event", datetime.now(UTC).isoformat(), {"frame_times": times})
    assert tasks.get(item["id"])["state"] == "armed"


def test_sequence_clock_must_be_ordered_and_end_at_event_time(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("request", "Take water")
    now = datetime.now(UTC)
    earlier = (now - timedelta(seconds=1)).isoformat()
    at = now.isoformat()
    for times in [[at, earlier], [earlier, earlier], [earlier, at, at]]:
        with pytest.raises(ValueError, match="sequence"):
            tasks.trigger("event", at, {"frame_times": times})
    assert tasks.get(item["id"])["state"] == "armed"


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


def test_expired_unclaimed_delivery_becomes_missed_without_replaying(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("turn-1", "Take water")
    tasks.trigger("event-1", datetime.now(UTC).isoformat(), {})
    old = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
    with tasks.connect() as db:
        db.execute("UPDATE deliveries SET observed_at=?", (old,))
    assert tasks.pending() == []
    assert tasks.get(item["id"])["state"] == "missed"
    assert tasks.trigger("event-2", datetime.now(UTC).isoformat(), {}) == []


def test_restart_marks_unclaimed_notification_missed_instead_of_replaying(tmp_path):
    from nyx.intentions import Intentions

    tasks = Intentions(tmp_path)
    item = tasks.create("turn-1", "Take water")
    tasks.trigger("event-1", datetime.now(UTC).isoformat(), {})
    reopened = Intentions(tmp_path)
    assert reopened.pending() == []
    assert reopened.get(item["id"])["state"] == "missed"
