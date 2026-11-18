from typing import ClassVar

import numpy as np
import pytest

from nyx.personal_memory import PersonalMemory
from nyx.voice import Conversations


class Encoder:
    dimensions = 2
    fingerprint: ClassVar = {"model": "memory-fixture", "dimensions": 2}

    def encode_text(self, text):
        return np.array([1, 0], dtype=np.float32)


def response(operations=(), relevant_ids=(), **changes):
    return {
        "operations": list(operations),
        "relevant_ids": list(relevant_ids),
        "needs_visual": False,
        "clarification": "",
        **changes,
    }


def operation(turn_id, quote, content, **changes):
    return {
        "operation": "append",
        "content": content,
        "kind": "report",
        "grounding": "text",
        "related_id": None,
        "quotes": [{"turn_id": turn_id, "text": quote}],
        **changes,
    }


def test_ingest_skips_query_embedding_when_every_available_memory_fits(tmp_path):
    queries = []

    class CountingEncoder(Encoder):
        def encode_text(self, text):
            queries.append(text)
            return super().encode_text(text)

    conversations = Conversations(tmp_path)
    encoder = CountingEncoder()
    memory = PersonalMemory(
        conversations,
        encoder,
        lambda payload, schema: response(
            [
                operation(
                    payload["current_turn"]["turn_id"],
                    payload["current_turn"]["text"],
                    "Prefers unsweetened tea",
                )
            ]
        ),
    )
    first = conversations.begin("I prefer tea without sugar.", {})
    memory.process(first)
    second = conversations.begin("Hello again.", {})
    memory.interpret = lambda payload, schema: response()
    queries.clear()
    memory.process(second)
    assert queries == []
    assert len(memory.recall("What tea do I prefer?")["matches"]) == 1
    assert queries == ["What tea do I prefer?"]


def test_general_fact_survives_restart_and_is_processed_only_once(tmp_path):
    conversations = Conversations(tmp_path)
    text = "I prefer tea without sugar."
    turn = conversations.begin(text, {})
    calls = []

    def interpret(payload, schema):
        calls.append(payload)
        return response([operation(turn, text, "Prefers tea without sugar")])

    first = PersonalMemory(conversations, Encoder(), interpret).process(turn)
    assert first["status"] == "saved" and len(first["saved_ids"]) == 1
    conversations.finish(turn, "Noted")
    fresh = PersonalMemory(
        Conversations(tmp_path), Encoder(), lambda *args: pytest.fail("Repeated interpretation")
    )
    assert fresh.process(turn) == first
    found = fresh.recall("Tea preference")
    assert found["matches"][0]["content"] == "Prefers tea without sugar"
    assert found["sources"] == [f"transcript:{turn}"]
    assert len(calls) == 1


def test_memory_context_time_scope_is_shared_non_mutating_and_reversible():
    from nyx.personal_memory import memory_context_at

    old = {"at": "2026-11-10T12:00:00Z", "sources": ["transcript:old"]}
    new = {"at": "2026-11-12T12:00:00Z", "sources": ["transcript:new"]}
    undated = {"at": None, "sources": ["transcript:undated"]}
    context = {
        "status": "saved",
        "answer": "Memory saved.",
        "records": [old, new, undated],
        "sources": ["transcript:old", "transcript:new", "transcript:undated"],
    }
    scoped = memory_context_at(context, "2026-11-11T12:00:00Z")
    assert scoped["records"] == [old] and scoped["sources"] == ["transcript:old"]
    assert scoped["status"] == "saved" and scoped["answer"] == "Memory saved."
    assert context["records"] == [old, new, undated]
    assert memory_context_at(context, None) == context


