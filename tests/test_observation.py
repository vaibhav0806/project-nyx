from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image


def test_observer_requires_a_fresh_sequence_and_resets_on_camera_session_change():
    from nyx.observation import Observer

    observer = Observer()
    now = datetime.now(UTC)
    image = Image.new("RGB", (160, 96), "gray")
    assert observer.feed("session-1", image, (now - timedelta(seconds=2)).isoformat()) is None
    assert observer.feed("session-1", image, (now - timedelta(seconds=1)).isoformat()) is None
    changed = Image.new("RGB", (160, 96), "white")
    burst = observer.feed("session-1", changed, now.isoformat())
    assert len(burst["images"]) == 3
    assert observer.valid(burst)
    observer.reset()
    assert not observer.valid(burst)
    assert observer.feed("session-2", changed, now.isoformat()) is None


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


def test_burst_metadata_describes_exactly_the_three_images_checked():
    from nyx.observation import Observer

    observer = Observer()
    now = datetime.now(UTC)
    times = [(now + timedelta(seconds=index - 4.5)).isoformat() for index in range(6)]
    for index, at in enumerate(times):
        burst = observer.feed("session", Image.new("RGB", (160, 96), (index * 30,) * 3), at)
    # The verifier checks first/middle/last; evidence must not name uninspected frames.
    assert burst["times"] == [times[0], times[3], times[5]]
    assert [image.getpixel((0, 0))[0] for image in burst["images"]] == [0, 90, 150]


@pytest.mark.parametrize("colors", [[100, 100, 100], [100, 101, 100]])
def test_unchanged_live_sequence_cannot_nominate_a_departure_check(colors):
    from nyx.observation import Observer

    observer = Observer()
    now = datetime.now(UTC)
    for index, gray in enumerate(colors):
        image = Image.new("RGB", (160, 96), (gray,) * 3)
        assert (
            observer.feed("session", image, (now + timedelta(seconds=index - 2)).isoformat())
            is None
        )


def test_slow_cumulative_change_is_not_lost_by_the_live_motion_gate():
    from nyx.observation import Observer

    observer = Observer()
    now = datetime.now(UTC)
    for index, gray in enumerate([100, 105, 110]):
        image = Image.new("RGB", (160, 96), (gray,) * 3)
        burst = observer.feed("session", image, (now + timedelta(seconds=index - 2)).isoformat())
    assert burst is not None


def test_quiet_monitoring_stays_local_across_periodic_checks_and_then_resumes(monkeypatch):
    from nyx import observation

    now = datetime.now(UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(observation, "datetime", Clock)
    observer = observation.Observer()
    still = Image.new("RGB", (160, 96), "gray")
    for _ in range(120):
        now += timedelta(seconds=1)
        assert observer.feed("session", still, now.isoformat()) is None
    now += timedelta(seconds=1)
    burst = observer.feed("session", Image.new("RGB", (160, 96), "white"), now.isoformat())
    assert burst is not None
    assert len(burst["images"]) == len(burst["times"]) == 3


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
