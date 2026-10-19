from datetime import UTC, datetime, timedelta

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
