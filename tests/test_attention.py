from PIL import Image, ImageDraw


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
        destination.mkdir(parents=True)
        result = []
        for offset in range(0, 60, 2):
            path = destination / f"{offset}.jpg"
            Image.new("RGB", (160, 90), "gray").save(path)
            result.append((float(offset), path))
        return result

    monkeypatch.setattr("nyx.retrieval.extract_frames", frames)
    store = Store(tmp_path / "index", ColorEncoder.fingerprint, 3)
    result = index_video(source, store, ColorEncoder(), adaptive=True)
    assert result["frame_count"] == 2
    assert result["decoded_samples"] == 30
    assert store.video(result["video_id"])["sampling_policy"] == "change-v1/2s/30s"
    assert len(list((store.root / "frames").rglob("*.jpg"))) == 2
    assert (
        store.root / "recordings" / f"{result['video_id']}.mp4"
    ).read_bytes() == source.read_bytes()
