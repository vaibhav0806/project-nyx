from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest
from PIL import Image


@pytest.fixture
def live(monkeypatch):
    from nyx import observation

    base = datetime.now(UTC)
    clock = [base]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    monkeypatch.setattr(observation, "datetime", Clock)
    observer = observation.Observer()

    def feed(at, gray=100, session="session"):
        clock[0] = base + timedelta(seconds=at)
        return observer.feed(
            session, Image.new("RGB", (160, 96), (gray,) * 3), clock[0].isoformat()
        )

    return observer, feed, base


def test_short_flash_cannot_nominate_a_live_model_check(live):
    _, feed, _ = live
    for tick in range(31):
        assert feed(tick / 10, 200 if tick == 10 else 100) is None


def test_live_placement_waits_for_persistence_and_has_exact_three_sample_evidence(live):
    observer, feed, base = live
    assert feed(0) is None
    for tick in range(1, 6):
        assert feed(tick / 10, 200) is None
    burst = feed(0.6, 200)
    assert burst["activity"]["qualified"]
    assert burst["times"] == [(base + timedelta(seconds=at)).isoformat() for at in [0, 0.3, 0.6]]
    assert [image.getpixel((0, 0))[0] for image in burst["images"]] == [100, 200, 200]
    assert observer.accept(burst)
    for tick in range(7, 21):
        assert feed(tick / 10, 200) is None


def test_busy_worker_does_not_consume_an_unaccepted_nomination(live):
    observer, feed, _ = live
    feed(0)
    for tick in range(1, 7):
        burst = feed(tick / 10, 200)
    first_event = burst["event_id"]
    # Keep collecting while no model job can be admitted, including episode closure.
    for tick in range(7, 13):
        burst = feed(tick / 10, 200)
        assert burst["event_id"] == first_event
    assert observer.accept(burst)
    assert feed(1.3, 200) is None


def test_continuing_activity_rechecks_only_with_new_evidence_in_the_same_episode(live):
    observer, feed, _ = live
    feed(0)
    admitted = []
    for tick in range(1, 70):
        burst = feed(tick / 10, 150 + (tick % 3) * 40)
        if burst:
            assert observer.accept(burst)
            admitted.append((tick / 10, burst))
    assert len(admitted) == 7
    assert len({burst["event_id"] for _, burst in admitted}) == 1
    assert all(right[0] - left[0] >= 0.99 for left, right in pairwise(admitted))
    assert len(observer.frames) <= 64


def test_camera_reset_or_sample_gap_invalidates_old_event_evidence(live):
    observer, feed, _ = live
    feed(0)
    for tick in range(1, 7):
        burst = feed(tick / 10, 200)
    assert observer.valid(burst)
    assert feed(1.3, 200) is None
    assert not observer.valid(burst)
    assert not observer.accept(burst)
    assert feed(1.4, 200, session="different") is None
    observer.reset()
    assert feed(1.5, 200) is None


def test_live_burst_keeps_bounded_dense_tracking_samples_before_semantic_selection(live):
    observer, feed, _ = live
    feed(0)
    for tick in range(1, 61):
        burst = feed(tick / 10, 150 + (tick % 3) * 40)
    assert len(burst["images"]) == 3
    assert 25 <= len(burst["tracking_images"]) <= 32
    assert len(burst["tracking_images"]) == len(burst["tracking_times"])
    assert burst["tracking_times"][0] == burst["times"][0]
    assert burst["tracking_times"][-1] == burst["times"][-1]
    assert len(observer.frames) <= 64


def test_new_activity_episode_keeps_recent_track_context_from_before_its_boundary(live):
    _, feed, _ = live
    feed(0)
    for tick in range(1, 18):
        feed(tick / 10, 200)
    for tick in range(18, 25):
        burst = feed(tick / 10, 150 + (tick % 3) * 40)
    assert burst["tracking_times"][0] < burst["times"][0]


def test_old_out_of_order_or_interrupted_sequences_cannot_trigger_departure():
    import pytest

    from nyx.observation import Observer

    observer = Observer()
    now = datetime.now(UTC)
    image = Image.new("RGB", (160, 96))
    with pytest.raises(ValueError, match="fresh"):
        observer.feed("session-1", image, (now - timedelta(minutes=1)).isoformat())
    observer.feed("session-1", image, now.isoformat())
    with pytest.raises(ValueError, match="order"):
        observer.feed("session-1", image, (now - timedelta(seconds=1)).isoformat())


def test_long_quiet_monitoring_does_not_load_a_model_and_resumes_on_change(live):
    observer, feed, _ = live
    for tick in range(1201):
        assert feed(tick / 10, 100 + tick % 2) is None
    for tick in range(1201, 1207):
        burst = feed(tick / 10, 200)
    assert burst is not None
    assert len(burst["images"]) == len(burst["times"]) == 3
    assert observer.valid(burst)


