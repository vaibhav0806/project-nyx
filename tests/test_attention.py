from itertools import pairwise

from PIL import Image, ImageDraw


def test_activity_indexing_keeps_small_object_below_motion_threshold():
    from nyx.attention import select_activity_frames

    background = Image.new("RGB", (1280, 720), (100, 100, 100))
    object_frame = background.copy()
    ImageDraw.Draw(object_frame).rectangle((600, 350, 624, 362), fill=(210, 210, 210))
    frames = [(i / 10, object_frame if 30 <= i < 60 else background) for i in range(100)]
    selected = select_activity_frames(frames)
    assert any(3 <= at < 6 for at, _ in selected)
    assert all(any(row is original for original in frames) for row in selected)
    assert max(b[0] - a[0] for a, b in pairwise(selected)) <= 2.01


def test_index_coverage_floor_is_explicit_and_legacy_comparison_remains_available():
    import pytest

    from nyx.attention import select_activity_frames

    image = Image.new("RGB", (160, 96), "gray")
    frames = [(i / 10, image) for i in range(100)]
    assert [at for at, _ in select_activity_frames(frames, coverage_interval=None)] == [0]
    assert [at for at, _ in select_activity_frames(frames, coverage_interval=2)] == [0, 2, 4, 6, 8]
    for interval in [0, -1, float("nan"), float("inf")]:
        with pytest.raises(ValueError, match="coverage"):
            select_activity_frames(frames, coverage_interval=interval)


def test_static_frames_are_sparse_but_keep_periodic_coverage():
    from nyx.attention import select_frames

    image = Image.new("RGB", (160, 90), "gray")
    selected = select_frames([(float(t), image) for t in range(0, 92, 2)])
    assert [row[0] for row in selected] == [0, 30, 60, 90]


def test_small_changed_region_keeps_before_change_and_settled_scene():
    from nyx.attention import select_frames

    quiet = Image.new("RGB", (160, 90), "gray")
    changed = quiet.copy()
    ImageDraw.Draw(changed).rectangle((70, 40, 85, 50), fill="white")
    frames = [(0, quiet), (2, quiet), (4, quiet), (6, changed), (8, changed), (10, changed)]
    selected = select_frames(frames)
    times = [row[0] for row in selected]
    assert 4 in times  # The scene immediately before the change.
    assert 6 in times
    assert 8 in times  # Settled scene after activity.
    assert 10 not in times


def test_a_gap_resets_change_comparison_instead_of_claiming_continuity():
    from nyx.attention import ChangeDetector

    detector = ChangeDetector()
    image = Image.new("RGB", (160, 90), "gray")
    assert detector.observe(image, 0)["reason"] == "initial"
    assert detector.observe(image, 1)["selected"] is False
    assert detector.observe(image, 40)["reason"] == "gap"


def test_adaptive_indexing_preserves_sources_and_records_selection_policy(tmp_path, monkeypatch):
    from test_nyx import ColorEncoder

    from nyx.memory import Store
    from nyx.retrieval import index_video

    source = tmp_path / "source.mp4"
    source.write_bytes(b"frame decoding is exercised separately")

    def frames(video, destination, interval):
        assert interval == 0.1
        destination.mkdir(parents=True)
        result = []
        for tick in range(600):
            offset = tick / 10
            path = destination / f"{tick:06d}.jpg"
            Image.new("RGB", (160, 90), "gray").save(path)
            result.append((float(offset), path))
        return result

    monkeypatch.setattr("nyx.retrieval.extract_frames", frames)
    store = Store(tmp_path / "index", ColorEncoder.fingerprint, 3)
    result = index_video(source, store, ColorEncoder(), adaptive=True)
    assert result["frame_count"] == 30
    assert result["decoded_samples"] == 600
    assert (
        store.video(result["video_id"])["sampling_policy"]
        == "activity-v2/scan=0.1s/0.5s-persistence/coverage=2s"
    )
    assert len(list((store.root / "frames").rglob("*.jpg"))) == 30
    assert (
        store.root / "recordings" / f"{result['video_id']}.mp4"
    ).read_bytes() == source.read_bytes()


def test_real_video_flash_is_skipped_but_persistent_placement_keeps_actual_offsets(tmp_path):
    import subprocess

    from test_nyx import ColorEncoder

    from nyx.memory import Store
    from nyx.retrieval import index_video

    inputs = tmp_path / "input"
    inputs.mkdir()
    for tick in range(60):
        image = Image.new("RGB", (160, 96), "gray")
        if tick in [10, 11] or tick >= 30:
            left = 30 if tick < 30 else 90
            ImageDraw.Draw(image).rectangle((left, 35, left + 18, 58), fill="white")
        image.save(inputs / f"{tick:03d}.png")
    source = tmp_path / "temporal.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-framerate",
            "20",
            "-i",
            str(inputs / "%03d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
    )
    store = Store(tmp_path / "data", ColorEncoder.fingerprint, 3)
    output = index_video(source, store, ColorEncoder(), adaptive=True)
    with store.connection() as db:
        offsets = [
            row[0]
            for row in db.execute("SELECT offset_seconds FROM frames ORDER BY offset_seconds")
        ]
    assert output["decoded_samples"] > 15
    assert not any(0.5 <= at < 0.6 for at in offsets)
    assert any(1.2 <= at < 1.5 for at in offsets)
    assert any(1.5 <= at <= 2.2 for at in offsets)
    assert any(2.2 <= at <= 2.5 for at in offsets)
    assert len(offsets) <= 6
    saved = store.root / store.video(output["video_id"])["path"]
    assert saved.read_bytes() == source.read_bytes()
