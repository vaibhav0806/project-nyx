from typing import ClassVar

import pytest

from nyx.verification import parse_judgment


def test_verifier_accepts_a_specific_visible_observation():
    result = parse_judgment(
        '{"visibility":"visible","location":"beside the laptop","description":"A pair of glasses is visible.","matching_count":1,"ambiguous":false}'
    )
    assert result["visibility"] == "visible"
    assert result["location"] == "beside the laptop"


@pytest.mark.parametrize(
    "raw",
    [
        "yes definitely",
        '{"visibility":"visible","location":"visible location or empty string","description":"two remote controls","ambiguous":false}',
        '{"visibility":"visible","location":"","description":"A remote","ambiguous":false}',
        '{"visibility":"visible","location":"left of the cat","description":"short observation","ambiguous":false}',
        '{"visibility":"visible","location":42}',
        '{"visibility":"visible","location":"beside laptop","description":"two pairs","ambiguous":true}',
        '{"visibility":"visible","location":"left","description":"glasses","ambiguous":"false"}',
    ],
)
def test_unparseable_or_ambiguous_model_output_cannot_confirm_presence(raw):
    assert parse_judgment(raw)["visibility"] == "uncertain"


def test_negative_model_output_cannot_attach_a_location():
    result = parse_judgment(
        '{"visibility":"not_visible","location":"in a drawer","description":"Not visible.","matching_count":0,"ambiguous":false}'
    )
    assert result["location"] is None
    assert result["visibility"] == "not_visible"


def test_history_checks_newest_frames_before_similarity_and_returns_evidence(tmp_path, video):
    import numpy as np
    from test_nyx import ColorEncoder

    from nyx.answers import history_steps
    from nyx.memory import Store
    from nyx.retrieval import index_video

    store = Store(tmp_path / "memory", ColorEncoder.fingerprint, 3)
    older = index_video(video, store, ColorEncoder(), recorded_at="2026-10-19T10:00:00Z")
    newer = index_video(video, store, ColorEncoder(), recorded_at="2026-10-19T11:00:00Z")
    with store.connection() as db:
        db.execute(
            "DELETE FROM frames WHERE video_id = ? AND offset_seconds > 0", (newer["video_id"],)
        )

    class ColorVerifier:
        fingerprint: ClassVar[dict] = {"model": "test-color-verifier"}

        def inspect(self, image, object_query):
            assert object_query == "green"
            visible = np.asarray(image).mean(axis=(0, 1))[1] > 100
            return {
                "visibility": "visible" if visible else "not_visible",
                "location": "center" if visible else None,
                "description": "Color observed",
            }

    steps = history_steps("green", store, ColorEncoder(), lambda: ColorVerifier())
    while True:
        try:
            next(steps)
        except StopIteration as done:
            answer = done.value
            break
    assert [row["video_id"] for row in answer["checked"]] == [newer["video_id"], older["video_id"]]
    assert answer["evidence"]["observed_at"] == "2026-10-19T10:00:02+00:00"
    assert answer["status"] == "seen"
    assert "still" in answer["answer"]
    assert answer["scope"]["candidate_limit"] == 17


def test_no_dated_history_does_not_load_verifier_or_invent_absence(tmp_path):
    from test_nyx import ColorEncoder

    from nyx.answers import history_steps
    from nyx.memory import Store

    store = Store(tmp_path, ColorEncoder.fingerprint, 3)
    steps = history_steps(
        "green", store, ColorEncoder(), lambda: pytest.fail("No evidence to verify")
    )
    with pytest.raises(StopIteration) as done:
        next(steps)
    assert done.value.value["status"] == "uncertain"
    assert done.value.value["evidence"] is None
    assert "not prove" in done.value.value["answer"]


pytest_plugins = ["test_nyx"]


def test_latest_search_can_reach_an_older_candidate_beyond_the_recent_scan(tmp_path, video):
    import numpy as np
    from test_nyx import ColorEncoder

    from nyx.answers import history_steps
    from nyx.memory import Store
    from nyx.retrieval import index_video

    store = Store(tmp_path / "history", ColorEncoder.fingerprint, 3)
    older = index_video(video, store, ColorEncoder(), recorded_at="2026-10-19T10:00:00Z")
    for second in range(13):
        newer = index_video(
            video, store, ColorEncoder(), recorded_at=f"2026-10-19T11:00:{second:02d}Z"
        )
        with store.connection() as db:
            db.execute(
                "DELETE FROM frames WHERE video_id = ? AND offset_seconds > 0", (newer["video_id"],)
            )

    class ColorVerifier:
        fingerprint: ClassVar[dict] = {"model": "color-test"}

        def inspect(self, image, object_query):
            visible = np.asarray(image).mean(axis=(0, 1))[1] > 100
            return {
                "visibility": "visible" if visible else "not_visible",
                "location": "center" if visible else None,
                "description": "Color check",
            }

    steps = history_steps("green", store, ColorEncoder(), ColorVerifier)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            result = done.value
            break
    assert result["evidence"] is not None
    assert result["evidence"]["video_id"] == older["video_id"]
    assert result["scope"]["fallback_used"] is True


def test_valid_ambiguity_is_preserved_without_a_location_claim():
    result = parse_judgment(
        '{"visibility":"visible","location":"left","description":"Two matches","matching_count":2,"ambiguous":true}'
    )
    assert result["visibility"] == "uncertain"
    assert result["ambiguous"] is True
    assert result["location"] is None


def test_ambiguous_history_stops_before_an_older_match(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from nyx.answers import history_steps

    candidates = [
        {"id": str(i), "video_id": "video", "video_path": "fixture.mp4", "offset_seconds": i}
        for i in range(2)
    ]
    monkeypatch.setattr("nyx.answers.search", lambda *args, **kwargs: candidates)
    monkeypatch.setattr("nyx.answers.frame_image", lambda *args: object())
    calls = []

    def inspect(image, query):
        calls.append(query)
        assert len(calls) == 1, "Must clarify before choosing another historical match"
        return {"visibility": "uncertain", "ambiguous": True}

    verifier = SimpleNamespace(inspect=inspect, fingerprint={"model": "fixture"})
    steps = history_steps(
        "mug", SimpleNamespace(root=tmp_path), None, lambda: verifier, mode="relevance"
    )
    while True:
        try:
            next(steps)
        except StopIteration as done:
            result = done.value
            break
    assert result["status"] == "clarify"
    assert result["evidence"] is None
    assert len(result["checked"]) == 1
    assert "Which one" in result["answer"]


@pytest.mark.parametrize("count", [0, 2, True, "1", None])
def test_visible_requires_exactly_one_reported_match(count):
    import json

    result = parse_judgment(
        json.dumps(
            {
                "visibility": "visible",
                "location": "left and right",
                "description": "Candidates",
                "matching_count": count,
                "ambiguous": False,
            }
        )
    )
    assert result["visibility"] == "uncertain"
    assert result["location"] is None
    if count == 2:
        assert result["ambiguous"] is True
