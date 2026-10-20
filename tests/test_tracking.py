from nyx import events


def entity(x, y=0.8):
    return [{"box": [x - 0.04, y - 0.3, x + 0.04, y], "score": 0.9}]


def test_brief_misses_preserve_only_observed_positions_and_exact_image_indices():
    result = events.track_detections(
        [0, 0.2, 0.4, 0.6, 0.8, 1], [entity(0.2), entity(0.3), [], [], entity(0.6), entity(0.7)]
    )
    assert result["indices"] == [0, 1, 4, 5]
    assert result["gaps"] == [{"after": 0.2, "before": 0.8, "missing_times": [0.4, 0.6]}]
    assert result["state"] == "observed"
    assert result["selected_indices"] == [0, 4, 5]


def test_long_gaps_people_and_position_jumps_start_new_trajectories():
    cases = [
        (
            [0, 0.2, 1.2, 1.4, 1.6],
            [entity(0.2), entity(0.3), entity(0.6), entity(0.7), entity(0.8)],
        ),
        (
            [0, 0.2, 0.4, 0.6, 0.8],
            [entity(0.2), entity(0.3) * 2, entity(0.5), entity(0.6), entity(0.7)],
        ),
        (
            [0, 0.2, 0.4, 0.6, 0.8],
            [entity(0.1), entity(0.2), entity(0.8), entity(0.85), entity(0.9)],
        ),
    ]
    for times, detections in cases:
        result = events.track_detections(times, detections)
        assert result["indices"] == [2, 3, 4]
        assert result["selected_indices"] == [2, 3, 4]
        assert result["breaks"]


def test_stale_tail_does_not_turn_an_old_track_into_current_evidence():
    result = events.track_detections(
        [0, 0.2, 0.4, 1.4], [entity(0.2), entity(0.3), entity(0.4), []]
    )
    assert result["selected_indices"] == []
    assert result["state"] == "lost"
    brief = events.track_detections([0, 0.2, 0.4, 0.6], [entity(0.2), entity(0.3), entity(0.4), []])
    assert brief["state"] == "gap"
    assert brief["selected_indices"] == [0, 1, 2]
    assert brief["last_observed_at"] == 0.4


def test_dense_intermediate_turnback_cannot_hide_behind_three_selected_frames():
    # Each step is small; the cumulative reversal must still be visible.
    xs = [0.2 + i * 0.02 for i in range(16)] + [0.48 - i * 0.02 for i in range(6)]
    result = events.region_motion([0.8, 0.1, 0.95, 0.9], [entity(x) for x in xs])
    assert result["relation"] == "reversed"


def test_track_times_are_ordered_finite_and_match_the_observations():
    import pytest

    for times in [[0, 0, 0.2], [0.2, 0.1, 0.3], [0, float("nan"), 0.2], [0, 0.2]]:
        with pytest.raises(ValueError):
            events.track_detections(times, [entity(0.2), entity(0.3), entity(0.4)])


def test_scene_regions_check_same_view_and_keep_unknown_output_unknown():
    history = events.RegionHistory()
    region = {
        "label": "Visible exit",
        "kind": "exterior_exit",
        "uncertain": False,
        "box": [0.7, 0.1, 0.9, 0.9],
    }
    assert history.check("view-1", region)["state"] == "initial"
    assert (
        history.check("view-1", {**region, "box": [0.71, 0.1, 0.91, 0.9]})["state"] == "consistent"
    )
    moved = {**region, "box": [0.1, 0.1, 0.3, 0.9]}
    assert history.check("view-1", moved)["state"] == "changed"
    assert history.check("view-1", moved)["state"] == "consistent"
    assert history.check("view-2", region)["state"] == "initial"
    assert history.check("view-2", None)["state"] == "uncertain"
    assert history.check("view-2", region)["state"] == "initial"


def test_dense_inference_selects_observed_images_and_reuses_only_same_view_detections():
    import json
    from datetime import UTC, datetime, timedelta
    from typing import ClassVar

    from PIL import Image

    from nyx.verification import LocalVerifier

    class Detector:
        fingerprint: ClassVar = {"model": "synthetic-dense"}

        def __init__(self):
            self.seen = []

        def detect(self, images):
            self.seen.extend(image.getpixel((0, 0))[0] for image in images)
            positions = [0.2, 0.3, None, None, 0.6, 0.7, 0.8]
            return [
                entity(positions[image.getpixel((0, 0))[0]])
                if positions[image.getpixel((0, 0))[0]] is not None
                else []
                for image in images
            ]

    verifier = LocalVerifier.__new__(LocalVerifier)
    verifier.detector = Detector()
    inspected = []

    def generate(messages, max_tokens):
        inspected.append(
            [
                part["image"].getpixel((0, 0))[0]
                for part in messages[0]["content"]
                if part["type"] == "image"
            ]
        )
        return json.dumps(
            {
                "cue": "Synthetic approach",
                "departure": True,
                "uncertain": False,
                "approached_exit": True,
                "exit_interaction": True,
                "region": {
                    "label": "Exit",
                    "kind": "exterior_exit",
                    "box": [800, 100, 950, 900],
                    "uncertain": False,
                },
            }
        )

    verifier.generate_json = generate
    base = datetime(2026, 10, 20, tzinfo=UTC)
    times = [(base + timedelta(seconds=i / 5)).isoformat() for i in range(7)]
    images = [Image.new("RGB", (160, 96), (i, 0, 0)) for i in range(7)]
    result = verifier.inspect_departure(images[:6], times=times[:6], view_id="view-1")
    assert result["frame_indices"] == [0, 4, 5]
    assert inspected[-1] == [0, 4, 5]
    assert len(result["tracking"]["observations"]) == 4
    assert result["tracking"]["gaps"]
    result = verifier.inspect_departure(images[1:], times=times[1:], view_id="view-1")
    assert verifier.detector.seen == list(range(7))
    assert result["region_consistency"]["state"] == "consistent"
    verifier.inspect_departure(images[:6], times=times[:6], view_id="view-2")
    assert verifier.detector.seen == list(range(7)) + list(range(6))