def test_independent_user_fact_survives_deletion_of_assistant_lookup_evidence(tmp_path):
    conversations = Conversations(tmp_path)
    text = "I prefer tea without sugar. Where are my keys?"
    turn = conversations.begin(text, {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response(
            [operation(turn, "I prefer tea without sugar", "Prefers tea without sugar")]
        ),
    )
    memory.process(turn)
    conversations.finish(turn, "Possible keys beside the amber jar", ["deleted-video"])
    conversations.invalidate("deleted-video")
    assert memory.recall("tea preference")["matches"][0]["content"] == "Prefers tea without sugar"


def test_moves_preserve_history_and_explicit_corrections_version_reports(tmp_path):
    conversations = Conversations(tmp_path)
    replies = []
    memory = PersonalMemory(conversations, Encoder(), lambda *args: replies.pop(0))
    old = conversations.begin("My keys are in the drawer", {})
    replies.append(response([operation(old, "My keys are in the drawer", "Keys in drawer")]))
    old_id = memory.process(old)["saved_ids"][0]
    moved = conversations.begin("I moved my keys to the bag", {})
    replies.append(
        response(
            [operation(moved, "I moved my keys to the bag", "Keys moved to bag", related_id=old_id)]
        )
    )
    moved_id = memory.process(moved)["saved_ids"][0]
    assert {r["id"] for r in memory.recall("keys")["matches"]} == {old_id, moved_id}
    corrected = conversations.begin("Correction: my keys are in the coat, not the bag", {})
    replies.append(
        response(
            [
                operation(
                    corrected,
                    "my keys are in the coat",
                    "Keys in coat",
                    operation="correct",
                    related_id=moved_id,
                )
            ]
        )
    )
    corrected_id = memory.process(corrected)["saved_ids"][0]
    current = {r["id"] for r in memory.recall("keys")["matches"]}
    assert corrected_id in current and moved_id not in current
    with conversations.connect() as db:
        assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 3


def test_plan_remains_a_plan_and_empty_input_can_be_a_noop(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I will put my bottle by the door later", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response(
            [
                operation(
                    turn,
                    "I will put my bottle by the door later",
                    "Plans to put bottle by door",
                    kind="plan",
                )
            ]
        ),
    )
    memory.process(turn)
    assert memory.recall("bottle")["matches"][0]["kind"] == "plan"
    hello = conversations.begin("Hello", {})
    noop = PersonalMemory(conversations, Encoder(), lambda *args: response()).process(hello)
    assert noop["status"] == "noop" and noop["saved_ids"] == []