def test_action_gate_matches_visual_and_temporal_evidence_to_current_requests(live):
    from nyx.observation import departure_action

    _, feed, base = live
    feed(0)
    for tick in range(1, 7):
        burst = feed(tick / 10, 200)
    judgment = {
        "departure": True,
        "uncertain": False,
        "approached_exit": True,
        "exit_interaction": True,
        "cue": "Synthetic approach and handle interaction",
        "region": {
            "label": "Synthetic exit",
            "kind": "exterior_exit",
            "box": [0.8, 0.1, 0.95, 0.8],
            "uncertain": False,
        },
        "entities": [
            [{"box": [x - 0.04, 0.4, x + 0.04, 0.6], "score": 0.9}] for x in [0.2, 0.5, 0.82]
        ],
    }
    older = {"id": "old", "state": "armed", "created_at": (base - timedelta(seconds=1)).isoformat()}
    newer = {
        "id": "new",
        "state": "armed",
        "created_at": (base + timedelta(seconds=0.2)).isoformat(),
    }
    cancelled = {**older, "id": "cancelled", "state": "cancelled"}
    result = departure_action(burst, judgment, [older, newer, cancelled])
    assert result["act"]
    assert result["request_ids"] == ["old"]
    assert not departure_action(
        burst, {**judgment, "region_consistency": {"state": "changed"}}, [older]
    )["act"]
    # Intermediate reversal is retained even when the three semantic images look positive.
    xs = [0.2, 0.3, 0.4, 0.5, 0.6, 0.58, 0.56, 0.54, 0.52, 0.5]
    full_track = {
        "observations": [[{"box": [x - 0.04, 0.4, x + 0.04, 0.6], "score": 0.9}] for x in xs]
    }
    assert not departure_action(burst, {**judgment, "tracking": full_track}, [older])["act"]
    # 2D door-box proximity is not physical distance. Consistent direction can
    # corroborate separately checked handle interaction before the feet reach it.
    toward = {
        "entities": [
            [{"box": [x - 0.04, 0.4, x + 0.04, 0.6], "score": 0.9}] for x in [0.2, 0.4, 0.65]
        ]
    }
    approach = departure_action(burst, {**judgment, **toward}, [older])
    assert approach["act"]
    assert approach["motion"]["relation"] == "toward"
    assert not departure_action(burst, {**judgment, **toward, "exit_interaction": False}, [older])[
        "act"
    ]
    assert not departure_action(burst, judgment, [newer, cancelled])["act"]
    assert not departure_action(burst, judgment, [])["act"]
    for patch in [
        {"uncertain": True},
        {"approached_exit": False},
        {"exit_interaction": False},
        {"departure": False},
        {"departure": "true"},
    ]:
        assert not departure_action(burst, {**judgment, **patch}, [older])["act"]
    assert not departure_action({**burst, "activity": {"qualified": False}}, judgment, [older])[
        "act"
    ]

    # Semantic booleans cannot override independent entering/stationary/turnback evidence.
    for points in [[0.82, 0.5, 0.2], [0.82, 0.82, 0.82], [0.3, 0.82, 0.4]]:
        spatial = {
            "entities": [[{"box": [x - 0.04, 0.4, x + 0.04, 0.6], "score": 0.9}] for x in points]
        }
        rejected = departure_action(
            burst, {**judgment, **spatial, "motion": {"relation": "approaching"}}, [older]
        )
        assert not rejected["act"]
        assert rejected["reason"] == "unconfirmed_approach"
    for region in [
        None,
        {**judgment["region"], "kind": "unknown"},
        {**judgment["region"], "uncertain": True},
    ]:
        rejected = departure_action(burst, {**judgment, "region": region}, [older])
        assert not rejected["act"]
        assert rejected["reason"] == "unresolved_exit"
    assert not departure_action(burst, {**judgment, "entities": [[], [], []]}, [older])["act"]


def test_departure_parser_cannot_promote_ambiguous_or_malformed_judgments():
    from nyx.observation import departure_judgment

    assert departure_judgment(
        '{"cue":"Person approaches exit and reaches for door handle","approached_exit":true,"exit_interaction":true,"departure":true,"uncertain":false}'
    )["departure"]
    for value in [
        "yes",
        '{"departure":"true","uncertain":false,"cue":"door"}',
        '{"departure":true,"uncertain":true,"cue":"Person is near a doorway"}',
        '{"cue":"Person stands still by a door","approached_exit":false,"exit_interaction":false,"departure":true,"uncertain":false}',
    ]:
        assert departure_judgment(value)["departure"] is False


def test_live_event_inspection_runs_before_a_backlog_of_background_jobs(tmp_path):
    from threading import Event

    import pytest

    pytest.importorskip("fastapi")
    from nyx.app import Workspace

    entered, release, inspected = Event(), Event(), Event()
    order = []
    workspace = Workspace(tmp_path, None, 1024**3, None)

    def running_batch():
        entered.set()
        assert release.wait(5)

    def observe():
        order.append("live-event")
        inspected.set()

    workspace.thread.start()
    try:
        workspace.submit(workspace.reserve("capture"), running_batch)
        assert entered.wait(2)
        for _ in range(3):
            workspace.submit(workspace.reserve("capture"), lambda: order.append("background"))
        workspace.submit(workspace.reserve("observe"), observe)
        release.set()
        assert inspected.wait(2)
    finally:
        release.set()
        workspace.close()
    assert order == ["live-event", "background", "background", "background"]
