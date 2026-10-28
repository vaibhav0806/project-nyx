"""Region-relative motion uses observations, without event labels or fixed layouts."""

import json
from typing import ClassVar

import pytest
from PIL import Image

from nyx import events


def observations(points):
    # The bottom center is the observed ground-contact proxy, not a known 3D position.
    return [[{"box": [x - 0.04, y - 0.2, x + 0.04, y], "score": 0.9}] for x, y in points]


def test_motion_follows_region_in_different_layouts_and_object_categories():
    right = [0.8, 0.1, 0.95, 0.8]
    trajectory = observations([(0.2, 0.6), (0.5, 0.6), (0.82, 0.6)])
    result = events.region_motion(right, trajectory)
    assert result["relation"] == "approaching"
    assert result["points"] == [[0.2, 0.6], [0.5, 0.6], [0.82, 0.6]]
    assert result["distances"] == pytest.approx([0.6, 0.3, 0])
    # Reflect the camera layout. No known side, doorway or bottle is in the algorithm.
    reflected = observations([(0.8, 0.6), (0.5, 0.6), (0.18, 0.6)])
    assert events.region_motion([0.05, 0.1, 0.2, 0.8], reflected)["relation"] == "approaching"
    assert events.region_motion(right, list(reversed(trajectory)))["relation"] == "away"
    assert (
        events.region_motion(
            [0.2, 0.1, 0.8, 0.3], observations([(0.5, 0.95), (0.5, 0.6), (0.5, 0.3)])
        )["relation"]
        == "approaching"
    )


@pytest.mark.parametrize(
    "points,relation",
    [
        ([(0.4, 0.6), (0.41, 0.6), (0.4, 0.6)], "stationary"),
        ([(0.82, 0.6), (0.83, 0.6), (0.82, 0.6)], "at_region"),
        ([(0.2, 0.6), (0.5, 0.6), (0.65, 0.6)], "toward"),
        ([(0.3, 0.6), (0.82, 0.6), (0.4, 0.6)], "reversed"),
        ([(0.2, 0.6), (0.82, 0.6), (0.94, 0.95)], "reversed"),
    ],
)
def test_nearby_activity_does_not_establish_a_final_approach(points, relation):
    assert events.region_motion([0.8, 0.1, 0.95, 0.8], observations(points))["relation"] == relation


@pytest.mark.parametrize(
    "region,rows",
    [
        (None, observations([(0.2, 0.6)] * 3)),
        ([0.8, 0.1, 0.7, 0.8], observations([(0.2, 0.6)] * 3)),
        ([0.8, 0.1, 1.2, 0.8], observations([(0.2, 0.6)] * 3)),
        ([False, 0.1, 0.95, 0.8], observations([(0.2, 0.6)] * 3)),
        ([float("nan"), 0.1, 0.95, 0.8], observations([(0.2, 0.6)] * 3)),
        ([0.8, 0.1, 0.95, 0.8], [[], [], []]),
        ([0.8, 0.1, 0.95, 0.8], observations([(0.2, 0.6)] * 2)),
        ([0.8, 0.1, 0.95, 0.8], observations([(0.2, 0.6)] * 3) + [[]]),
        ([0.8, 0.1, 0.95, 0.8], [[{"box": [0, 0, 1, 1], "score": 0.9}]] * 2 + [[]]),
        ([0.8, 0.1, 0.95, 0.8], [observations([(0.2, 0.6)])[0] * 2] * 3),
    ],
)
def test_missing_ambiguous_or_malformed_evidence_abstains(region, rows):
    assert events.region_motion(region, rows)["relation"] == "unknown"


def test_detector_normalization_preserves_boxes_scores_and_other_entity_categories():
    prediction = {
        "boxes": [[20, 10, 100, 90], [40, 30, 80, 80], [50, 20, 120, 90], [0, 0, 200, 100]],
        "labels": [1, 1, 2, 1],
        "scores": [0.9, 0.2, 0.95, float("nan")],
    }
    result = events.normalize_detections(prediction, (200, 100), label=1)
    assert result == [{"box": [0.1, 0.1, 0.5, 0.9], "score": 0.9}]
    assert events.normalize_detections(prediction, (200, 100), label=2) == [
        {"box": [0.25, 0.2, 0.6, 0.9], "score": 0.95}
    ]