def test_fabricated_sources_or_target_cannot_write_a_memory(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("My keys are in the drawer", {})
    for bad in [
        operation("invented-turn", "keys", "Keys in drawer"),
        operation(turn, "Words I never said", "Keys in drawer"),
        operation(
            turn, "keys", "Keys in drawer", operation="correct", related_id="invented-memory"
        ),
    ]:
        memory = PersonalMemory(conversations, Encoder(), lambda *args, bad=bad: response([bad]))
        with pytest.raises(ValueError):
            memory.process(turn)
    with conversations.connect() as db:
        assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 0
    assert conversations.recent()[0]["transcript"] == "My keys are in the drawer"


def test_embedding_failure_leaves_no_partial_memory_and_allows_retry(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I prefer tea", {})
    interpret = lambda *args: response([operation(turn, "I prefer tea", "Prefers tea")])

    class Broken(Encoder):
        def encode_text(self, text):
            raise ValueError("Embedding unavailable")

    memory = PersonalMemory(conversations, Broken(), interpret)
    with pytest.raises(ValueError, match="Embedding"):
        memory.process(turn)
    assert PersonalMemory(conversations, Encoder(), interpret).process(turn)["status"] == "saved"


def test_existing_linked_statements_import_without_reembedding_or_source_changes(tmp_path):
    import json

    conversations = Conversations(tmp_path)
    text = "I put my phone in the kitchen drawer."
    turn = conversations.begin(text, {})
    conversations.finish(turn, "Saved")
    with conversations.connect() as db:
        db.execute(
            "CREATE TABLE statements(turn_id TEXT PRIMARY KEY,object_description TEXT,kind TEXT,captured_at TEXT,image BLOB,embedding BLOB,encoder TEXT,resolver TEXT)"
        )
        db.execute(
            "INSERT INTO statements VALUES (?,?,?,?,?,?,?,?)",
            (
                turn,
                "phone",
                "reported_placement",
                "2026-11-10T10:00:00Z",
                b"original-photo",
                np.array([1, 0], dtype=np.float32).tobytes(),
                json.dumps(Encoder.fingerprint),
                '{"reference_version":2}',
            ),
        )
    memory = PersonalMemory(
        conversations, Encoder(), lambda *args: pytest.fail("Migration called a model")
    )
    row = memory.recall("phone")["matches"][0]
    assert row["content"] == text and row["kind"] == "report"
    assert row["visual"]["captured_at"] == "2026-11-10T10:00:00Z"
    assert row["has_image"] is True
    with conversations.connect() as db:
        assert db.execute("SELECT image FROM statements").fetchone()[0] == b"original-photo"
        assert db.execute("SELECT image FROM memories").fetchone()[0] == b"original-photo"


def test_visual_evidence_is_requested_once_and_ambiguity_does_not_create_a_link(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I left this in the drawer", {})
    calls = []

    def interpret(payload, schema):
        calls.append(payload)
        return response(needs_visual=True)

    checks = []

    def observe():
        checks.append(True)
        return {"status": "clarify", "answer": "Which item?"}

    result = PersonalMemory(conversations, Encoder(), interpret).process(turn, observe=observe)
    assert result["status"] == "clarify" and result["saved_ids"] == []
    assert len(calls) == len(checks) == 1


def test_cancellation_stops_before_followup_visual_work(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I left this in the drawer", {})
    enabled = [True]

    def interpret(*args):
        enabled[0] = False
        return response(needs_visual=True)

    memory = PersonalMemory(conversations, Encoder(), interpret)
    with pytest.raises(ValueError, match="cancel"):
        memory.process(
            turn,
            active=lambda: enabled[0],
            observe=lambda: pytest.fail("Cancelled visual work ran"),
        )


def test_unavailable_correction_never_resurrects_a_superseded_memory(tmp_path):
    conversations = Conversations(tmp_path)
    old = conversations.begin("The keys are in the drawer", {})
    first = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response([operation(old, "keys are in the drawer", "Keys in drawer")]),
    )
    old_id = first.process(old)["saved_ids"][0]
    new = conversations.begin("Correction: keys are in the bag", {})
    second = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response(
            [
                operation(
                    new,
                    "keys are in the bag",
                    "Keys in bag",
                    operation="correct",
                    related_id=old_id,
                )
            ]
        ),
    )
    second.process(new)
    with conversations.connect() as db:
        db.execute("UPDATE turns SET input_available=0 WHERE id=?", (new,))
    assert second.recall("keys")["matches"] == []


def test_correction_can_cite_an_older_retrieved_memory_after_context_eviction(tmp_path):
    conversations = Conversations(tmp_path)
    old = conversations.begin("My spare keys are in the drawer", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response(
            [operation(old, "My spare keys are in the drawer", "Spare keys in drawer")]
        ),
    )
    old_id = memory.process(old)["saved_ids"][0]
    for i in range(25):
        turn = conversations.begin(f"Unrelated turn {i}", {})
        conversations.finish(turn, "Okay")
    current = conversations.begin("I was mistaken; they are in the bag", {})
    correction = operation(
        current,
        "I was mistaken; they are in the bag",
        "Spare keys in bag",
        operation="correct",
        related_id=old_id,
    )
    correction["quotes"].append({"turn_id": old, "text": "My spare keys"})
    saved = PersonalMemory(conversations, Encoder(), lambda *args: response([correction])).process(
        current
    )
    assert saved["status"] == "saved"
    assert saved["sources"] == sorted([f"transcript:{old}", f"transcript:{current}"])


def test_prepared_context_revalidates_deleted_quotes_and_superseded_records(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("My keys are in the drawer", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response([operation(turn, "My keys are in the drawer", "Keys in drawer")]),
    )
    memory.process(turn)
    assert PersonalMemory.turn_context(conversations, turn)["records"]
    conversations.finish(turn, "Noted", ["deleted-clip"])
    conversations.invalidate("deleted-clip")
    assert PersonalMemory.turn_context(conversations, turn)["records"]
    conversations.invalidate("transcript:" + turn)
    context = PersonalMemory.turn_context(conversations, turn)
    assert not context["records"] and not context["sources"]
    assert context["status"] == "uncertain" and "Memory saved" not in context["answer"]


def test_bad_stored_vector_withholds_candidate_and_reports_coverage(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("My keys are in the drawer", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response([operation(turn, "My keys are in the drawer", "Keys in drawer")]),
    )
    memory.process(turn)
    with conversations.connect() as db:
        db.execute("UPDATE memories SET embedding=?", (b"broken",))
    result = memory.recall("keys")
    assert not result["matches"]
    # The native index rejects changed vector bytes before candidate validation.
    # Coverage describes inspected candidates, not an exhaustive archive audit.
    assert "candidate_unavailable_count" in result["coverage"]


def test_source_change_during_interpretation_writes_nothing_and_can_retry(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I like tea", {})

    def interpret(*args):
        with conversations.connect() as db:
            db.execute("UPDATE turns SET input_available=0 WHERE id=?", (turn,))
        return response([operation(turn, "I like tea", "Likes tea")])

    memory = PersonalMemory(conversations, Encoder(), interpret)
    with pytest.raises(ValueError, match="unavailable"):
        memory.process(turn)
    with conversations.connect() as db:
        assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM memory_turns").fetchone()[0] == 0


def test_correction_changed_by_an_intervening_request_is_not_overwritten(tmp_path):
    conversations = Conversations(tmp_path)
    first = conversations.begin("My keys are in the drawer", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response([operation(first, "My keys are in the drawer", "Keys in drawer")]),
    )
    old_id = memory.process(first)["saved_ids"][0]
    current = conversations.begin("Correction: my keys are in the bag", {})

    def interpret(*args):
        with conversations.connect() as db:
            db.execute("INSERT INTO memory_relations VALUES (?,?,?)", (old_id, "other", "correct"))
        return response(
            [
                operation(
                    current,
                    "my keys are in the bag",
                    "Keys in bag",
                    operation="correct",
                    related_id=old_id,
                )
            ]
        )

    memory.interpret = interpret
    with pytest.raises(ValueError, match="changed"):
        memory.process(current)
    with conversations.connect() as db:
        assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 1


def test_historical_state_uses_microseconds_timezones_and_excludes_future_reports(tmp_path):
    conversations = Conversations(tmp_path)
    replies = []
    memory = PersonalMemory(conversations, Encoder(), lambda *args: replies.pop(0))
    old = conversations.begin("My phone is in the kitchen", {})
    with conversations.connect() as db:
        db.execute("UPDATE turns SET at='2026-11-06T12:00:00Z' WHERE id=?", (old,))
    replies.append(response([operation(old, "My phone is in the kitchen", "Phone in kitchen")]))
    old_id = memory.process(old)["saved_ids"][0]
    new = conversations.begin("Correction: my phone is in the bag", {})
    with conversations.connect() as db:
        db.execute("UPDATE turns SET at='2026-11-06T12:00:00.000100Z' WHERE id=?", (new,))
    replies.append(
        response(
            [
                operation(
                    new,
                    "my phone is in the bag",
                    "Phone in bag",
                    operation="correct",
                    related_id=old_id,
                )
            ]
        )
    )
    memory.process(new)
    assert [
        r["turn_id"] for r in memory.recall("phone", as_of="2026-11-06T17:30:00+05:30")["matches"]
    ] == [old]
    assert [r["turn_id"] for r in memory.recall("phone")["matches"]] == [new]
    future = conversations.begin("The spare phone is on the desk", {})
    replies.append(
        response([operation(future, "The spare phone is on the desk", "Spare phone on desk")])
    )
    memory.process(future)
    with conversations.connect() as db:
        db.execute("UPDATE turns SET at='2099-01-01T00:00:00Z' WHERE id=?", (future,))
    assert future not in [r["turn_id"] for r in memory.recall("phone")["matches"]]
    with pytest.raises(ValueError, match="future"):
        memory.recall("phone", as_of="2099-01-01T00:00:00Z")


def test_retraction_preserves_old_history_without_inventing_a_new_location(tmp_path):
    conversations = Conversations(tmp_path)
    replies = []
    memory = PersonalMemory(conversations, Encoder(), lambda *args: replies.pop(0))
    old = conversations.begin("My phone is in the kitchen", {})
    replies.append(response([operation(old, "My phone is in the kitchen", "Phone in kitchen")]))
    old_id = memory.process(old)["saved_ids"][0]
    new = conversations.begin("I withdraw that claim. I do not know where my phone is.", {})
    replies.append(
        response(
            [
                operation(
                    new,
                    "I withdraw that claim.",
                    "Retracts phone location",
                    operation="retract",
                    related_id=old_id,
                )
            ]
        )
    )
    memory.process(new)
    matches = memory.recall("phone")["matches"]
    assert len(matches) == 1 and matches[0]["kind"] == "retraction"
    with conversations.connect() as db:
        assert (
            db.execute("SELECT content FROM memories WHERE id=?", (old_id,)).fetchone()[0]
            == "Phone in kitchen"
        )


def test_database_write_failure_rolls_back_memory_and_turn_marker(tmp_path):
    import sqlite3

    conversations = Conversations(tmp_path)
    turn = conversations.begin("I like black tea", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response([operation(turn, "I like black tea", "Likes black tea")]),
    )
    with conversations.connect() as db:
        db.execute(
            "CREATE TRIGGER refuse_memory BEFORE INSERT ON memory_turns BEGIN SELECT RAISE(ABORT,'simulated disk failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="disk failure"):
        memory.process(turn)
    with conversations.connect() as db:
        assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM memory_turns").fetchone()[0] == 0
        assert (
            db.execute("SELECT transcript FROM turns WHERE id=?", (turn,)).fetchone()[0]
            == "I like black tea"
        )
        db.execute("DROP TRIGGER refuse_memory")
    assert memory.process(turn)["status"] == "saved"


def test_future_dated_user_reports_are_not_reintroduced_through_recent_turns(tmp_path):
    conversations = Conversations(tmp_path)
    old = conversations.begin("My watch is in the cabinet", {})
    conversations.finish(old, "Noted")
    with conversations.connect() as db:
        db.execute("UPDATE turns SET at='2099-01-01T00:00:00Z' WHERE id=?", (old,))
    turn = conversations.begin("What have I said about my watch up to now?", {})

    def interpret(payload, schema):
        assert not payload["recent_user_turns"] and not payload["memories"]
        assert payload["current_turn"]["turn_id"] == turn
        return response()

    result = PersonalMemory(conversations, Encoder(), interpret).process(turn)
    assert result["status"] == "noop" and not result["saved_ids"]


def test_recall_selects_relevant_records_in_memory_component_without_writing(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("My headphones are in the cabinet", {})
    replies = [
        response([operation(turn, "My headphones are in the cabinet", "Headphones in cabinet")]),
        response(),
    ]
    calls = []

    def interpret(payload, schema):
        calls.append(payload)
        return replies.pop(0)

    memory = PersonalMemory(conversations, Encoder(), interpret)
    memory.process(turn)
    result = memory.recall("Have I told you where my scarf is?", select=True)
    assert result["status"] == "uncertain" and result["matches"] == []
    assert calls[-1]["mode"] == "recall" and len(calls[-1]["memories"]) == 1
    with conversations.connect() as db:
        assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 1


def test_recall_selection_cannot_return_fabricated_or_newly_deleted_sources(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I like black tea", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response([operation(turn, "I like black tea", "Likes black tea")]),
    )
    identifier = memory.process(turn)["saved_ids"][0]
    memory.interpret = lambda *args: response(relevant_ids=["invented"])
    with pytest.raises(ValueError, match="selection"):
        memory.recall("tea", select=True)

    def deleting(*args):
        with conversations.connect() as db:
            db.execute("UPDATE turns SET input_available=0 WHERE id=?", (turn,))
        return response(relevant_ids=[identifier])

    memory.interpret = deleting
    with pytest.raises(ValueError, match="source changed"):
        memory.recall("tea", select=True)


def test_context_resolved_memory_inherits_original_visual_clock_photo_and_sources(tmp_path):
    from PIL import Image

    conversations = Conversations(tmp_path)
    first = conversations.begin("I put this on the table", {})
    replies = [
        response(needs_visual=True),
        response(
            [operation(first, "I put this on the table", "Blue phone on table", grounding="visual")]
        ),
    ]
    memory = PersonalMemory(conversations, Encoder(), lambda *args: replies.pop(0))
    old_id = memory.process(
        first,
        observe=lambda: {
            "status": "resolved",
            "object_description": "blue phone",
            "captured_at": "2026-11-06T12:00:00Z",
            "image": Image.new("RGB", (10, 10), "blue"),
        },
    )["saved_ids"][0]
    second = conversations.begin("I moved it into my bag", {})
    replies.append(
        response(
            [
                operation(
                    second,
                    "I moved it into my bag",
                    "Blue phone moved into bag",
                    related_id=old_id,
                    grounding="memory",
                )
            ]
        )
    )
    saved = memory.process(second)
    assert set(saved["sources"]) == {"transcript:" + first, "transcript:" + second}
    current = next(row for row in memory.recall("phone")["matches"] if row["turn_id"] == second)
    assert current["visual"]["captured_at"] == "2026-11-06T12:00:00Z" and current["has_image"]
    assert set(current["sources"]) == set(saved["sources"])
    with conversations.connect() as db:
        photos = [row[0] for row in db.execute("SELECT image FROM memories")]
        assert photos[0] == photos[1]
        db.execute("UPDATE turns SET input_available=0 WHERE id=?", (first,))
    assert memory.recall("phone")["matches"] == []


def test_successful_correction_does_not_mark_its_intentionally_replaced_context_unavailable(
    tmp_path,
):
    conversations = Conversations(tmp_path)
    first = conversations.begin("I like tea", {})
    replies = [response([operation(first, "I like tea", "Likes tea")])]
    memory = PersonalMemory(conversations, Encoder(), lambda *args: replies.pop(0))
    old_id = memory.process(first)["saved_ids"][0]
    second = conversations.begin("Correction: I meant coffee", {})
    replies.append(
        response(
            [
                operation(
                    second,
                    "Correction: I meant coffee",
                    "Likes coffee",
                    operation="correct",
                    related_id=old_id,
                )
            ],
            relevant_ids=[old_id],
        )
    )
    memory.process(second)
    context = memory.turn_context(conversations, second)
    assert context["status"] == "saved" and len(context["records"]) == 1
    assert context["records"][0]["content"] == "Likes coffee"


def test_one_visual_observation_is_not_attached_to_unrelated_facts_in_same_utterance(tmp_path):
    from PIL import Image

    conversations = Conversations(tmp_path)
    text = "I put this in my bag, and my glasses are on the table."
    turn = conversations.begin(text, {})
    replies = [
        response(needs_visual=True),
        response(
            [
                operation(turn, "I put this in my bag", "Phone in bag", grounding="visual"),
                operation(
                    turn, "my glasses are on the table", "Glasses on table", grounding="text"
                ),
            ]
        ),
    ]
    memory = PersonalMemory(conversations, Encoder(), lambda *args: replies.pop(0))
    memory.process(
        turn,
        observe=lambda: {
            "status": "resolved",
            "object_description": "phone",
            "captured_at": "2026-11-17T00:00:00Z",
            "image": Image.new("RGB", (10, 10), "blue"),
        },
    )
    records = {r["content"]: r for r in memory.recall("belongings")["matches"]}
    assert records["Phone in bag"]["has_image"]
    assert (
        not records["Glasses on table"]["has_image"] and records["Glasses on table"]["visual"] == {}
    )


def test_visual_resolution_refreshes_candidates_beyond_initial_pronoun_query(tmp_path):
    from PIL import Image

    class DistinctEncoder(Encoder):
        def encode_text(self, text):
            return np.array([0, 1] if "blue phone" in text.lower() else [1, 0], dtype=np.float32)

    conversations = Conversations(tmp_path)
    replies = []
    memory = PersonalMemory(conversations, DistinctEncoder(), lambda *args: replies.pop(0))
    old = conversations.begin("My blue phone is in the desk drawer", {})
    replies.append(
        response(
            [operation(old, "My blue phone is in the desk drawer", "Blue phone in desk drawer")]
        )
    )
    identifier = memory.process(old)["saved_ids"][0]
    conversations.finish(old, "Noted")
    for index in range(25):
        text = f"Unrelated fact number {index}"
        turn = conversations.begin(text, {})
        replies.append(response([operation(turn, text, text)]))
        memory.process(turn)
        conversations.finish(turn, "Noted")
    query = conversations.begin("Where did I put this?", {})
    seen = []

    def interpret(payload, schema):
        seen.append(payload)
        ids = {row["id"] for row in payload["memories"]}
        if payload["visual"] is None:
            assert identifier not in ids
            return response(needs_visual=True)
        assert identifier in ids
        return response(relevant_ids=[identifier])

    memory.interpret = interpret
    memory.process(
        query,
        observe=lambda: {
            "status": "resolved",
            "object_description": "blue phone",
            "captured_at": "2026-11-17T00:00:00Z",
            "image": Image.new("RGB", (10, 10), "blue"),
        },
    )
    assert len(seen) == 2
    assert memory.turn_context(conversations, query)["records"][0]["turn_id"] == old


@pytest.mark.parametrize("grounding", ["visual", "memory"])
def test_fabricated_grounding_cannot_save_without_its_required_source(tmp_path, grounding):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I put this in my bag", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response(
            [operation(turn, "I put this in my bag", "Phone in bag", grounding=grounding)]
        ),
    )
    with pytest.raises(ValueError, match="grounding"):
        memory.process(turn)
    with conversations.connect() as db:
        assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 0


def test_interpretation_model_is_recorded_before_an_assistant_can_fail(tmp_path):
    import json

    conversations = Conversations(tmp_path)
    turn = conversations.begin("I prefer tea", {})
    model_info = {"model": "fixture-interpreter", "memory_policy_version": 4}
    PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response([operation(turn, "I prefer tea", "Prefers tea")]),
        model_info=model_info,
    ).process(turn)
    conversations.finish(turn, status="interrupted")
    with conversations.connect() as db:
        result = json.loads(
            db.execute("SELECT result FROM memory_turns WHERE turn_id=?", (turn,)).fetchone()[0]
        )
        assert result["model_info"] == model_info
        assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 1


def test_unresolved_interpretation_discards_proposed_writes_and_returns_clarification(tmp_path):
    conversations = Conversations(tmp_path)
    turn = conversations.begin("I put it there", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response(
            [operation(turn, "I put it there", "Unspecified object in unspecified place")],
            clarification="Which item and location do you mean?",
        ),
    )
    result = memory.process(turn)
    assert result["status"] == "clarify" and result["saved_ids"] == []
    assert result["answer"] == "Which item and location do you mean?"
    with conversations.connect() as db:
        assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 0
        assert (
            db.execute("SELECT transcript FROM turns WHERE id=?", (turn,)).fetchone()[0]
            == "I put it there"
        )
