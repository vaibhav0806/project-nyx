import threading
from concurrent.futures import TimeoutError
from types import SimpleNamespace

import pytest
from test_personal_memory import Encoder, operation, response

from nyx.personal_memory import PersonalMemory
from nyx.voice import Conversations


def test_unresolved_background_memory_is_quiet_and_keeps_original_input(tmp_path):
    from nyx.background_memory import BackgroundMemory

    conversations = Conversations(tmp_path)
    turn = conversations.begin("I keep this in the kitchen.", {})
    component = PersonalMemory(conversations, Encoder(), lambda *args: response())
    lane = BackgroundMemory(
        SimpleNamespace(conversations=conversations, personal_memory=lambda: component)
    )
    try:
        lane.submit(turn, []).result(timeout=1)
        context = lane.turn_context(turn)
        assert context["status"] == "noop"
        assert "?" not in context["answer"]
        assert lane.status(turn)["status"] == "noop"
        with conversations.connect() as db:
            assert (
                db.execute("SELECT transcript FROM turns WHERE id=?", (turn,)).fetchone()[0]
                == "I keep this in the kitchen."
            )
            assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 0
    finally:
        lane.close()


def test_background_memory_is_ordered_owned_and_durable(tmp_path):
    from nyx.background_memory import BackgroundMemory

    conversations = Conversations(tmp_path)
    started, release = threading.Event(), threading.Event()
    interpreted = []

    def interpret(payload, schema):
        current = payload["current_turn"]
        if current["turn_id"] == first:
            assert all(row["turn_id"] != second for row in payload["recent_user_turns"])
        interpreted.append(current["turn_id"])
        if len(interpreted) == 1:
            started.set()
            assert release.wait(3)
        return response([operation(current["turn_id"], current["text"], current["text"])])

    memory = PersonalMemory(conversations, Encoder(), interpret)
    lane = BackgroundMemory(
        SimpleNamespace(conversations=conversations, personal_memory=lambda: memory)
    )
    first = conversations.begin("My cup is on the table.", {})
    second = conversations.begin("My book is on the shelf.", {})
    try:
        pending = lane.submit(first, [])
        assert started.wait(1)
        conversations.finish(first, status="interrupted")
        following = lane.submit(second, [])
        assert lane.submit(first, []) is pending
        assert not following.done()
        assert lane.status(first)["status"] == "pending"
        with pytest.raises(TimeoutError):
            lane.wait(second, timeout=0.01)
        release.set()
        assert lane.wait(second, timeout=2) == []
        assert interpreted == [first, second]
        assert pending.result()["status"] == "saved"
        assert lane.status(first)["status"] == "saved"
    finally:
        release.set()
        lane.close()
    reopened = PersonalMemory(Conversations(tmp_path), Encoder(), lambda *args: response())
    assert len(reopened.recall("cup book")["matches"]) == 2


def test_background_memory_failure_is_visible_and_does_not_block_next_input(tmp_path):
    from nyx.background_memory import BackgroundMemory

    conversations = Conversations(tmp_path)
    first = conversations.begin("Remember this.", {})
    second = conversations.begin("Another detail.", {})

    def process(turn_id, **kwargs):
        if turn_id == first:
            raise RuntimeError("synthetic inference failure")
        return {"status": "noop"}

    lane = BackgroundMemory(
        SimpleNamespace(
            conversations=conversations, personal_memory=lambda: SimpleNamespace(process=process)
        )
    )
    try:
        lane.submit(first, [])
        lane.submit(second, [])
        assert lane.wait(second, timeout=2) == [first]
        assert lane.status(first) == {"status": "failed"}
        assert lane.status(second)["status"] == "noop"
        assert conversations.source_availability([first], input_only=True)[first]
    finally:
        lane.close()


def test_withdrawn_input_cannot_commit_a_late_background_save(tmp_path):
    from nyx.background_memory import BackgroundMemory

    conversations = Conversations(tmp_path)
    started, release = threading.Event(), threading.Event()
    turn = conversations.begin("The keys are in the drawer.", {})

    def interpret(payload, schema):
        started.set()
        assert release.wait(2)
        return response([operation(turn, payload["current_turn"]["text"], "Keys in drawer")])

    component = PersonalMemory(conversations, Encoder(), interpret)
    lane = BackgroundMemory(
        SimpleNamespace(conversations=conversations, personal_memory=lambda: component)
    )
    try:
        lane.submit(turn, [])
        assert started.wait(1)
        conversations.invalidate("transcript:" + turn)
        release.set()
        assert lane.wait(turn, timeout=2) == [turn]
        with conversations.connect() as db:
            assert db.execute("SELECT count(*) FROM memories").fetchone()[0] == 0
    finally:
        release.set()
        lane.close()


def test_early_candidates_do_not_wait_for_writer_and_revalidate_sources(tmp_path):
    from nyx.background_memory import BackgroundMemory

    conversations = Conversations(tmp_path)
    old = conversations.begin("I plan to keep my phone on the shelf.", {})
    component = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response(
            [
                operation(
                    old,
                    "I plan to keep my phone on the shelf.",
                    "Plans to keep phone on shelf",
                    kind="plan",
                )
            ]
        ),
    )
    component.process(old)
    component.interpret = lambda *args: response()
    started, release = threading.Event(), threading.Event()
    process = component.process

    def blocked(*args, **kwargs):
        started.set()
        assert release.wait(3)
        return process(*args, **kwargs)

    component.process = blocked
    lane = BackgroundMemory(
        SimpleNamespace(conversations=conversations, personal_memory=lambda: component)
    )
    new = conversations.begin("Where did I say I would keep it?", {})
    try:
        lane.submit(new, [])
        assert started.wait(1)
        task = lane.prefetch(new, "phone")
        assert task.result(timeout=1)["matches"][0]["turn_id"] == old
        context = lane.early_context(new)
        assert context["records"][0]["content"] == "Plans to keep phone on shelf"
        assert "embedding" not in str(context)
        assert context["records"][0]["quotes"][0]["text"] == "I plan to keep my phone on the shelf."
        conversations.invalidate("transcript:" + old)
        assert lane.early_context(new)["records"] == []
    finally:
        release.set()
        lane.close()


