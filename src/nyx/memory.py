import json
import math
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import sqlite_vec


def _vector(values, dimensions):
    vector = np.asarray(values, dtype=np.float32)
    if vector.shape != (dimensions,) or not np.isfinite(vector).all():
        raise ValueError(f"Expected a finite {dimensions}-dimensional vector")
    norm = float(np.linalg.norm(vector))
    if norm == 0 or not math.isfinite(norm):
        raise ValueError("Expected a nonzero finite vector")
    return (vector / norm).tobytes()


class Store:
    def __init__(self, root: Path, fingerprint: dict, dimensions: int):
        if dimensions < 1:
            raise ValueError("Vector dimensions must be positive")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.fingerprint = fingerprint
        self.dimensions = dimensions
        identity = json.dumps({"encoder": fingerprint, "dimensions": dimensions}, sort_keys=True)
        with self.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            saved = db.execute("SELECT value FROM meta WHERE key = 'encoder'").fetchone()
            if saved and saved[0] != identity:
                raise ValueError(
                    "This index uses a different encoder; choose another data directory"
                )
            db.execute("INSERT OR IGNORE INTO meta VALUES ('encoder', ?)", (identity,))
            db.executescript("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    recorded_at TEXT,
                    imported_at TEXT NOT NULL,
                    interval_seconds REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'indexing',
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS frames (
                    id INTEGER PRIMARY KEY,
                    video_id TEXT NOT NULL REFERENCES videos(id),
                    offset_seconds REAL NOT NULL,
                    thumbnail TEXT NOT NULL,
                    embedding BLOB NOT NULL
                );
                CREATE INDEX IF NOT EXISTS frames_video ON frames(video_id);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.root / "index.sqlite3")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_video(self, name, path, recorded_at, interval, video_id=None):
        video_id = video_id or uuid.uuid4().hex
        with self.connection() as db:
            db.execute(
                """INSERT INTO videos
                (id, name, path, recorded_at, imported_at, interval_seconds)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (video_id, name, path, recorded_at, datetime.now(UTC).isoformat(), interval),
            )
        return video_id

    def video(self, video_id):
        with self.connection() as db:
            row = db.execute(
                """SELECT videos.*, COUNT(frames.id) AS frame_count,
                MAX(frames.offset_seconds) AS last_sample_seconds
                FROM videos LEFT JOIN frames ON frames.video_id = videos.id
                WHERE videos.id = ? GROUP BY videos.id""",
                (video_id,),
            ).fetchone()
        return dict(row) if row else None

    def restart_video(self, video_id):
        with self.connection() as db:
            db.execute("DELETE FROM frames WHERE video_id = ?", (video_id,))
            db.execute(
                "UPDATE videos SET status = 'indexing', error = NULL WHERE id = ?", (video_id,)
            )

    def add_frames(self, video_id, frames, vectors):
        if len(frames) != len(vectors):
            raise ValueError("Frame and vector counts differ")
        rows = []
        for (offset, thumbnail), vector in zip(frames, vectors, strict=True):
            if not math.isfinite(offset) or offset < 0:
                raise ValueError("Frame offset must be finite and nonnegative")
            rows.append((video_id, offset, thumbnail, _vector(vector, self.dimensions)))
        with self.connection() as db:
            db.executemany(
                "INSERT INTO frames (video_id, offset_seconds, thumbnail, embedding) VALUES (?,?,?,?)",
                rows,
            )

    def finish_video(self, video_id):
        with self.connection() as db:
            db.execute("UPDATE videos SET status = 'ready', error = NULL WHERE id = ?", (video_id,))

    def fail_video(self, video_id, error):
        with self.connection() as db:
            db.execute("DELETE FROM frames WHERE video_id = ?", (video_id,))
            db.execute(
                "UPDATE videos SET status = 'failed', error = ? WHERE id = ?", (error, video_id)
            )

    def list_videos(self):
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute("""
                SELECT videos.*, COUNT(frames.id) AS frame_count
                FROM videos LEFT JOIN frames ON frames.video_id = videos.id
                GROUP BY videos.id ORDER BY imported_at DESC
            """)
            ]

    def search(self, vector, limit=5, video_id=None, start=None, end=None):
        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100")
        for offset in [start, end]:
            if offset is not None and (not math.isfinite(offset) or offset < 0):
                raise ValueError("Time offsets must be finite and nonnegative")
        if start is not None and end is not None and start > end:
            raise ValueError("Start offset must not exceed end offset")
        filters = ["v.status = 'ready'"]
        params = [_vector(vector, self.dimensions)]
        for clause, value in [
            ("v.id = ?", video_id),
            ("f.offset_seconds >= ?", start),
            ("f.offset_seconds <= ?", end),
        ]:
            if value is not None:
                filters.append(clause)
                params.append(value)
        params.append(limit)
        with self.connection() as db:
            rows = db.execute(
                f"""SELECT f.id, f.video_id, f.offset_seconds, f.thumbnail,
                v.name, v.path AS video_path, v.recorded_at, v.imported_at,
                vec_distance_cosine(f.embedding, ?) AS distance
                FROM frames f JOIN videos v ON v.id = f.video_id
                WHERE {" AND ".join(filters)} ORDER BY distance, f.id LIMIT ?""",
                params,
            ).fetchall()
        return [{**dict(row), "similarity": 1 - row["distance"], "verified": False} for row in rows]
