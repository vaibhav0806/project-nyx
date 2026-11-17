import threading
from concurrent.futures import TimeoutError
from types import SimpleNamespace

import pytest
from test_personal_memory import Encoder, operation, response

from nyx.personal_memory import PersonalMemory
from nyx.voice import Conversations


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
