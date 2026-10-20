"""Bounded ephemeral live sequences, distinct from the recorded-history index."""

import json
from collections import deque
from datetime import UTC, datetime
from threading import Lock

from nyx.activity import ActivityWindow
from nyx.attention import frame_pixels, pixels_changed
from nyx.memory import aware_time


def departure_judgment(raw):
    uncertain = {"departure": False, "uncertain": True, "cue": "No reliable departure evidence"}
    try:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        row = json.loads(raw)
        if any(
            type(row.get(key)) is not bool
            for key in ["departure", "uncertain", "approached_exit", "exit_interaction"]
        ):
            return uncertain
        if not isinstance(row.get("cue"), str) or not 1 <= len(row["cue"]) <= 400:
            return uncertain
        return {
            **row,
            "departure": row["departure"]
            and not row["uncertain"]
            and row["approached_exit"]
            and row["exit_interaction"],
        }
    except (ValueError, AttributeError, TypeError, IndexError):
        return uncertain


def departure_action(burst, judgment, requests):
    """Application eligibility, separate from fallible visual interpretation."""
    decision = {"act": False, "request_ids": []}
    if burst.get("activity", {}).get("qualified") is not True:
        return {**decision, "reason": "wait_activity"}
    if judgment.get("uncertain") is not False:
        return {**decision, "reason": "uncertain"}
    if judgment.get("departure") is not True:
        return {**decision, "reason": "no_departure"}
    if any(judgment.get(key) is not True for key in ["approached_exit", "exit_interaction"]):
        return {**decision, "reason": "missing_exit_cues"}
    first = aware_time(burst["times"][0])
    eligible = [
        row["id"]
        for row in requests
        if row["state"] == "armed" and aware_time(row["created_at"]) <= first
    ]
    if not eligible:
        return {**decision, "reason": "no_matching_request"}
    return {"act": True, "request_ids": eligible, "reason": "requested_departure"}


class Observer:
    def __init__(self):
        self.lock = Lock()
        self.epoch = 0
        self.session = None
        self.frames = deque(maxlen=64)
        self.window = ActivityWindow()
        self.phase = "quiet"
        self.pending = None
        self.last_check = None
        self.last_event = None
        self.last_pixels = None

    def reset(self):
        with self.lock:
            self.epoch += 1
            self.session = None
            self.frames.clear()
            self.window = ActivityWindow()
            self.phase = "quiet"
            self.pending = None
            self.last_check = None
            self.last_event = None
            self.last_pixels = None

    def valid(self, burst):
        with self.lock:
            return burst["epoch"] == self.epoch and burst["session"] == self.session

    def accept(self, burst):
        """Consume a nomination only after a model job has actually been admitted."""
        with self.lock:
            if burst["epoch"] != self.epoch or burst["session"] != self.session:
                return False
            self.last_check = aware_time(burst["times"][-1])
            self.last_event = burst["event_id"]
            self.last_pixels = frame_pixels(burst["images"][-1])
            if self.pending and self.pending["times"][-1] <= burst["times"][-1]:
                self.pending = None
            return True

    def feed(self, session, image, captured_at):
        at = aware_time(captured_at)
        age = (datetime.now(UTC) - at).total_seconds()
        if age < -2 or age > 5:
            raise ValueError("Observation must be fresh and use this laptop's clock")
        with self.lock:
            if self.session != session:
                self.epoch += 1
                self.session = session
                self.frames.clear()
                self.window = ActivityWindow()
                self.pending = None
                self.last_check = None
                self.last_event = None
                self.last_pixels = None
            if self.frames and at <= self.frames[-1][0]:
                raise ValueError("Observation frames must arrive in time order")
            if self.frames and (at - self.frames[-1][0]).total_seconds() > 0.5:
                self.frames.clear()
                self.window = ActivityWindow()
                self.pending = None
                self.last_check = None
                self.last_event = None
                self.last_pixels = None
                self.epoch += 1
            activity = self.window.observe(image, at.timestamp())
            self.phase = activity["state"]
            small = image.copy()
            small.thumbnail((640, 360))
            self.frames.append((at, small))
            while self.frames and (at - self.frames[0][0]).total_seconds() > 6:
                self.frames.popleft()
            ready = activity["qualified"] and (
                activity["event_id"] != self.last_event
                or (
                    (at - self.last_check).total_seconds() >= 3
                    and pixels_changed(frame_pixels(small), self.last_pixels)
                )
            )
            if ready and len(self.frames) >= 3:
                samples = list(self.frames)
                start = next(
                    (
                        i
                        for i, row in enumerate(samples)
                        if row[0].timestamp() >= activity["started_at"]
                    ),
                    0,
                )
                samples = samples[max(0, start - 1) :]
                samples = [samples[0], samples[len(samples) // 2], samples[-1]]
                self.pending = {
                    "epoch": self.epoch,
                    "session": session,
                    "event_id": activity["event_id"],
                    "images": [row[1] for row in samples],
                    "times": [row[0].isoformat() for row in samples],
                    "activity": {
                        **activity,
                        "started_at": datetime.fromtimestamp(
                            activity["started_at"], UTC
                        ).isoformat(),
                        "qualified_at": datetime.fromtimestamp(
                            activity["qualified_at"], UTC
                        ).isoformat(),
                    },
                }
            if self.pending and (at - aware_time(self.pending["times"][-1])).total_seconds() > 8:
                self.pending = None
            return self.pending
