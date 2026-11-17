"""Bounded playback around a sighting, preserving source capture clocks."""

from datetime import timedelta

from nyx.memory import aware_time


def playback_window(capture, video_id, offset, radius=10):
    try:
        anchor = capture.segment(video_id)
    except ValueError:
        anchor = None
    if not anchor or anchor["timing_uncertain"]:
        return {
            "parts": [
                {
                    "media_url": f"/api/videos/{video_id}/media",
                    "start": max(0, offset - radius),
                    "end": offset + radius,
                }
            ],
            "note": "Context is limited to this clip; adjacent capture times are unavailable.",
        }
    at = aware_time(anchor["recorded_at"]) + timedelta(seconds=offset)
    start, end = at - timedelta(seconds=radius), at + timedelta(seconds=radius)
    with capture.connection() as db:
        rows = db.execute(
            "SELECT * FROM segments WHERE session_id=? AND size>0 AND state NOT IN ('deleted','deleting') AND timing_uncertain=0 ORDER BY sequence",
            (anchor["session_id"],),
        ).fetchall()
    parts = []
    for row in rows:
        a, b = aware_time(row["recorded_at"]), aware_time(row["ended_at"])
        if b <= start or a >= end or not (capture.root / row["path"]).is_file():
            continue
        parts.append(
            {
                "media_url": f"/api/capture/segments/{row['id']}/media",
                "start": max(0, (start - a).total_seconds()),
                "end": min((b - a).total_seconds(), (end - a).total_seconds()),
                "at": max(start, a).isoformat(),
            }
        )
    return {
        "parts": parts,
        "matched_at": at.isoformat(),
        "note": "Up to 10 seconds before and after the match. Missing or interrupted footage is not reconstructed.",
    }
