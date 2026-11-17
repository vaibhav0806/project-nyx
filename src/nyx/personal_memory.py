"""Source-linked personal memory; interpretation is separate from reliable persistence."""

import hashlib
import json

import numpy as np

from nyx.memory import aware_time

MEMORY_INSTRUCTIONS = """Organize useful information from user input into source-linked memories and select relevant stored memories.
Record facts, preferences, events and plans. A move adds an event; an explicit correction or retraction versions an earlier report. Preserve uncertainty and distinguish plans from reports.
Use exact user quotes as sources. Questions and assistant guesses are not new user facts. Request visual evidence when needed to resolve a reference. Ask for clarification if important meaning or identity remains unclear."""

SCHEMA = {
    "type": "object",
    "properties": {
        "operations": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["append", "correct", "retract"]},
                    "content": {
                        "type": "string",
                        "description": "Concise memory grounded in the quoted input",
                    },
                    "kind": {"type": "string", "enum": ["report", "plan"]},
                    "related_id": {
                        "type": ["string", "null"],
                        "description": "Actual related memory ID; required for correction/retraction",
                    },
                    "quotes": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "turn_id": {"type": "string"},
                                "text": {"type": "string"},
                            },
                            "required": ["turn_id", "text"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["operation", "content", "kind", "related_id", "quotes"],
                "additionalProperties": False,
            },
        },
        "relevant_ids": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
        "needs_visual": {"type": "boolean"},
        "clarification": {"type": "string"},
    },
    "required": ["operations", "relevant_ids", "needs_visual", "clarification"],
    "additionalProperties": False,
}


