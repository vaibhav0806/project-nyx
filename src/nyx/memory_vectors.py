"""SQLite-native personal-memory KNN; original records remain authoritative."""

import hashlib
import json
from contextlib import contextmanager

import numpy as np
import sqlite_vec


class MemoryVectors:
    def __init__(self, conversations, encoder):
        self.conversations = conversations
        self.encoder = encoder
        identity = json.dumps(encoder.fingerprint, sort_keys=True)
        suffix = hashlib.sha256(identity.encode()).hexdigest()[:16]
        self.table = f"memory_vectors_{suffix}"
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {self.table} USING vec0("
                f"memory_id TEXT PRIMARY KEY, embedding float[{encoder.dimensions}] "
                "distance_metric=cosine, +encoder TEXT)"
            )
            # Additive backfill, once per record/encoder. Never rewrite source vectors/photos.
            rows = db.execute(
                f"SELECT m.id,m.embedding,m.encoder FROM memories m LEFT JOIN {self.table} v "
                "ON v.memory_id=m.id WHERE v.memory_id IS NULL"
            )
            for row in rows.fetchall():
                try:
                    vector = np.frombuffer(row["embedding"], dtype=np.float32)
                    if (
                        json.loads(row["encoder"]) != encoder.fingerprint
                        or vector.shape != (encoder.dimensions,)
                        or not np.isfinite(vector).all()
                        or not np.linalg.norm(vector)
                    ):
                        continue
                except (ValueError, TypeError):
                    continue
                self.add(db, row["id"], row["embedding"], row["encoder"])

    @staticmethod
    def load(db):
        db.enable_load_extension(True)
        try:
            sqlite_vec.load(db)
        finally:
            db.enable_load_extension(False)

    @contextmanager
    def connection(self):
        db = self.conversations.connect()
        try:
            self.load(db)
            with db:
                yield db
        finally:
            db.close()

    def add(self, db, identifier, embedding, encoder):
        self.load(db)
        db.execute(
            f"INSERT INTO {self.table}(memory_id,embedding,encoder) VALUES (?,?,?)",
            (identifier, embedding, encoder),
        )

    def candidates(self, vector, *, limit, cutoff, historical=False, excluded=()):
        """Filter eligibility before KNN; invalid source chains can be excluded and refilled."""
        eligible = (
            "SELECT m.id FROM memories m JOIN turns t ON t.id=m.turn_id "
            "WHERE t.input_available=1 "
            # Seconds are a conservative prefilter. Exact microseconds are checked on
            # selected records; SQLite's Julian-day conversion rounds submilliseconds.
            "AND (t.at IS NULL OR CAST(strftime('%s',t.at) AS INTEGER)"
            "<=CAST(strftime('%s',?) AS INTEGER)) "
            "AND (?=0 OR t.at IS NOT NULL) "
            "AND m.id NOT IN (SELECT value FROM json_each(?)) "
            "AND NOT EXISTS (SELECT 1 FROM memory_relations r "
            "LEFT JOIN memories replacement ON replacement.id=r.replacement_id "
            "LEFT JOIN turns rt ON rt.id=replacement.turn_id "
            "WHERE r.previous_id=m.id AND r.relation IN ('correct','retract') "
            "AND (rt.at IS NULL OR CAST(strftime('%s',rt.at) AS INTEGER)"
            "<CAST(strftime('%s',?) AS INTEGER)))"
        )
        params = [cutoff, int(historical), json.dumps(list(excluded)), cutoff]
        with self.connection() as db:
            if vector is None:
                rows = db.execute(
                    eligible + f" AND m.id IN (SELECT memory_id FROM {self.table})"
                    " ORDER BY t.at DESC,m.id LIMIT ?",
                    [*params, limit],
                )
            else:
                rows = db.execute(
                    f"WITH nearest AS (SELECT memory_id,distance FROM {self.table} "
                    f"WHERE embedding MATCH ? AND k=? AND memory_id IN ({eligible})) "
                    "SELECT n.memory_id AS id,n.distance FROM nearest n JOIN memories m ON m.id=n.memory_id "
                    "JOIN turns t ON t.id=m.turn_id ORDER BY n.distance,t.at DESC,m.id",
                    [vector.tobytes(), limit + 1, *params],
                ).fetchall()
                if len(rows) > limit and rows[limit - 1]["distance"] == rows[limit]["distance"]:
                    # vec0 does not promise which equidistant rows cross the K boundary.
                    # Resolve that boundary with native SQL distance + recency, preserving
                    # latest-first semantics without transferring vectors into Python.
                    rows = db.execute(
                        f"SELECT m.id,vec_distance_cosine(v.embedding,?) AS distance "
                        f"FROM memories m JOIN {self.table} v ON v.memory_id=m.id "
                        f"JOIN turns t ON t.id=m.turn_id WHERE m.id IN ({eligible}) "
                        "ORDER BY distance,t.at DESC,m.id LIMIT ?",
                        [vector.tobytes(), *params, limit],
                    )
            return [row["id"] for row in rows][:limit]

    def unchanged(self, identifiers):
        """Compare source vectors only for nominated records, never the entire archive."""
        with self.connection() as db:
            return {
                row[0]
                for row in db.execute(
                    f"SELECT m.id FROM memories m JOIN {self.table} v ON v.memory_id=m.id "
                    "WHERE m.id IN (SELECT value FROM json_each(?)) "
                    "AND m.embedding=v.embedding AND m.encoder=v.encoder",
                    (json.dumps(identifiers),),
                )
            }
