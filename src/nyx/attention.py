"""Cheap local change detection. Selection is not a semantic observation."""

import numpy as np
from PIL import Image


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
        pixels = np.asarray(image.convert("L").resize((160, 96)), dtype=np.float32) / 255
        reason = None
        changed = False
        if self.previous is None:
            reason = "initial"
        elif at <= self.last_at or at - self.last_at > self.gap:
            reason = "gap"
            self.settle = False
        else:
            difference = np.abs(pixels - self.previous)
            # Local blocks prevent a small placed object being diluted by the whole room.
            blocks = difference.reshape(12, 8, 20, 8).mean(axis=(1, 3))
            changed = float(difference.mean()) > 0.035 or float(blocks.max()) > 0.12
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
