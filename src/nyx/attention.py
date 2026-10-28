"""Cheap local change detection. Selection is not a semantic observation."""

import numpy as np
from PIL import Image


def frame_pixels(image):
    return np.asarray(image.convert("L").resize((160, 96)), dtype=np.float32) / 255


def pixels_changed(left, right):
    difference = np.abs(left - right)
    blocks = difference.reshape(12, 8, 20, 8).mean(axis=(1, 3))
    return float(difference.mean()) > 0.035 or float(blocks.max()) > 0.12


class ChangeDetector:
    def __init__(self, heartbeat=30.0, gap=10.0):
        self.heartbeat = heartbeat
        self.gap = gap
        self.previous = None
        self.last_at = None
        self.selected_at = None
        self.settle = False

    def observe(self, image, at):
        if not np.isfinite(at):
            raise ValueError("Frame time must be finite")
        pixels = frame_pixels(image)
        reason = None
        changed = False
        if self.previous is None:
            reason = "initial"
        elif at <= self.last_at or at - self.last_at > self.gap:
            reason = "gap"
            self.settle = False
        else:
            # Local blocks prevent a small placed object being diluted by the whole room.
            changed = pixels_changed(pixels, self.previous)
            if changed:
                reason = "change"
            elif self.settle:
                reason = "settled"
            elif at - self.selected_at >= self.heartbeat:
                reason = "periodic"
        self.previous = pixels
        self.last_at = at
        self.settle = changed
        if reason:
            self.selected_at = at
        return {"selected": reason is not None, "reason": reason, "changed": changed}


def sequence_changed(images):
    """Motion nomination only; compare to the anchor to retain slow cumulative changes."""
    for image in images[1:]:
        detector = ChangeDetector()
        detector.observe(images[0], 0)
        if detector.observe(image, 1)["changed"]:
            return True
    return False


def select_frames(frames):
    """Return original (offset, image-or-path) rows, preserving actual timestamps."""
    detector = ChangeDetector()
    selected = set()
    for i, (at, source) in enumerate(frames):
        if isinstance(source, Image.Image):
            decision = detector.observe(source, at)
        else:
            with Image.open(source) as image:
                decision = detector.observe(image, at)
        if decision["selected"]:
            selected.add(i)
        if decision["changed"] and i:
            selected.add(i - 1)
    return [row for i, row in enumerate(frames) if i in selected]


def select_activity_frames(frames):
    """Dense cheap observations select sparse evidence; original rows retain offsets."""
    from nyx.activity import ActivityWindow

    window = ActivityWindow()
    selected = set()
    event_start = None
    selected_event = None
    last_selected = None
    for index, (at, source) in enumerate(frames):
        if isinstance(source, Image.Image):
            activity = window.observe(source, at)
        else:
            with Image.open(source) as image:
                activity = window.observe(image, at)
        if index == 0 or activity["discontinuity"]:
            selected.add(index)
            last_selected = at
        if activity["state"] == "collecting" and activity["started_at"] == at:
            event_start = index
        if activity["qualified"]:
            if activity["event_id"] != selected_event:
                selected.update([max(0, event_start - 1), event_start, index])
                selected_event = activity["event_id"]
                last_selected = at
            elif activity["closed"] or (activity["moved"] and at - last_selected >= 3):
                selected.add(index)
                last_selected = at
        elif activity["state"] == "quiet" and at - last_selected >= 30:
            selected.add(index)
            last_selected = at
    return [row for index, row in enumerate(frames) if index in selected]
