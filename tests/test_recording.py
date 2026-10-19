from pathlib import Path

import pytest

from nyx.recording import CaptureJournal

START = "2026-10-19T10:00:00+00:00"
END = "2026-10-19T10:00:10+00:00"


def save_segment(journal, session_id, sequence=0, data=b"video", start=START, end=END):
    segment = journal.begin_segment(session_id, sequence, start, end, ".webm")
    path = journal.partial_path(segment["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return journal.finish_upload(segment["id"], len(data))


def test_capture_delivery_is_idempotent_and_preserves_original_metadata(tmp_path):
    journal = CaptureJournal(tmp_path, budget_bytes=1024)
    session = journal.start(START)
    first = save_segment(journal, session["id"])
    again = journal.begin_segment(session["id"], 0, START, END, ".webm")
    assert again["id"] == first["id"]
    assert again["state"] == "queued"
    assert len(journal.pending()) == 1
    assert (tmp_path / first["path"]).read_bytes() == b"video"
    assert journal.snapshot()["recorded_through"] == END
    assert journal.snapshot()["searchable_through"] is None
    with pytest.raises(ValueError, match="metadata"):
        journal.begin_segment(session["id"], 0, START, "2026-10-19T10:00:11Z", ".webm")


def test_capture_recovery_requeues_saved_work_and_exposes_lost_upload(tmp_path):
    journal = CaptureJournal(tmp_path)
    session = journal.start(START)
    saved = save_segment(journal, session["id"])
    journal.mark(saved["id"], "indexing")
    unfinished = journal.begin_segment(session["id"], 1, END, "2026-10-19T10:00:20Z", ".webm")
    journal.partial_path(unfinished["id"]).write_bytes(b"incomplete")
    reopened = CaptureJournal(tmp_path)
    reopened.recover()
    assert reopened.get_session(session["id"])["state"] == "interrupted"
    assert [row["id"] for row in reopened.pending()] == [saved["id"]]
    assert not reopened.partial_path(unfinished["id"]).exists()
    assert reopened.segment(unfinished["id"])["state"] == "failed"
    assert (tmp_path / saved["path"]).read_bytes() == b"video"
    assert reopened.snapshot()["searchable_through"] is None
    assert any("restart" in row["reason"].lower() for row in reopened.snapshot()["events"])


def test_capture_budget_counts_existing_video_without_deleting_it(tmp_path):
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    old = recordings / "existing.mp4"
    old.write_bytes(b"12345678")
    journal = CaptureJournal(tmp_path, budget_bytes=8)
    with pytest.raises(ValueError, match="budget"):
        journal.start(START)
    assert journal.video_bytes() == 8
    assert old.read_bytes() == b"12345678"


def test_capture_backlog_is_bounded_and_duplicate_delivery_uses_no_slot(tmp_path):
    journal = CaptureJournal(tmp_path, max_pending=1)
    session = journal.start(START)
    saved = save_segment(journal, session["id"])
    assert journal.begin_segment(session["id"], 0, START, END, ".webm")["id"] == saved["id"]
    with pytest.raises(ValueError, match="backlog"):
        journal.begin_segment(session["id"], 1, END, "2026-10-19T10:00:20Z", ".webm")
    journal.mark(saved["id"], "ready", last_sample_seconds=8)
    assert journal.snapshot()["searchable_through"] == "2026-10-19T10:00:08+00:00"


def test_capture_pause_resume_and_invalid_timestamps_are_explicit(tmp_path):
    journal = CaptureJournal(tmp_path)
    session = journal.start(START)
    with pytest.raises(ValueError, match="active"):
        journal.start(START)
    assert journal.transition(session["id"], "paused", END, "Paused by user")["state"] == "paused"
    assert (
        journal.transition(session["id"], "recording", END, "Resumed by user")["state"]
        == "recording"
    )
    journal.transition(session["id"], "stopped", END, "Stopped by user")
    with pytest.raises(ValueError, match="resume"):
        journal.transition(session["id"], "recording", END, "Resumed")
    for start, end in [("2026-10-19T10:00:00", END), (END, START)]:
        with pytest.raises(ValueError, match="time"):
            journal.begin_segment(session["id"], 0, start, end, ".webm")
    assert [row["reason"] for row in journal.snapshot()["events"]][:3] == [
        "Stopped by user",
        "Resumed by user",
        "Paused by user",
    ]


def test_staged_upload_survives_crash_before_rename(tmp_path):
    journal = CaptureJournal(tmp_path)
    session = journal.start(START)
    saved = save_segment(journal, session["id"])
    Path(tmp_path / saved["path"]).replace(journal.partial_path(saved["id"]))
    with journal.connection() as db:
        db.execute("UPDATE segments SET state = 'staged' WHERE id = ?", (saved["id"],))
    journal.recover()
    assert journal.pending()[0]["id"] == saved["id"]
    assert (tmp_path / saved["path"]).read_bytes() == b"video"


def test_interrupted_segment_does_not_extend_known_time_coverage(tmp_path):
    journal = CaptureJournal(tmp_path)
    session = journal.start(START)
    segment = journal.begin_segment(session["id"], 0, START, END, ".webm", timing_uncertain=True)
    journal.partial_path(segment["id"]).write_bytes(b"video")
    journal.finish_upload(segment["id"], 5)
    journal.mark(segment["id"], "ready", last_sample_seconds=2)
    status = journal.snapshot()
    assert status["recorded_through"] is None
    assert status["searchable_through"] is None
    assert status["timing_uncertain_count"] == 1


def test_storage_scan_tolerates_a_source_deleted_during_counting(tmp_path, monkeypatch):
    journal = CaptureJournal(tmp_path)
    folder = tmp_path / "recordings"
    folder.mkdir()
    removed, kept = folder / "removed.mp4", folder / "kept.mp4"
    removed.write_bytes(b"removed")
    kept.write_bytes(b"keep")
    original_stat = Path.stat
    seen = False

    def disappearing(path, *args, **kwargs):
        nonlocal seen
        if path == removed:
            if seen:
                removed.unlink(missing_ok=True)
            seen = True
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", disappearing)
    assert journal.video_bytes() == 4
