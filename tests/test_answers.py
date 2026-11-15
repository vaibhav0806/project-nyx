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
    assert answer["status"] == "candidate"
    assert "current location" in answer["answer"]
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


def test_source_balanced_pool_reaches_verified_older_scene_beyond_dense_distractors(
    tmp_path, video
):
    import numpy as np
    from test_agent import complete
    from test_nyx import ColorEncoder

    from nyx.answers import history_steps
    from nyx.memory import Store
    from nyx.retrieval import index_video

    store = Store(tmp_path / "history", ColorEncoder.fingerprint, 3)
    older = index_video(video, store, ColorEncoder(), recorded_at="2026-11-05T12:00:00Z")
    newer = index_video(video, store, ColorEncoder(), recorded_at="2026-11-06T12:00:00Z")
    with store.connection() as db:
        thumbnail = db.execute(
            "SELECT thumbnail FROM frames WHERE video_id=? LIMIT 1", (newer["video_id"],)
        ).fetchone()[0]
        db.execute("DELETE FROM frames WHERE video_id=?", (newer["video_id"],))
        db.execute("DELETE FROM frames WHERE video_id=? AND offset_seconds=0", (older["video_id"],))
    store.add_frames(newer["video_id"], [(i / 100, thumbnail) for i in range(80)], [[0, 1, 0]] * 80)
    # Controlled inference error: the correct older scene has a lower nomination score.
    from nyx.memory import _vector

    with store.connection() as db:
        db.execute(
            "UPDATE frames SET embedding=? WHERE video_id=?",
            (_vector([0.4, 0.9, 0], 3), older["video_id"]),
        )

    class Verifier:
        fingerprint: ClassVar = {"model": "color-check"}

        def inspect(self, image, query):
            visible = np.asarray(image).mean(axis=(0, 1))[1] > 100
            return {
                "visibility": "visible" if visible else "not_visible",
                "location": "center" if visible else None,
                "description": "Generated color fixture",
            }

    flat = complete(
        history_steps(
            "green", store, ColorEncoder(), Verifier, semantic_latest=True, source_balanced=False
        )
    )
    assert flat["evidence"] is None
    balanced = complete(
        history_steps(
            "green", store, ColorEncoder(), Verifier, semantic_latest=True, source_balanced=True
        )
    )
    assert balanced["evidence"]["video_id"] == older["video_id"]
    assert balanced["evidence"]["observed_at"] == "2026-11-05T12:00:02+00:00"
    assert balanced["evidence"]["media_url"].endswith(older["video_id"] + "/media")


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


@pytest.mark.parametrize("ambiguous_first", [False, True])
@pytest.mark.parametrize("confirmation_requests", [0, 1])
def test_batch_keeps_candidate_order_and_stops_after_first_decisive_batch(
    tmp_path, video, ambiguous_first, confirmation_requests
):
    from test_nyx import ColorEncoder

    from nyx.answers import history_steps
    from nyx.memory import Store
    from nyx.retrieval import index_video

    store = Store(tmp_path, ColorEncoder.fingerprint, 3)
    index_video(video, store, ColorEncoder(), recorded_at="2026-10-19T10:00:00Z")

    class BatchVerifier:
        fingerprint: ClassVar[dict] = {"model": "test"}
        calls = 0

        def inspect_batch(self, images, query):
            self.calls += 1
            assert self.calls == 1
            return [
                {
                    "visibility": "uncertain" if i == 0 and ambiguous_first else "visible",
                    "ambiguous": i == 0 and ambiguous_first,
                    "location": "desk",
                    "confirmation_requests": confirmation_requests,
                }
                for i in range(len(images))
            ]

    verifier = BatchVerifier()
    steps = history_steps("green", store, ColorEncoder(), lambda: verifier)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            result = done.value
            break
    assert result["timings"]["vision_requests"] == len(result["checked"]) * (
        1 + confirmation_requests
    )
    if ambiguous_first:
        assert result["status"] == "clarify" and result["evidence"] is None
    else:
        assert result["evidence"]["id"] == result["checked"][0]["id"]


def test_diverse_history_candidates_spread_moments_and_keep_sparse_neighbors():
    from nyx.answers import diverse_candidates

    rows = [
        {"id": i, "video_id": "clip", "offset_seconds": offset}
        for i, offset in enumerate([0, 1, 2, 8, 16])
    ]
    assert [r["offset_seconds"] for r in diverse_candidates(rows, 3)] == [0, 8, 16]
    assert [r["offset_seconds"] for r in diverse_candidates(rows[:3], 3)] == [0, 1, 2]
    other = {"id": 6, "video_id": "other", "offset_seconds": 0}
    assert diverse_candidates([rows[0], other], 2) == [rows[0], other]


def test_diversity_crosses_clip_boundaries_only_with_known_capture_continuity():
    from datetime import UTC, datetime, timedelta

    from nyx.answers import diverse_candidates

    at = datetime(2026, 11, 15, tzinfo=UTC)
    rows = [
        {
            "id": i,
            "video_id": f"clip-{i}",
            "offset_seconds": 0,
            "capture_session": "session-a",
            "observed_at": (at + timedelta(seconds=i)).isoformat(),
        }
        for i in [0, 1, 2, 8, 16]
    ]
    assert [r["id"] for r in diverse_candidates(rows, 3)] == [0, 8, 16]
    unrelated = {**rows[1], "capture_session": "session-b"}
    assert diverse_candidates([rows[0], unrelated], 2) == [rows[0], unrelated]
    unknown = {**rows[1], "observed_at": None}
    assert diverse_candidates([rows[0], unknown], 2) == [rows[0], unknown]


def test_reference_nomination_is_explicit_and_does_not_replace_verification(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from nyx.answers import history_steps

    seen = []
    monkeypatch.setattr("nyx.answers.search", lambda *a, **kw: seen.append(kw) or [])
    reference = object()
    for enabled in [False, True]:
        steps = history_steps(
            "keys",
            SimpleNamespace(root=tmp_path),
            None,
            lambda: pytest.fail("No candidate to verify"),
            reference_image=reference,
            reference_candidates=enabled,
        )
        while True:
            try:
                next(steps)
            except StopIteration:
                break
        assert seen[-1].get("reference_image") is (reference if enabled else None)


def test_history_checks_reference_image_instead_of_category_only(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from nyx.answers import history_steps

    candidate = {
        "id": 1,
        "video_id": "video",
        "video_path": "fixture.mp4",
        "offset_seconds": 0,
        "observed_at": "2026-10-31T12:00:00Z",
    }
    monkeypatch.setattr("nyx.answers.search", lambda *a, **k: [candidate])
    image, reference = object(), object()
    monkeypatch.setattr("nyx.answers.frame_image", lambda *a: image)
    seen = []

    class Verifier:
        fingerprint = None

        def inspect_reference(self, current, shown, query):
            seen.append((current, shown, query))
            return {"visibility": "not_visible", "location": "", "description": "Different object"}

        def inspect(self, *args):
            raise AssertionError("Category-only verification must not replace comparison")

    steps = history_steps(
        "phone",
        SimpleNamespace(root=tmp_path),
        None,
        Verifier,
        mode="relevance",
        reference_image=reference,
    )
    while True:
        try:
            next(steps)
        except StopIteration as done:
            result = done.value
            break
    assert seen == [(image, reference, "phone")]
    assert result["evidence"] is None
