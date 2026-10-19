import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path


def capture_time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Capture time requires a timezone")
    return parsed.astimezone(UTC)


class CaptureJournal:
    def __init__(self, root, budget_bytes=1024**3, max_pending=8):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "incoming").mkdir(exist_ok=True)
        self.budget_bytes = budget_bytes
        self.max_pending = max_pending
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, state TEXT NOT NULL,
                    started_at TEXT NOT NULL, updated_at TEXT NOT NULL, reason TEXT
                );
                CREATE TABLE IF NOT EXISTS segments (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                    sequence INTEGER NOT NULL, recorded_at TEXT NOT NULL, ended_at TEXT NOT NULL,
                    state TEXT NOT NULL, path TEXT NOT NULL, size INTEGER NOT NULL DEFAULT 0,
                    last_sample_seconds REAL, error TEXT,
                    timing_uncertain INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(session_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
                    at TEXT NOT NULL, reason TEXT NOT NULL
                );
            """)
            if "timing_uncertain" not in {
                row[1] for row in db.execute("PRAGMA table_info(segments)")
            }:
                db.execute(
                    "ALTER TABLE segments ADD COLUMN timing_uncertain INTEGER NOT NULL DEFAULT 0"
                )

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.root / "capture.sqlite3")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def video_bytes(self):
        return sum(
            path.stat().st_size
            for folder in ["recordings", "incoming"]
            for path in (self.root / folder).rglob("*")
            if path.is_file()
        )

    def start(self, at):
        at = capture_time(at).isoformat()
        if self.video_bytes() >= self.budget_bytes:
            raise ValueError("Saved-video budget reached; existing clips are kept")
        session_id = uuid.uuid4().hex
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT id FROM sessions WHERE state IN ('recording', 'paused')"
            ).fetchone():
                raise ValueError(
                    "A recording session is already active; stop it before starting another"
                )
            db.execute(
                "INSERT INTO sessions VALUES (?, 'recording', ?, ?, NULL)",
                (session_id, at, datetime.now(UTC).isoformat()),
            )
        return self.get_session(session_id)

    def get_session(self, session_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise ValueError("Recording session not found")
        return dict(row)

    def transition(self, session_id, state, at, reason):
        at = capture_time(at).isoformat()
        if state not in {"recording", "paused", "stopped", "interrupted"}:
            raise ValueError("Invalid recording state")
        with self.connection() as db:
            current = db.execute(
                "SELECT state FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if current is None:
                raise ValueError("Recording session not found")
            if state == "recording" and current[0] != "paused":
                raise ValueError("Only a paused session can resume")
            if state == "paused" and current[0] != "recording":
                raise ValueError("Only a recording session can pause")
            db.execute(
                "UPDATE sessions SET state = ?, reason = ?, updated_at = ? WHERE id = ?",
                (state, reason, datetime.now(UTC).isoformat(), session_id),
            )
            db.execute(
                "INSERT INTO events (session_id, at, reason) VALUES (?, ?, ?)",
                (session_id, at, reason),
            )
        return self.get_session(session_id)

    def heartbeat(self, session_id):
        with self.connection() as db:
            db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (datetime.now(UTC).isoformat(), session_id),
            )
        return self.get_session(session_id)

    def begin_segment(
        self, session_id, sequence, recorded_at, ended_at, suffix, timing_uncertain=False
    ):
        start, end = capture_time(recorded_at), capture_time(ended_at)
        if end <= start or (end - start).total_seconds() > 180:
            raise ValueError(
                "Segment times must describe a positive interval of at most three minutes"
            )
        if sequence < 0 or suffix not in {".webm", ".mp4"}:
            raise ValueError("Invalid segment sequence or video format")
        self.get_session(session_id)
        segment_id = uuid.uuid5(uuid.UUID(hex=session_id), str(sequence)).hex
        path = str(Path("recordings") / f"{segment_id}{suffix}")
        identity = (start.isoformat(), end.isoformat(), path, int(timing_uncertain))
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
            if existing:
                if (
                    tuple(
                        existing[key]
                        for key in ["recorded_at", "ended_at", "path", "timing_uncertain"]
                    )
                    != identity
                ):
                    raise ValueError("Segment retry metadata differs from the saved source")
                if existing["state"] != "failed" or (self.root / path).exists():
                    return dict(existing)
            count = db.execute(
                "SELECT COUNT(*) FROM segments WHERE state IN ('uploading','staged','queued','indexing')"
            ).fetchone()[0]
            if count >= self.max_pending:
                raise ValueError("Indexing backlog is full; stop recording until it catches up")
            if existing:
                db.execute(
                    "UPDATE segments SET state = 'uploading', error = NULL WHERE id = ?",
                    (segment_id,),
                )
            else:
                db.execute(
                    "INSERT INTO segments (id, session_id, sequence, recorded_at, ended_at, state, path, timing_uncertain) VALUES (?,?,?,?,?,'uploading',?,?)",
                    (segment_id, session_id, sequence, *identity),
                )
        return self.segment(segment_id)

    def segment(self, segment_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
        if row is None:
            raise ValueError("Recording segment not found")
        return dict(row)

    def partial_path(self, segment_id):
        return self.root / "incoming" / f"capture-{segment_id}.part"

    def finish_upload(self, segment_id, size):
        partial = self.partial_path(segment_id)
        if size <= 0 or partial.stat().st_size != size:
            raise ValueError("Recording upload is empty or incomplete")
        if self.video_bytes() > self.budget_bytes:
            raise ValueError("Saved-video budget reached; existing clips are kept")
        with partial.open("rb") as file:
            os.fsync(file.fileno())
        with self.connection() as db:
            db.execute(
                "UPDATE segments SET state = 'staged', size = ? WHERE id = ?", (size, segment_id)
            )
        self._promote(self.segment(segment_id))
        return self.segment(segment_id)

    def _promote(self, segment):
        destination = self.root / segment["path"]
        destination.parent.mkdir(exist_ok=True)
        if not destination.exists():
            self.partial_path(segment["id"]).replace(destination)
        self.mark(segment["id"], "queued")

    def mark(self, segment_id, state, error=None, last_sample_seconds=None):
        with self.connection() as db:
            db.execute(
                "UPDATE segments SET state = ?, error = ?, last_sample_seconds = ? WHERE id = ?",
                (state, error, last_sample_seconds, segment_id),
            )

    def pending(self):
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM segments WHERE state = 'queued' ORDER BY recorded_at, sequence"
                )
            ]

    def recover(self):
        now = datetime.now(UTC).isoformat()
        with self.connection() as db:
            active = db.execute(
                "SELECT id FROM sessions WHERE state IN ('recording', 'paused')"
            ).fetchall()
        for row in active:
            self.transition(
                row["id"],
                "interrupted",
                now,
                "Server restart; coverage after the last saved segment is unknown",
            )
        with self.connection() as db:
            segments = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM segments WHERE state IN ('uploading','staged','indexing')"
                )
            ]
        for segment in segments:
            if segment["state"] == "uploading":
                self.partial_path(segment["id"]).unlink(missing_ok=True)
                self.mark(segment["id"], "failed", "Upload interrupted; source tail unavailable")
            elif segment["state"] == "staged":
                partial = self.partial_path(segment["id"])
                source = self.root / segment["path"]
                if any(
                    path.is_file() and path.stat().st_size == segment["size"]
                    for path in [source, partial]
                ):
                    self._promote(segment)
                else:
                    self.mark(segment["id"], "failed", "Saved segment is missing or incomplete")
            else:
                self.mark(segment["id"], "queued")

    def snapshot(self):
        with self.connection() as db:
            sessions = [
                dict(row)
                for row in db.execute("SELECT * FROM sessions ORDER BY rowid DESC LIMIT 10")
            ]
            segments = [
                dict(row)
                for row in db.execute("SELECT * FROM segments ORDER BY recorded_at DESC LIMIT 100")
            ]
            events = [
                dict(row) for row in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 20")
            ]
            counts = {
                row[0]: row[1]
                for row in db.execute("SELECT state, COUNT(*) FROM segments GROUP BY state")
            }
            coverage = [dict(row) for row in db.execute("SELECT * FROM segments WHERE size > 0")]
        saved = [row for row in coverage if (self.root / row["path"]).exists()]
        known = [row for row in saved if not row["timing_uncertain"]]
        ready = [
            row
            for row in known
            if row["state"] == "ready" and row["last_sample_seconds"] is not None
        ]
        return {
            "session": sessions[0] if sessions else None,
            "segments": segments,
            "events": events,
            "counts": counts,
            "video_bytes": self.video_bytes(),
            "video_budget_bytes": self.budget_bytes,
            "segment_seconds": 10,
            "sample_seconds": 2,
            "timing_uncertain_count": sum(bool(row["timing_uncertain"]) for row in saved),
            "recorded_through": max((row["ended_at"] for row in known), default=None),
            "searchable_through": max(
                (
                    (
                        capture_time(row["recorded_at"])
                        + timedelta(seconds=row["last_sample_seconds"])
                    ).isoformat()
                    for row in ready
                ),
                default=None,
            ),
        }
