"""Durable next-departure requests and separate delivery/acknowledgement state."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from nyx.memory import aware_time


class Intentions:
    def __init__(self, root):
        self.path = Path(root) / "intentions.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS intentions (
                    id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                    message TEXT NOT NULL, created_at TEXT NOT NULL,
                    state TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS deliveries (
                    id TEXT PRIMARY KEY, intention_id TEXT NOT NULL,
                    event_id TEXT NOT NULL, observed_at TEXT NOT NULL,
                    evidence TEXT NOT NULL, state TEXT NOT NULL,
                    UNIQUE(intention_id, event_id));
            """)
            db.execute("UPDATE intentions SET state='interrupted' WHERE state='delivering'")
            db.execute("UPDATE deliveries SET state='interrupted' WHERE state='delivering'")
            db.execute("UPDATE intentions SET state='missed' WHERE state='pending'")
            db.execute("UPDATE deliveries SET state='missed' WHERE state='pending'")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, request_id, message):
        if not isinstance(message, str) or not 1 <= len(message.strip()) <= 240:
            raise ValueError("Use a reminder message of 1–240 characters")
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
            raise ValueError("A stable request ID is required")
        now = datetime.now(UTC).isoformat()
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO intentions VALUES (?,?,?,?,?,?)",
                (uuid.uuid4().hex, request_id, message.strip(), now, "armed", now),
            )
            row = db.execute(
                "SELECT * FROM intentions WHERE request_id=?", (request_id,)
            ).fetchone()
            if row["message"] != message.strip():
                raise ValueError("Request ID already belongs to a different reminder")
            return dict(row)

    def get(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT * FROM intentions WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise ValueError("Reminder not found")
        return dict(row)

    def active(self):
        self.expire()
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM intentions WHERE state IN ('armed','pending','delivering') ORDER BY created_at"
                )
            ]

    def recent(self):
        self.expire()
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM intentions ORDER BY created_at DESC LIMIT 30")
            ]

    def cancel(self, identifier):
        self.get(identifier)
        with self.connect() as db:
            db.execute(
                "UPDATE intentions SET state='cancelled',updated_at=? WHERE id=?",
                (datetime.now(UTC).isoformat(), identifier),
            )
            db.execute(
                "UPDATE deliveries SET state='cancelled' WHERE intention_id=? AND state IN ('pending','delivering')",
                (identifier,),
            )

    def trigger(self, event_id, observed_at, evidence):
        observed = aware_time(observed_at)
        age = (datetime.now(UTC) - observed).total_seconds()
        if age < -2:
            raise ValueError("Event clock is ahead")
        if age > 15:
            return []
        rows = []
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for task in db.execute("SELECT * FROM intentions WHERE state='armed'").fetchall():
                if observed < aware_time(task["created_at"]):
                    continue
                identifier = uuid.uuid4().hex
                db.execute(
                    "INSERT OR IGNORE INTO deliveries VALUES (?,?,?,?,?,?)",
                    (
                        identifier,
                        task["id"],
                        event_id,
                        observed.isoformat(),
                        json.dumps(evidence),
                        "pending",
                    ),
                )
                db.execute(
                    "UPDATE intentions SET state='pending',updated_at=? WHERE id=?",
                    (datetime.now(UTC).isoformat(), task["id"]),
                )
                rows.append(
                    {
                        "id": identifier,
                        "intention_id": task["id"],
                        "message": task["message"],
                        "state": "pending",
                    }
                )
        return rows

    def pending(self):
        self.expire()
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute("""SELECT d.*,i.message FROM deliveries d
                JOIN intentions i ON i.id=d.intention_id WHERE d.state='pending' AND i.state='pending'""")
            ]

    def expire(self):
        now = datetime.now(UTC)
        with self.connect() as db:
            for row in db.execute(
                "SELECT * FROM deliveries WHERE state IN ('pending','delivering')"
            ).fetchall():
                age = (now - aware_time(row["observed_at"])).total_seconds()
                if (row["state"] == "pending" and age > 15) or (
                    row["state"] == "delivering" and age > 45
                ):
                    outcome = "missed" if row["state"] == "pending" else "interrupted"
                    db.execute(
                        "UPDATE deliveries SET state=? WHERE id=? AND state=?",
                        (outcome, row["id"], row["state"]),
                    )
                    db.execute(
                        "UPDATE intentions SET state=?,updated_at=? WHERE id=? AND state=?",
                        (outcome, now.isoformat(), row["intention_id"], row["state"]),
                    )

    def deliver(self, identifier):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT d.*,i.message FROM deliveries d JOIN intentions i ON i.id=d.intention_id
                WHERE d.id=? AND d.state='pending' AND i.state='pending'""",
                (identifier,),
            ).fetchone()
            if row is None:
                return None
            if (datetime.now(UTC) - aware_time(row["observed_at"])).total_seconds() > 15:
                db.execute("UPDATE deliveries SET state='missed' WHERE id=?", (identifier,))
                db.execute(
                    "UPDATE intentions SET state='missed' WHERE id=?", (row["intention_id"],)
                )
                return None
            db.execute("UPDATE deliveries SET state='delivering' WHERE id=?", (identifier,))
            db.execute(
                "UPDATE intentions SET state='delivering' WHERE id=?", (row["intention_id"],)
            )
            return {**dict(row), "state": "delivering"}

    def finish(self, identifier, outcome):
        if outcome not in {"played", "failed", "interrupted"}:
            raise ValueError("Unknown playback outcome")
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM deliveries WHERE id=? AND state='delivering'", (identifier,)
            ).fetchone()
            if row:
                db.execute("UPDATE deliveries SET state=? WHERE id=?", (outcome, identifier))
                db.execute(
                    "UPDATE intentions SET state=?,updated_at=? WHERE id=? AND state='delivering'",
                    (
                        "delivered" if outcome == "played" else outcome,
                        datetime.now(UTC).isoformat(),
                        row["intention_id"],
                    ),
                )

    def acknowledge(self, identifier):
        with self.connect() as db:
            db.execute(
                "UPDATE intentions SET state='acknowledged',updated_at=? WHERE id=? AND state='delivered'",
                (datetime.now(UTC).isoformat(), identifier),
            )
