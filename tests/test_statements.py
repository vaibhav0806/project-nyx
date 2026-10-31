import json
from types import SimpleNamespace
from typing import ClassVar

import numpy as np
from PIL import Image

from nyx.statements import Statements
from nyx.voice import Conversations


class Encoder:
    fingerprint: ClassVar = {"model": "synthetic-test"}

    def encode_text(self, text):
        return np.array([1, 0] if "phone" in text else [0, 1], dtype=np.float32)


def test_pronoun_link_survives_restart_without_recent_chat(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I'm going to keep this in the kitchen.", {"mode": "test"})
    seen = []

    def resolve(messages, limit, **kwargs):
        seen.append(next(p["image"] for p in messages[0]["content"] if p["type"] == "image"))
        return json.dumps(
            {
                "object_description": "black phone",
                "kind": "intention",
                "source": "visual",
                "frame_index": 0,
                "destination": "kitchen",
                "ambiguous": False,
            }
        )

    Statements(conversations).remember(
        turn,
        SimpleNamespace(generate_json=resolve),
        Encoder(),
        Image.new("RGB", (40, 40)),
        "2026-10-31T12:00:00Z",
    )
    assert len(seen) == 1
    for _ in range(30):
        conversations.begin("Unrelated conversation", {"mode": "test"})
    fresh = Conversations(tmp_path)
    assert turn not in [r["id"] for r in fresh.recent()]
    matches = Statements(fresh).search("phone", Encoder())
    assert matches[0]["turn_id"] == turn
    assert matches[0]["kind"] == "intention"
    assert matches[0]["has_image"]
    assert matches[0]["text"] == "I'm going to keep this in the kitchen."


def test_ambiguous_link_does_not_create_object_memory(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("Put this there?", {})
    store = Statements(conversations)
    result = store.remember(
        turn,
        SimpleNamespace(
            generate_json=lambda *_, **kwargs: '{"kind":"none","object_description":""}'
        ),
        Encoder(),
    )
    assert result["status"] == "clarify"
    assert store.search("phone", Encoder()) == []
    assert conversations.recent()[0]["transcript"] == "Put this there?"


def test_embedding_failure_keeps_original_transcript_without_partial_link(tmp_path):
    import pytest

    conversations = Conversations(tmp_path)
    turn = conversations.begin("I'll keep my phone in the kitchen", {})
    store = Statements(conversations)

    class Broken(Encoder):
        def encode_text(self, text):
            raise ValueError("Provider failed")

    with pytest.raises(ValueError):
        store.remember(
            turn,
            SimpleNamespace(
                generate_json=lambda *_, **kwargs: (
                    '{"kind":"intention","object_description":"phone","source":"explicit_text","frame_index":-1,"destination":"kitchen","ambiguous":false}'
                )
            ),
            Broken(),
        )
    assert store.search("phone", Encoder()) == []
    assert conversations.recent()[0]["id"] == turn


def test_recall_filters_candidates_and_rejects_fabricated_citation(tmp_path):
    import pytest

    conversations = Conversations(tmp_path)
    turn = conversations.begin("My phone is on the kitchen counter", {})
    store = Statements(conversations)
    relevant = SimpleNamespace(
        generate_json=lambda *_, **kwargs: json.dumps({"statement_ids": [turn]})
    )
    result = store.recall("phone", Encoder(), relevant)
    assert result["matches"][0]["turn_id"] == turn
    assert "kitchen counter" in result["answer"]
    assert "not visual confirmation" in result["answer"]
    empty = SimpleNamespace(generate_json=lambda *_, **kwargs: '{"statement_ids": []}')
    assert not store.recall("phone", Encoder(), empty)["matches"]
    forged = SimpleNamespace(generate_json=lambda *_, **kwargs: '{"statement_ids": ["invented"]}')
    with pytest.raises(ValueError, match="citations"):
        store.recall("phone", Encoder(), forged)


def test_invalidated_original_is_not_recalled(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I'll keep my phone in the kitchen", {})
    store = Statements(conversations)
    store.remember(
        turn,
        SimpleNamespace(
            generate_json=lambda *_, **kwargs: (
                '{"kind":"intention","object_description":"phone","source":"explicit_text","frame_index":-1,"destination":"kitchen","ambiguous":false}'
            )
        ),
        Encoder(),
    )
    conversations.finish(turn, sources=["removed-video"])
    conversations.invalidate("removed-video")
    assert not store.search("phone", Encoder())


def test_malformed_model_output_never_creates_link(tmp_path):
    import pytest

    conversations = Conversations(tmp_path)
    turn = conversations.begin("I'll put this in the kitchen", {})
    store = Statements(conversations)
    with pytest.raises(ValueError, match="Invalid object reference"):
        store.remember(turn, SimpleNamespace(generate_json=lambda *_, **kwargs: "[]"), Encoder())
    assert not store.search("phone", Encoder())


def test_repair_preserves_old_link_and_replaces_only_after_valid_resolution(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I'll put this in my wardrobe", {})
    store = Statements(conversations)
    with conversations.connect() as db:
        db.execute(
            "INSERT INTO statements VALUES (?,?,?,?,?,?,?,?)",
            (turn, "wardrobe", "intention", None, None, b"old", "{}", "{}"),
        )
    result = store.remember(
        turn, SimpleNamespace(generate_json=lambda *a, **k: "{}"), Encoder(), repair=True
    )
    assert result["status"] == "clarify"
    with conversations.connect() as db:
        assert db.execute("SELECT object_description FROM statements").fetchone()[0] == "wardrobe"
    good = {
        "object_description": "water bottle",
        "destination": "my wardrobe",
        "kind": "intention",
        "source": "visual",
        "frame_index": 0,
        "ambiguous": False,
    }
    result = store.remember(
        turn,
        SimpleNamespace(generate_json=lambda *a, **k: json.dumps(good)),
        Encoder(),
        frames=[{"image": Image.new("RGB", (20, 20)), "captured_at": "2026-10-31T12:00:00Z"}],
        repair=True,
    )
    assert result["status"] == "complete"
    with conversations.connect() as db:
        assert (
            db.execute("SELECT object_description FROM statements").fetchone()[0] == "water bottle"
        )
        assert (
            db.execute("SELECT object_description FROM statement_revisions").fetchone()[0]
            == "wardrobe"
        )
        assert (
            db.execute("SELECT transcript FROM turns WHERE id=?", (turn,)).fetchone()[0]
            == "I'll put this in my wardrobe"
        )


def test_repair_connection_does_not_interrupt_pending_turns(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("An active spoken turn", {})
    observer = Conversations(tmp_path, recover_pending=False)
    assert next(row for row in observer.recent() if row["id"] == turn)["status"] == "pending"