def test_model_region_is_validated_before_using_it_for_geometry():
    region = {
        "label": "Visible front exit",
        "kind": "exterior_exit",
        "box": [800, 100, 950, 800],
        "uncertain": False,
    }
    assert events.parse_region(region) == {**region, "box": [0.8, 0.1, 0.95, 0.8]}
    for patch in [
        {"box": [800, 100, 750, 800]},
        {"box": [800, 100, 1001, 800]},
        {"box": [False, 100, 950, 800]},
        {"box": [800, 100, "950", 800]},
        {"uncertain": True},
        {"uncertain": "false"},
        {"label": ""},
        {"kind": None},
    ]:
        assert events.parse_region({**region, **patch}) is None
    assert events.parse_region(None) is None
    assert events.parse_region([]) is None


def test_local_inspection_retains_independent_geometry_even_when_semantics_disagree():
    from nyx.verification import CloudVerifier

    class Detector:
        fingerprint: ClassVar = {"model": "synthetic-box-observations"}

        def detect(self, images):
            return observations([(0.82, 0.6), (0.5, 0.6), (0.2, 0.6)])

    verifier = CloudVerifier.__new__(CloudVerifier)
    verifier.detector = Detector()
    verifier.generate_json = lambda *args: json.dumps(
        {
            "departure": True,
            "uncertain": False,
            "approached_exit": True,
            "exit_interaction": True,
            "cue": "Incorrect semantic departure claim",
            "region": {
                "label": "Exit",
                "kind": "exterior_exit",
                "box": [800, 100, 950, 800],
                "uncertain": False,
            },
            "motion": {"relation": "approaching"},  # Model cannot supply measured geometry.
            "tracking": {"observations": observations([(0.2, 0.6), (0.5, 0.6), (0.82, 0.6)])},
        }
    )
    result = verifier.inspect_departure([Image.new("RGB", (160, 96)) for _ in range(3)])
    assert result["motion"]["relation"] == "away"
    assert result["region"]["box"] == [0.8, 0.1, 0.95, 0.8]
    assert result["detector"] == Detector.fingerprint
    assert result["tracking"] is None


def test_missing_entity_does_not_spend_a_semantic_inference_or_establish_absence():
    from nyx.verification import CloudVerifier

    class Detector:
        fingerprint: ClassVar = {"model": "synthetic-missed-detection"}

        def detect(self, images):
            return [[], [], []]

    verifier = CloudVerifier.__new__(CloudVerifier)
    verifier.detector = Detector()

    def unexpected(*args):
        pytest.fail("No complete trajectory; do not run semantic inference")

    verifier.generate_json = unexpected
    result = verifier.inspect_departure([Image.new("RGB", (160, 96)) for _ in range(3)])
    assert result["uncertain"]
    assert not result["departure"]
    assert result["motion"]["relation"] == "unknown"


def test_stationary_subject_preserves_semantic_capacity_for_later_movement():
    from nyx.verification import CloudVerifier

    class Detector:
        fingerprint: ClassVar = {"model": "synthetic-stationary-detection"}

        def detect(self, images):
            return observations([(0.4, 0.6), (0.41, 0.6), (0.4, 0.6)])

    verifier = CloudVerifier.__new__(CloudVerifier)
    verifier.detector = Detector()
    verifier.generate_json = lambda *args: pytest.fail(
        "Stationary positions cannot establish approach"
    )
    result = verifier.inspect_departure([Image.new("RGB", (160, 96)) for _ in range(3)])
    assert not result["departure"]
    assert result["motion"]["relation"] == "stationary"
    assert result["motion"]["points"] == [[0.4, 0.6], [0.41, 0.6], [0.4, 0.6]]