def test_early_candidates_recheck_corrections_and_historical_state(tmp_path):
    from datetime import UTC, datetime, timedelta

    from nyx.background_memory import BackgroundMemory

    conversations = Conversations(tmp_path)
    old = conversations.begin("My camera is in the bag.", {})
    component = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response([operation(old, "My camera is in the bag.", "Camera in bag")]),
    )
    old_id = component.process(old)["saved_ids"][0]
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    with conversations.connect() as db:
        db.execute(
            "UPDATE turns SET at=? WHERE id=?", ((cutoff - timedelta(hours=1)).isoformat(), old)
        )
    lane = BackgroundMemory(
        SimpleNamespace(conversations=conversations, personal_memory=lambda: component)
    )
    try:
        lane.prefetch("query", "camera").result(timeout=1)
        correction = conversations.begin("Correction: the camera is in the cupboard.", {})
        component.interpret = lambda *args: response(
            [
                operation(
                    correction,
                    "the camera is in the cupboard",
                    "Camera in cupboard",
                    operation="correct",
                    related_id=old_id,
                )
            ]
        )
        component.process(correction)
        assert lane.early_context("query")["records"] == []
        assert lane.early_context("query", as_of=cutoff.isoformat())["records"][0]["id"] == old_id
    finally:
        lane.close()


def test_early_lookup_bounds_inflight_reads_and_exposes_failure_without_empty_success(tmp_path):
    from nyx.background_memory import BackgroundMemory

    started, release = threading.Event(), threading.Event()
    lane = BackgroundMemory(SimpleNamespace(conversations=Conversations(tmp_path)))

    def unavailable(query):
        started.set()
        assert release.wait(2)
        raise RuntimeError("Synthetic lookup outage")

    lane._candidates = unavailable
    try:
        first = lane.prefetch("first", "one")
        assert started.wait(1)
        assert lane.prefetch("second", "two") is None
        assert lane.early_context("second")["status"] == "unavailable"
        release.set()
        with pytest.raises(RuntimeError):
            first.result(timeout=1)
        assert lane.early_context("first")["status"] == "failed"
    finally:
        release.set()
        lane.close()


@pytest.mark.parametrize("vision", ["resolved", "unclear", "failed"])
def test_visual_preparation_is_evidence_not_a_gate_on_supported_memories(tmp_path, vision):
    import json

    from PIL import Image

    from nyx.background_memory import BackgroundMemory
    from nyx.cloud import CloudError

    conversations = Conversations(tmp_path)
    text = "I will put this in my purse and keep my purse in the cupboard."
    turn = conversations.begin(text, {})
    frames = [{"image": Image.new("RGB", (10, 10)), "captured_at": "2026-11-19T05:53:45Z"}]
    payloads = []
    encoded = []

    class EvidenceEncoder(Encoder):
        def encode_text(self, text):
            encoded.append(text)
            return super().encode_text(text)

    def interpret(payload, schema):
        payloads.append(payload)
        assert payload["frames"] is frames
        assert "visual_available" not in payload and "needs_visual" not in schema["properties"]
        if vision == "resolved":
            assert payload["shown_object"]["object_description"] == "brass key"
            return response(
                [
                    operation(
                        turn,
                        text,
                        "Plans to put shown key in purse and purse in cupboard",
                        kind="plan",
                        grounding="visual",
                        visual_reference={"object_description": "brass key", "frame_index": 0},
                    )
                ]
            )
        assert "shown_object" not in payload
        return response(
            [
                operation(
                    turn,
                    "keep my purse in the cupboard",
                    "Plans to keep purse in cupboard",
                    kind="plan",
                )
            ]
        )

    def visual_reply(*args, **kwargs):
        if vision == "failed":
            raise CloudError("Provider unavailable")
        return json.dumps(
            {
                "targets": "One key" if vision == "resolved" else "Two unclear items",
                "target_count": 1 if vision == "resolved" else 2,
                "object_description": "brass key" if vision == "resolved" else "",
                "frame_index": 0 if vision == "resolved" else -1,
                "ambiguous": vision != "resolved",
            }
        )

    memory = PersonalMemory(conversations, EvidenceEncoder(), interpret)
    lane = BackgroundMemory(
        SimpleNamespace(
            conversations=conversations,
            personal_memory=lambda: memory,
            visual_verifier=lambda: SimpleNamespace(
                fingerprint={"model": "fixture-vision"}, generate_json=visual_reply
            ),
        )
    )
    try:
        result = lane.submit(turn, frames).result(timeout=1)
        assert result["status"] == "saved" and len(payloads) == 1
        record = memory.recall("purse", rank_all=False)["matches"][0]
        assert record["has_image"] == (vision == "resolved")
        assert "?" not in result["answer"]
        if vision == "resolved":
            assert "brass key" in encoded[0] and text in encoded[0]
            assert record["visual"]["captured_at"] == frames[0]["captured_at"]
        else:
            assert record["content"] == "Plans to keep purse in cupboard"
    finally:
        lane.close()