class PersonalMemory:
    def __init__(self, conversations, encoder, interpret):
        self.conversations, self.encoder, self.interpret = conversations, encoder, interpret
        with conversations.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY, turn_id TEXT NOT NULL, content TEXT NOT NULL,
                    kind TEXT NOT NULL, quotes TEXT NOT NULL, embedding BLOB NOT NULL,
                    encoder TEXT NOT NULL, visual TEXT NOT NULL, image BLOB);
                CREATE TABLE IF NOT EXISTS memory_relations (
                    previous_id TEXT NOT NULL, replacement_id TEXT PRIMARY KEY,
                    relation TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memory_turns (
                    turn_id TEXT PRIMARY KEY, result TEXT NOT NULL);
            """)
            if "image" not in {row[1] for row in db.execute("PRAGMA table_info(memories)")}:
                db.execute("ALTER TABLE memories ADD COLUMN image BLOB")
        self._import_statements()

    def _import_statements(self):
        """Copy attributed old rows losslessly; no inference, source edits or vector rebuild."""
        with self.conversations.connect() as db:
            tables = {
                row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if "statements" not in tables:
                return
            columns = {row[1] for row in db.execute("PRAGMA table_info(statements)")}
            resolver = "s.resolver" if "resolver" in columns else "'{}'"
            rows = db.execute(
                "SELECT s.*,t.transcript,t.sources,"
                + resolver
                + " AS saved_resolver FROM statements s JOIN turns t ON t.id=s.turn_id"
            ).fetchall()
            for row in rows:
                try:
                    metadata = json.loads(row["saved_resolver"] or "{}")
                except (ValueError, TypeError):
                    metadata = {}
                visual = {
                    "object_description": row["object_description"],
                    "captured_at": row["captured_at"],
                    "identity_inferred": True,
                    "needs_review": metadata.get("reference_version") not in {2, 3},
                }
                quotes = [{"turn_id": row["turn_id"], "text": row["transcript"]}]
                kind = (
                    "plan"
                    if row["kind"] == "intention"
                    else "retraction"
                    if row["kind"] == "retraction"
                    else "report"
                )
                db.execute(
                    "INSERT OR IGNORE INTO memories(id,turn_id,content,kind,quotes,embedding,encoder,visual,image) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        row["turn_id"],
                        row["turn_id"],
                        row["transcript"],
                        kind,
                        json.dumps(quotes),
                        row["embedding"],
                        row["encoder"],
                        json.dumps(visual),
                        row["image"],
                    ),
                )
            if "statement_corrections" in tables:
                for row in db.execute("SELECT * FROM statement_corrections").fetchall():
                    db.execute(
                        "INSERT OR IGNORE INTO memory_relations VALUES (?,?,?)",
                        (row["previous_turn_id"], row["replacement_turn_id"], "correct"),
                    )

    @staticmethod
    def _photo(image):
        if image is None:
            return None
        from io import BytesIO

        snapshot = image.convert("RGB")
        snapshot.thumbnail((768, 768))
        buffer = BytesIO()
        snapshot.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()

    def _quote_sources(self, db, quotes):
        if not isinstance(quotes, list) or not 1 <= len(quotes) <= 4:
            raise ValueError("Memory needs user sources")
        sources = set()
        for quote in quotes:
            if not isinstance(quote, dict) or not isinstance(quote.get("turn_id"), str):
                raise TypeError("Invalid memory source")
            text = quote.get("text")
            row = db.execute(
                "SELECT transcript,sources,sources_available FROM turns WHERE id=?",
                (quote["turn_id"],),
            ).fetchone()
            if (
                not row
                or not row["sources_available"]
                or not isinstance(text, str)
                or not text.strip()
                or text not in row["transcript"]
            ):
                raise ValueError("Memory source is unavailable or quote is not verbatim")
            dependencies = json.loads(row["sources"] or "[]")
            if not isinstance(dependencies, list) or any(
                not isinstance(x, str) for x in dependencies
            ):
                raise ValueError("Invalid source dependencies")
            sources.update(dependencies)
            sources.add("transcript:" + quote["turn_id"])
        return sorted(sources)

    def _rows(self, *, as_of=None):
        cutoff = aware_time(as_of) if as_of else None
        with self.conversations.connect() as db:
            rows = db.execute(
                "SELECT m.*,t.at,t.sources_available FROM memories m JOIN turns t ON t.id=m.turn_id"
            ).fetchall()
            relations = {
                row["replacement_id"]: dict(row)
                for row in db.execute("SELECT * FROM memory_relations")
            }
            available = []
            unavailable = 0
            for row in rows:
                if cutoff and row["at"] and aware_time(row["at"]) > cutoff:
                    continue
                if not row["sources_available"] or (cutoff and not row["at"]):
                    unavailable += 1
                    continue
                try:
                    quotes = json.loads(row["quotes"])
                    sources = self._quote_sources(db, quotes)
                except (ValueError, TypeError, KeyError):
                    unavailable += 1
                    continue
                available.append({**dict(row), "quotes": quotes, "sources": sources})
        dates = {row["id"]: row["at"] for row in rows}
        replaced = {
            relation["previous_id"]
            for identifier, relation in relations.items()
            if relation["relation"] in {"correct", "retract"}
            and (not cutoff or not dates.get(identifier) or aware_time(dates[identifier]) <= cutoff)
        }
        return [row for row in available if row["id"] not in replaced], unavailable

    @staticmethod
    def _public(row):
        return {
            **{
                key: row[key]
                for key in ["id", "turn_id", "content", "kind", "at", "quotes", "sources"]
            },
            "visual": json.loads(row["visual"]),
            "has_image": row["image"] is not None,
        }

    def recall(self, query, *, limit=5, as_of=None):
        if not isinstance(query, str) or not query.strip() or not 1 <= limit <= 8:
            raise ValueError("Invalid memory query")
        rows, unavailable = self._rows(as_of=as_of)
        ranked = []
        if rows:
            vector = np.asarray(self.encoder.encode_text(query), dtype=np.float32)
            if (
                vector.shape != (self.encoder.dimensions,)
                or not np.isfinite(vector).all()
                or not np.linalg.norm(vector)
            ):
                raise ValueError("Invalid query embedding")
            vector = vector / np.linalg.norm(vector)
            for row in rows:
                saved = np.frombuffer(row["embedding"], dtype=np.float32)
                if (
                    json.loads(row["encoder"]) != self.encoder.fingerprint
                    or saved.shape != vector.shape
                    or not np.isfinite(saved).all()
                    or not np.linalg.norm(saved)
                ):
                    continue
                score = float((saved / np.linalg.norm(saved)) @ vector)
                ranked.append((score, row["at"] or "", row))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        matches = [self._public(row) for _, _, row in ranked[:limit]]
        return {
            "kind": "memories",
            "coverage": {"global_unavailable_count": unavailable},
            "status": "candidates" if matches else "uncertain",
            "matches": matches,
            "sources": sorted({s for row in matches for s in row["sources"]}),
            "answer": f"Retrieved {len(matches)} attributed memory candidates."
            if matches
            else "No matching memory was retrieved.",
        }

    def process(self, turn_id, *, observe=None, active=lambda: True):
        def check_active():
            if not active():
                raise ValueError("Request cancelled")

        check_active()
        with self.conversations.connect() as db:
            turn = db.execute("SELECT * FROM turns WHERE id=?", (turn_id,)).fetchone()
            if not turn or not turn["sources_available"]:
                raise ValueError("User input is unavailable")
            cached = db.execute(
                "SELECT result FROM memory_turns WHERE turn_id=?", (turn_id,)
            ).fetchone()
        if cached:
            return json.loads(cached["result"])
        candidates = self.recall(turn["transcript"], limit=8)["matches"]
        recent = [
            {"turn_id": row["id"], "text": row["transcript"]}
            for row in self.conversations.recent()
            if row["sources_available"] and row["id"] != turn_id
        ][-6:]
        payload = {
            "current_turn": {"turn_id": turn_id, "text": turn["transcript"]},
            "recent_user_turns": recent,
            "memories": candidates,
            "visual_available": observe is not None,
            "visual": None,
        }
        visual = {}
        check_active()
        reply = self.interpret(payload, SCHEMA)
        check_active()
        if not isinstance(reply, dict):
            raise TypeError("Invalid memory interpretation")
        if reply.get("needs_visual") is True and observe is not None:
            visual = observe()
            check_active()
            if visual.get("status") not in {"resolved", "seen"}:
                reply = {
                    "operations": [],
                    "relevant_ids": [],
                    "needs_visual": False,
                    "clarification": visual.get("answer") or "Which item do you mean?",
                }
            else:
                payload = {
                    **payload,
                    "visual_available": False,
                    "visual": {k: v for k, v in visual.items() if k != "image"},
                }
                reply = self.interpret(payload, SCHEMA)
                check_active()
        if (
            not isinstance(reply, dict)
            or type(reply.get("needs_visual")) is not bool
            or not isinstance(reply.get("operations"), list)
            or len(reply["operations"]) > 4
            or not isinstance(reply.get("clarification"), str)
            or len(reply["clarification"]) > 400
        ):
            raise ValueError("Invalid memory interpretation")
        if reply["needs_visual"] and not reply["clarification"]:
            reply = {**reply, "clarification": "Which item do you mean?"}
        if reply["clarification"] and reply["operations"]:
            raise ValueError("Unresolved memory cannot be partly saved")
        by_id = {row["id"]: row for row in candidates}
        selected = reply.get("relevant_ids")
        if (
            not isinstance(selected, list)
            or len(selected) > 5
            or any(not isinstance(x, str) or x not in by_id for x in selected)
        ):
            raise ValueError("Memory selected an unavailable record")
        allowed = {turn_id, *[row["turn_id"] for row in recent]}
        prepared = []
        with self.conversations.connect() as db:
            for index, op in enumerate(reply["operations"]):
                if (
                    not isinstance(op, dict)
                    or op.get("operation") not in {"append", "correct", "retract"}
                    or op.get("kind") not in {"report", "plan"}
                    or not isinstance(op.get("content"), str)
                    or not 1 <= len(op["content"].strip()) <= 1000
                ):
                    raise ValueError("Invalid memory operation")
                quotes = op.get("quotes")
                sources = self._quote_sources(db, quotes)
                if any(q["turn_id"] not in allowed for q in quotes):
                    raise ValueError("Memory source was not supplied for this turn")
                target = op.get("related_id")
                if target is not None and (not isinstance(target, str) or target not in by_id):
                    raise ValueError("Related memory is unavailable")
                if op["operation"] in {"correct", "retract"} and target is None:
                    raise ValueError("Correction needs an existing memory")
                identifier = hashlib.sha256(f"{turn_id}:{index}".encode()).hexdigest()[:32]
                prepared.append({**op, "id": identifier, "sources": sources})
        for op in prepared:
            check_active()
            vector = np.asarray(self.encoder.encode_text(op["content"]), dtype=np.float32)
            if (
                vector.shape != (self.encoder.dimensions,)
                or not np.isfinite(vector).all()
                or not np.linalg.norm(vector)
            ):
                raise ValueError("Invalid memory embedding")
            op["embedding"] = (vector / np.linalg.norm(vector)).tobytes()
        result = {
            "kind": "memory",
            "status": "clarify" if reply["clarification"] else "saved" if prepared else "noop",
            "answer": reply["clarification"]
            or ("Memory saved." if prepared else "No new memory recorded."),
            "saved_ids": [op["id"] for op in prepared],
            "relevant": [by_id[x] for x in selected],
            "sources": sorted(
                {s for op in prepared for s in op["sources"]}
                | {s for x in selected for s in by_id[x]["sources"]}
            ),
        }
        with self.conversations.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT result FROM memory_turns WHERE turn_id=?", (turn_id,)
            ).fetchone()
            if prior:
                return json.loads(prior["result"])
            check_active()
            for op in prepared:
                self._quote_sources(db, op["quotes"])
                if op["related_id"]:
                    target = db.execute(
                        "SELECT m.id,t.at,t.sources_available FROM memories m JOIN turns t ON t.id=m.turn_id WHERE m.id=?",
                        (op["related_id"],),
                    ).fetchone()
                    if (
                        not target
                        or not target["sources_available"]
                        or (
                            target["at"]
                            and turn["at"]
                            and aware_time(target["at"]) > aware_time(turn["at"])
                        )
                    ):
                        raise ValueError("Related memory changed")
                db.execute(
                    "INSERT INTO memories(id,turn_id,content,kind,quotes,embedding,encoder,visual,image) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        op["id"],
                        turn_id,
                        op["content"].strip(),
                        "retraction" if op["operation"] == "retract" else op["kind"],
                        json.dumps(op["quotes"]),
                        op["embedding"],
                        json.dumps(self.encoder.fingerprint),
                        json.dumps({k: v for k, v in visual.items() if k != "image"}),
                        self._photo(visual.get("image")),
                    ),
                )
                if op["related_id"]:
                    db.execute(
                        "INSERT INTO memory_relations VALUES (?,?,?)",
                        (op["related_id"], op["id"], op["operation"]),
                    )
            db.execute("INSERT INTO memory_turns VALUES (?,?)", (turn_id, json.dumps(result)))
        return result
