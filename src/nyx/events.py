"""Visible spatial evidence, independent of reminder content and event semantics."""

import math
from itertools import pairwise


def parse_region(value):
    """Validate VLM image coordinates (0..1000), keeping inference distinct from truth."""
    if not isinstance(value, dict) or value.get("uncertain") is not False:
        return None
    if any(
        not isinstance(value.get(key), str) or not 1 <= len(value[key].strip()) <= 160
        for key in ["label", "kind"]
    ):
        return None
    box = value.get("box")
    if not isinstance(box, list) or len(box) != 4 or any(type(x) not in {int, float} for x in box):
        return None
    normalized = [x / 1000 for x in box]
    if not valid_box(normalized):
        return None
    return {"label": value["label"], "kind": value["kind"], "box": normalized, "uncertain": False}


def normalize_detections(prediction, size, label=1):
    """Filter detector observations, normalizing actual-image xyxy coordinates."""
    width, height = size
    result = []
    for box, category, score in zip(
        prediction["boxes"], prediction["labels"], prediction["scores"], strict=True
    ):
        if category != label or not math.isfinite(score) or score < 0.6:
            continue
        normalized = [
            value / scale for value, scale in zip(box, [width, height, width, height], strict=True)
        ]
        if valid_box(normalized):
            result.append({"box": normalized, "score": score})
    return result


class ObjectDetector:
    """Lazy small CPU detector, reused for nominated images on the inference worker."""

    def __init__(self):
        from importlib.metadata import version

        from torchvision.models.detection import (
            SSDLite320_MobileNet_V3_Large_Weights,
            ssdlite320_mobilenet_v3_large,
        )

        weights = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1
        self.model = ssdlite320_mobilenet_v3_large(weights=weights, progress=False).eval().to("cpu")
        self.transform = weights.transforms()
        self.categories = weights.meta["categories"]
        self.fingerprint = {
            "model": "torchvision/ssdlite320_mobilenet_v3_large",
            "weights": "COCO_V1",
            "url": weights.url,
            "torchvision": version("torchvision"),
            "device": "cpu",
            "score_threshold": 0.6,
        }

    def detect(self, images, category="person"):
        import torch

        label = self.categories.index(category)
        with torch.inference_mode():
            predictions = self.model([self.transform(image.convert("RGB")) for image in images])
        return [
            normalize_detections(
                {key: value.cpu().tolist() for key, value in prediction.items()}, image.size, label
            )
            for image, prediction in zip(images, predictions, strict=True)
        ]


def valid_box(box):
    return (
        isinstance(box, list)
        and len(box) == 4
        and all(
            type(value) in {float, int} and math.isfinite(value) and 0 <= value <= 1
            for value in box
        )
        and box[0] < box[2]
        and box[1] < box[3]
    )


def entity_motion(observations):
    """Whether one entity has supported translation; no direction/intent inference."""
    result = {"relation": "unknown", "points": [], "policy": "entity-motion-v1"}
    if len(observations) != 3 or any(len(rows) != 1 for rows in observations):
        return {**result, "reason": "ambiguous_or_missing_entity"}
    boxes = [rows[0].get("box") for rows in observations]
    if not all(valid_box(box) for box in boxes):
        return {**result, "reason": "invalid_entity_box"}
    points = [[(box[0] + box[2]) / 2, box[3]] for box in boxes]
    span = max(math.dist(left, right) for left in points for right in points)
    return {
        **result,
        "relation": "moving" if span >= 0.08 else "stationary",
        "points": points,
        "span": span,
        "reason": "observed_geometry",
    }


def region_motion(region, observations):
    """Sparse image-plane relation for a single observed entity, never identity or intent.

    Coordinates use [0, 1] relative to each image. Bottom-center points approximate
    ground contact; perspective, occlusion and detector errors remain limitations.
    The three observations must come from ordered images in one continuous view.
    """
    result = {"relation": "unknown", "points": [], "distances": [], "policy": "region-motion-v1"}
    if not valid_box(region):
        return {**result, "reason": "unresolved_region"}
    trajectory = entity_motion(observations)
    if trajectory["relation"] == "unknown":
        return {**result, "reason": trajectory["reason"]}
    points = trajectory["points"]
    x1, y1, x2, y2 = region
    distances = [math.hypot(max(x1 - x, 0, x - x2), max(y1 - y, 0, y - y2)) for x, y in points]
    changes = [right - left for left, right in pairwise(distances)]
    # Global image-relative starting policies, deliberately independent of clip/event.
    if any(step < -0.03 for step in changes) and any(step > 0.03 for step in changes):
        relation = "reversed"
    elif distances[0] - distances[-1] >= 0.08:
        relation = "approaching" if distances[-1] <= 0.06 else "toward"
    elif distances[-1] - distances[0] >= 0.08:
        relation = "away"
    else:
        relation = "at_region" if distances[-1] <= 0.06 else "stationary"
    return {
        **result,
        "relation": relation,
        "reason": "observed_geometry",
        "points": points,
        "distances": distances,
    }
