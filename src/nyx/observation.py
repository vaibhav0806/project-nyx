"""Bounded ephemeral live sequences, distinct from the recorded-history index."""

import json
from collections import deque
from datetime import UTC, datetime
from threading import Lock

from nyx.attention import ChangeDetector, sequence_changed
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


class Observer:
    def __init__(self):
        self.lock = Lock()
        self.epoch = 0
        self.session = None
        self.frames = deque(maxlen=6)
        self.detector = ChangeDetector()
        self.last_check = None

    def reset(self):
        with self.lock:
            self.epoch += 1
            self.session = None
            self.frames.clear()
            self.detector = ChangeDetector()
            self.last_check = None

    def valid(self, burst):
        with self.lock:
            return burst["epoch"] == self.epoch and burst["session"] == self.session

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
                self.detector = ChangeDetector()
                self.last_check = None
            if self.frames and at <= self.frames[-1][0]:
                raise ValueError("Observation frames must arrive in time order")
            if self.frames and (at - self.frames[-1][0]).total_seconds() > 3:
                self.frames.clear()
                self.detector = ChangeDetector()
                self.epoch += 1
            decision = self.detector.observe(image, at.timestamp())
            small = image.copy()
            small.thumbnail((640, 360))
            self.frames.append((at, small))
            if len(self.frames) < 3 or (not decision["selected"] and self.last_check is not None):
                return None
            if self.last_check and (at - self.last_check).total_seconds() < 3:
                return None
            samples = list(self.frames)
            if len(samples) > 3:
                samples = [samples[0], samples[len(samples) // 2], samples[-1]]
            if not sequence_changed([row[1] for row in samples]):
                return None
            self.last_check = at
            return {
                "epoch": self.epoch,
                "session": session,
                "images": [row[1] for row in samples],
                "times": [row[0].isoformat() for row in samples],
            }
