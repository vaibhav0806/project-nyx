import pytest
from PIL import Image, ImageDraw


def room(object_at=None):
    image = Image.new("RGB", (160, 96), "gray")
    if object_at is not None:
        ImageDraw.Draw(image).rectangle((object_at, 35, object_at + 18, 58), fill="white")
    return image


def test_a_tenth_second_disturbance_returning_to_baseline_never_qualifies():
    from nyx.activity import ActivityWindow

    window = ActivityWindow()
    for tick in range(31):
        result = window.observe(room(60) if tick == 10 else room(), tick / 10)
        assert result["qualified"] is False
    assert result["state"] == "quiet"


def test_fast_placement_qualifies_when_its_result_persists_before_settling():
    from nyx.activity import ActivityWindow

    window = ActivityWindow()
    window.observe(room(), 0)
    qualified = []
    for tick in range(1, 21):
        result = window.observe(room(60), tick / 10)
        if result["qualified"]:
            qualified.append((tick / 10, result))
    assert 0.5 <= qualified[0][0] <= 0.7
    assert qualified[0][1]["state"] in {"active", "settling"}
    assert len({row["event_id"] for _, row in qualified}) == 1
    assert result["state"] == "quiet"
    assert not result["qualified"]


def test_repeated_isolated_flashes_do_not_accumulate_into_sustained_activity():
    from nyx.activity import ActivityWindow

    window = ActivityWindow()
    for tick in range(51):
        result = window.observe(room(60) if tick % 3 == 1 else room(), tick / 10)
        assert not result["qualified"]


def test_continuing_motion_is_one_episode_and_later_motion_starts_another():
    from nyx.activity import ActivityWindow

    window = ActivityWindow()
    window.observe(room(), 0)
    events = set()
    for tick in range(1, 31):
        result = window.observe(room(35 + (tick % 4) * 15), tick / 10)
        if result["qualified"]:
            events.add(result["event_id"])
    assert len(events) == 1
    for tick in range(31, 45):
        result = window.observe(room(), tick / 10)
    assert result["state"] == "quiet"
    for tick in range(45, 55):
        result = window.observe(room(60), tick / 10)
        if result["qualified"]:
            assert result["event_id"] not in events


def test_dropped_samples_cannot_establish_persistence():
    from nyx.activity import ActivityWindow

    window = ActivityWindow()
    window.observe(room(), 0)
    window.observe(room(60), 0.1)
    result = window.observe(room(60), 1.5)
    assert not result["qualified"]
    assert result["discontinuity"]
    for at in [1.6, 1.7, 1.8]:
        assert not window.observe(room(60), at)["qualified"]


def test_elapsed_time_and_multiple_observations_are_both_required():
    from nyx.activity import ActivityWindow

    window = ActivityWindow()
    window.observe(room(), 0)
    for at in [0.1, 0.101, 0.102]:
        assert not window.observe(room(60), at)["qualified"]
    for at in [0.3, 0.5, 0.7]:
        result = window.observe(room(60), at)
    assert result["qualified"]


def test_exact_half_second_sampling_boundary_does_not_create_a_float_rounding_gap():
    from nyx.activity import ActivityWindow

    window = ActivityWindow()
    window.observe(room(), 0)
    for at in [0.1, 0.6, 1.1]:
        result = window.observe(room(60), at)
    assert result["qualified"]
    assert not result["discontinuity"]


@pytest.mark.parametrize("at", [float("nan"), float("inf"), -float("inf")])
def test_invalid_sample_time_is_rejected(at):
    from nyx.activity import ActivityWindow

    with pytest.raises(ValueError, match="finite"):
        ActivityWindow().observe(room(), at)


def test_backwards_clock_is_rejected():
    from nyx.activity import ActivityWindow

    window = ActivityWindow()
    window.observe(room(), 1)
    with pytest.raises(ValueError, match="order"):
        window.observe(room(), 0.9)


def test_selection_ignores_flash_and_keeps_before_during_and_settled_placement():
    from nyx.attention import select_activity_frames

    frames = []
    for tick in range(41):
        image = room(30) if tick == 5 else room(90) if tick >= 20 else room()
        frames.append((tick / 10, image))
    selected = select_activity_frames(frames)
    times = [at for at, _ in selected]
    assert 0 in times
    assert 0.5 not in times
    assert 1.9 in times
    assert any(2.0 <= at <= 2.7 for at in times)
    assert any(2.8 <= at <= 3.1 for at in times)
    assert len(selected) <= 6


def test_activity_selection_preserves_periodic_coverage_and_original_offsets():
    from nyx.attention import select_activity_frames

    frames = [(tick / 10, room()) for tick in range(911)]
    selected = select_activity_frames(frames)
    assert [at for at, _ in selected] == [0, 30, 60, 90]
