import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from nyx.context import attach_statements, playback_window, transcript_candidates
from nyx.recording import CaptureJournal
from nyx.voice import Conversations, spoken_answer


def test_attached_transcript_sources_are_retained_and_late_deletion_is_rejected(tmp_path):
    import pytest

    conversations = Conversations(tmp_path)
    claim = conversations.begin("My phone is on the table", {})
    conversations.finish(claim, sources=["spoken-video"])
    model = SimpleNamespace(generate_json=lambda *a, **k: json.dumps({"statement_ids": [claim]}))

    def observation():
        return {
            "object_query": "phone",
            "evidence": {"id": 1, "video_id": "visual-video"},
            "answer": "A sighting.",
        }

    result = attach_statements(observation(), conversations, model, object())
    assert result["sources"] == ["spoken-video", f"transcript:{claim}"]

    def deleted(*args, **kwargs):
        conversations.invalidate("spoken-video")
        return json.dumps({"statement_ids": [claim]})

    with pytest.raises(ValueError, match="available|changed"):
        attach_statements(
            observation(), conversations, SimpleNamespace(generate_json=deleted), object()
        )


def test_transcripts_search_beyond_recent_turns_and_keep_sources(tmp_path):
    c = Conversations(tmp_path)
    first = c.begin("I will put my glasses on the centre table.", {"mode": "agent"})
    c.finish(first, "Noted")
    for _ in range(35):
        c.begin("An unrelated question", {"mode": "chat"})
    candidates = transcript_candidates(c, "glasses", None)
    assert [r["id"] for r in candidates] == [first]
    result = {
        "kind": "history",
        "object_query": "glasses",
        "answer": "Possible visual match.",
        "evidence": {"observed_at": None},
    }
    v = SimpleNamespace(generate_json=lambda *args: json.dumps({"statement_ids": [first]}))
    attach_statements(result, c, v, object())
    assert "You said" in spoken_answer(result)
    assert "You said" in result["answer"] and "will put" in result["answer"]
    assert "not visual confirmation" not in result["answer"]


def test_nearby_pronouns_and_unknown_citations(tmp_path):
    c = Conversations(tmp_path)
    key = c.begin("I will put this on the table.", {"mode": "agent"})
    now = datetime.now(UTC).isoformat()
    assert key in [r["id"] for r in transcript_candidates(c, "spectacles", now)]
    assert not transcript_candidates(c, "spectacles", None)
    result = {
        "object_query": "spectacles",
        "answer": "Evidence only.",
        "evidence": {"observed_at": now},
    }
    v = SimpleNamespace(generate_json=lambda *args: '{"statement_ids":["invented"]}')
    attach_statements(result, c, v, object())
    assert result["answer"] == "Evidence only." and result["spoken_context"] == []


def test_playback_window_crosses_segments_and_excludes_other_sessions(tmp_path):
    c = CaptureJournal(tmp_path)
    start = datetime(2026, 10, 28, tzinfo=UTC)
    with c.connection() as db:
        db.execute(
            "INSERT INTO sessions VALUES ('a','stopped',?,?, 'test')",
            (start.isoformat(), start.isoformat()),
        )
        db.execute(
            "INSERT INTO sessions VALUES ('b','stopped',?,?, 'test')",
            (start.isoformat(), start.isoformat()),
        )
        for i in range(4):
            path = f"recordings/{i}.webm"
            (tmp_path / path).parent.mkdir(exist_ok=True)
            (tmp_path / path).write_bytes(b"fixture")
            a = start + timedelta(seconds=i * 10 if i < 3 else 10)
            db.execute(
                "INSERT INTO segments(id,session_id,sequence,recorded_at,ended_at,state,path,size,timing_uncertain) VALUES (?,?,?,?,?,'ready',?,7,0)",
                (
                    str(i),
                    "a" if i < 3 else "b",
                    i,
                    a.isoformat(),
                    (a + timedelta(seconds=10)).isoformat(),
                    path,
                ),
            )
    result = playback_window(c, "1", 0.123)
    assert len(result["parts"]) == 3
    assert abs(result["parts"][0]["start"] - 0.123) < 0.001
    assert abs(result["parts"][-1]["end"] - 0.123) < 0.001
    assert abs(sum(p["end"] - p["start"] for p in result["parts"]) - 20) < 0.001
    with c.connection() as db:
        db.execute("UPDATE segments SET timing_uncertain=1 WHERE id='0'")
    assert len(playback_window(c, "1", 0.123)["parts"]) == 2


def test_unknown_time_playback_stays_in_clip(tmp_path):
    result = playback_window(CaptureJournal(tmp_path), "imported", 2)
    assert result["parts"][0]["start"] == 0 and result["parts"][0]["end"] == 12


def test_question_only_history_skips_context_model_and_frame_decode(tmp_path):
    c = Conversations(tmp_path)
    c.begin("Hey Nyx, where is my phone?", {"mode": "agent"})
    c.begin("When did you see my phone?", {"mode": "agent"})
    result = {"object_query": "phone", "evidence": {"observed_at": None}, "answer": "Found."}

    def unexpected(*args):
        raise AssertionError("No frame decode or model call for question-only context")

    attach_statements(result, c, SimpleNamespace(generate_json=unexpected), unexpected)
    assert result["answer"] == "Found."
    mixed = c.begin("Where is my phone? I left it on the table.", {"mode": "agent"})
    assert [r["id"] for r in transcript_candidates(c, "phone", None)] == [mixed]
