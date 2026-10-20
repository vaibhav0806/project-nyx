"""Elapsed-time activity nomination. Pixel changes never establish semantic importance."""

import math
import uuid

from nyx.attention import frame_pixels, pixels_changed


class ActivityWindow:
    policy = "activity-v1/0.5s-persistence/0.8s-quiet/0.5s-gap"

    def __init__(self):
        self.reference = None
        self.previous = None
        self.last_at = None
        self._clear_episode()

    def _clear_episode(self):
        self.state = "quiet"
        self.event_id = None
        self.started_at = None
        self.qualified_at = None
        self.last_motion_at = None
        self.support = 0

    def observe(self, image, at):
        if not math.isfinite(at):
            raise ValueError("Frame time must be finite")
        if self.last_at is not None and at <= self.last_at:
            raise ValueError("Activity samples must arrive in time order")
        pixels = frame_pixels(image)
        gap = self.last_at is not None and at - self.last_at > 0.5 + 1e-6
        moved = False
        if self.previous is None or gap:
            self.reference = pixels
            self._clear_episode()
        else:
            moved = pixels_changed(pixels, self.previous)
            changed = pixels_changed(pixels, self.reference)
            if self.state == "quiet" and changed:
                self.state = "collecting"
                self.event_id = uuid.uuid4().hex
                self.started_at = at
                self.last_motion_at = at
                self.support = 1
            elif self.state == "collecting":
                if not changed:
                    # A flash returning to the baseline cannot accumulate persistence.
                    self._clear_episode()
                else:
                    self.support += 1
                    if moved:
                        self.last_motion_at = at
                    if self.support >= 3 and at - self.started_at >= 0.5 - 1e-6:
                        self.qualified_at = at
                        self.state = "active"
            elif self.state in {"active", "settling"} and moved:
                self.last_motion_at = at
            if self.qualified_at is not None:
                self.state = "active" if moved else "settling"
        self.previous = pixels
        self.last_at = at
        closed = self.qualified_at is not None and at - self.last_motion_at >= 0.8 - 1e-6
        result = {
            "state": "settled" if closed else self.state,
            "event_id": self.event_id,
            "started_at": self.started_at,
            "qualified_at": self.qualified_at,
            "qualified": self.qualified_at is not None,
            "moved": moved,
            "closed": closed,
            "discontinuity": gap,
            "policy": self.policy,
        }
        if closed:
            self.reference = pixels
            self._clear_episode()
        return result
