import json

import numpy as np
from test_personal_memory import Encoder, operation, response

from nyx.personal_memory import PersonalMemory
from nyx.voice import Conversations


def test_vec0_migrates_existing_vectors_and_preserves_source_bytes(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("The phone is on the shelf.", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response([operation(turn, "The phone is on the shelf.", "Phone on shelf")]),
    )
    saved = memory.process(turn)["saved_ids"][0]
    with conversations.connect() as db:
        before = tuple(db.execute("SELECT embedding,encoder FROM memories").fetchone())
        tables = db.execute(
            "SELECT sql FROM sqlite_master WHERE sql LIKE '%USING vec0%'"
        ).fetchall()
    assert tables, "Personal memory must use a native vec0 index"
    reopened = PersonalMemory(conversations, Encoder(), lambda *args: response())
    assert reopened.recall("phone")["matches"][0]["id"] == saved
    with conversations.connect() as db:
        assert tuple(db.execute("SELECT embedding,encoder FROM memories").fetchone()) == before


def test_recall_only_validates_selected_records_and_not_all_vectors(tmp_path, monkeypatch):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("My phone is here.", {})
    memory = PersonalMemory(conversations, Encoder(), lambda *args: response())
    with conversations.connect() as db:
        db.executemany(
            "INSERT INTO memories(id,turn_id,content,kind,quotes,embedding,encoder,visual) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    str(i),
                    turn,
                    "Phone",
                    "report",
                    json.dumps([{"turn_id": turn, "text": "My phone"}]),
                    np.array([1, i / 1000], dtype=np.float32).tobytes(),
                    json.dumps(Encoder.fingerprint),
                    "{}",
                )
                for i in range(1000)
            ],
        )
    memory = PersonalMemory(conversations, Encoder(), lambda *args: response())
    original = PersonalMemory._read_rows
    inspected = []

    def bounded(conversations, *, as_of=None, identifiers=None):
        assert identifiers is not None, "Recall must not validate the entire corpus"
        inspected.extend(identifiers)
        return original(conversations, as_of=as_of, identifiers=identifiers)

    monkeypatch.setattr(PersonalMemory, "_read_rows", staticmethod(bounded))
    result = memory.recall("phone")
    assert [r["id"] for r in result["matches"]] == [str(i) for i in range(5)]
    assert len(inspected) <= 32


def test_invalid_top_candidates_do_not_hide_valid_memories(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("My phone is on the shelf.", {})
    PersonalMemory(conversations, Encoder(), lambda *args: response())
    with conversations.connect() as db:
        db.executemany(
            "INSERT INTO memories(id,turn_id,content,kind,quotes,embedding,encoder,visual) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    str(i),
                    turn,
                    "Phone",
                    "report",
                    json.dumps(
                        [{"turn_id": turn, "text": "wrong quote" if i < 40 else "My phone"}]
                    ),
                    np.array([1, i / 100], dtype=np.float32).tobytes(),
                    json.dumps(Encoder.fingerprint),
                    "{}",
                )
                for i in range(45)
            ],
        )
    memory = PersonalMemory(conversations, Encoder(), lambda *args: response())
    assert [r["id"] for r in memory.recall("phone")["matches"]] == [str(i) for i in range(40, 45)]
