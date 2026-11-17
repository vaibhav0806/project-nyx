from datetime import UTC, datetime, timedelta

from nyx.context import playback_window
from nyx.recording import CaptureJournal


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
