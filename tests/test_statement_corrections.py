import json
from types import SimpleNamespace
from typing import ClassVar

import pytest

from nyx.statements import Statements
from nyx.voice import Conversations


def test_legacy_transcript_fallback_cannot_resurrect_corrected_report(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    new = begin(conversations, "Correction: it is in the bag", "2026-11-07T12:00:00Z")
    statements.remember(new, verifier("bag"), Encoder(), supersedes_turn_id=old)
    forged = SimpleNamespace(generate_json=lambda *a, **k: json.dumps({"statement_ids": [old]}))
    with pytest.raises(ValueError, match="citations"):
        statements.recall("phone", Encoder(), forged)
    historical = statements.recall("phone", Encoder(), forged, as_of="2026-11-06T18:00:00Z")
    assert historical["matches"][0]["turn_id"] == old


def test_as_of_cutoff_respects_microseconds_and_different_timezones(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00+00:00")
    statements.remember(old, verifier(), Encoder())
    new = begin(conversations, "Correction: it is in the bag", "2026-11-06T12:00:00.000100+00:00")
    statements.remember(new, verifier("bag"), Encoder(), supersedes_turn_id=old)
    assert [
        r["turn_id"]
        for r in statements.search("phone", Encoder(), as_of="2026-11-06T17:30:00+05:30")
    ] == [old]


class Encoder:
    dimensions = 2
    device = "cpu"
    fingerprint: ClassVar = {"model": "correction-test"}

    def encode_text(self, text):
        import numpy as np

        return np.array([1, 0], dtype=np.float32)


def test_statement_source_invalidated_during_verification_is_not_returned(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    conversations.finish(old, sources=["source-video"])

    def invalidate(*args, **kwargs):
        conversations.invalidate("source-video")
        return json.dumps({"statement_ids": [old]})

    with pytest.raises(ValueError, match="available|changed"):
        statements.recall("phone", Encoder(), SimpleNamespace(generate_json=invalidate))


def verifier(destination="kitchen", accepted=True, kind="reported_placement"):
    def generate(messages, *args, **kwargs):
        if any(m["role"] == "system" and "CORRECTION_CHECK_V1" in m["content"] for m in messages):
            return json.dumps(
                {
                    "corrects_report": accepted,
                    "same_referent": accepted,
                    "kind": kind,
                    "destination": destination,
                    "ambiguous": False,
                }
            )
        return json.dumps(
            {
                "object_description": "phone",
                "kind": "reported_placement",
                "source": "explicit_text",
                "frame_index": -1,
                "destination": destination,
                "ambiguous": False,
            }
        )

    return SimpleNamespace(generate_json=generate, fingerprint={"model": "fake-verifier"})


def test_explicit_retraction_supersedes_report_without_inventing_new_location(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    new = begin(
        conversations, "I was wrong, my phone is not in the kitchen", "2026-11-07T12:00:00Z"
    )
    result = statements.remember(
        new, verifier("", kind="retraction"), Encoder(), supersedes_turn_id=old
    )
    assert result["status"] == "complete"
    current = statements.search("phone", Encoder())
    assert len(current) == 1 and current[0]["kind"] == "retraction" and current[0]["turn_id"] == new
    assert statements.search("phone", Encoder(), as_of="2026-11-06T18:00:00Z")[0]["turn_id"] == old


def test_report_correction_and_recall_carry_transitive_source_dependencies(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    conversations.finish(old, sources=["original-video"])
    new = begin(conversations, "Correction: it is in the bag", "2026-11-07T12:00:00Z")
    result = statements.remember(new, verifier("bag"), Encoder(), supersedes_turn_id=old)
    conversations.finish(new, sources=result["sources"])
    found = statements.recall(
        "phone",
        Encoder(),
        SimpleNamespace(generate_json=lambda *a, **k: json.dumps({"statement_ids": [new]})),
    )
    answer = conversations.begin("Where is my phone?", {})
    conversations.finish(answer, sources=found["sources"])
    conversations.invalidate("original-video")
    assert not conversations.recent()[-1]["sources_available"]
    assert statements.search("phone", Encoder()) == []


def begin(conversations, text, at):
    identifier = conversations.begin(text, {})
    with conversations.connect() as db:
        db.execute("UPDATE turns SET at=? WHERE id=?", (at, identifier))
    return identifier


def test_correction_survives_restart_and_preserves_historical_report(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    new = begin(
        conversations, "Correction: it is in the bag, I was mistaken", "2026-11-07T12:00:00Z"
    )
    result = statements.remember(new, verifier("bag"), Encoder(), supersedes_turn_id=old)
    assert result["status"] == "complete"
    fresh = Statements(Conversations(tmp_path))
    assert [r["turn_id"] for r in fresh.search("phone", Encoder())] == [new]
    assert [
        r["turn_id"] for r in fresh.search("phone", Encoder(), as_of="2026-11-06T18:00:00Z")
    ] == [old]
    with conversations.connect() as db:
        assert (
            db.execute("SELECT transcript FROM turns WHERE id=?", (old,)).fetchone()[0]
            == "My phone is in the kitchen"
        )
    again = fresh.remember(new, verifier("bag"), Encoder(), supersedes_turn_id=old)
    assert again["status"] == "complete"


def test_unverified_correction_does_not_partially_save_a_link(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    new = begin(conversations, "Maybe it is in the bag?", "2026-11-07T12:00:00Z")
    result = statements.remember(new, verifier("bag", False), Encoder(), supersedes_turn_id=old)
    assert result["status"] == "clarify"
    assert [r["turn_id"] for r in statements.search("phone", Encoder())] == [old]
    with conversations.connect() as db:
        assert db.execute("SELECT transcript FROM turns WHERE id=?", (new,)).fetchone()
        assert db.execute("SELECT count(*) FROM statement_corrections").fetchone()[0] == 0


@pytest.mark.parametrize("correcting", [False, True])
def test_source_invalidated_during_embedding_cannot_persist_statement(tmp_path, correcting):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    new = begin(conversations, "Correction: my phone is in the bag", "2026-11-07T12:00:00Z")
    conversations.finish(new, sources=["pending-source"])

    class InvalidatingEncoder(Encoder):
        def encode_text(self, text):
            conversations.invalidate("pending-source")
            return super().encode_text(text)

    with pytest.raises(ValueError, match="source.*available"):
        statements.remember(
            new,
            verifier("bag"),
            InvalidatingEncoder(),
            supersedes_turn_id=old if correcting else None,
        )
    with conversations.connect() as db:
        assert (
            db.execute("SELECT count(*) FROM statements WHERE turn_id=?", (new,)).fetchone()[0] == 0
        )
        assert db.execute("SELECT count(*) FROM statement_corrections").fetchone()[0] == 0
    assert [r["turn_id"] for r in statements.search("phone", Encoder())] == [old]


def test_retry_cannot_acknowledge_a_statement_with_invalidated_sources(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    conversations.finish(old, sources=["source-video"])
    conversations.invalidate("source-video")
    with pytest.raises(ValueError, match="source.*available"):
        statements.remember(old, verifier(), Encoder())


def test_deleted_replacement_does_not_resurrect_superseded_report(tmp_path):
    conversations = Conversations(tmp_path)
    statements = Statements(conversations)
    old = begin(conversations, "My phone is in the kitchen", "2026-11-06T12:00:00Z")
    statements.remember(old, verifier(), Encoder())
    new = begin(conversations, "Correction: it is in the bag", "2026-11-07T12:00:00Z")
    statements.remember(new, verifier("bag"), Encoder(), supersedes_turn_id=old)
    with conversations.connect() as db:
        db.execute("UPDATE turns SET sources_available=0 WHERE id=?", (new,))
    assert statements.search("phone", Encoder()) == []
    assert [
        r["turn_id"] for r in statements.search("phone", Encoder(), as_of="2026-11-06T18:00:00Z")
    ] == [old]
