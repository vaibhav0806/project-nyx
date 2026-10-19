import subprocess
from typing import ClassVar

import numpy as np
import pytest
from PIL import Image

from nyx.capture import extract_frames
from nyx.memory import Store
from nyx.retrieval import index_video, search


class ColorEncoder:
    fingerprint: ClassVar[dict] = {
        "model": "test-rgb",
        "revision": "1",
        "preprocessing": "mean-rgb",
    }
    dimensions = 3
    device = "cpu"

    def encode_images(self, images):
        colors = np.array([np.asarray(image).mean(axis=(0, 1)) for image in images])
        return (colors / np.linalg.norm(colors, axis=1, keepdims=True)).astype(np.float32)

    def encode_text(self, query):
        return {"red": np.array([1, 0, 0]), "green": np.array([0, 1, 0])}[query]


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "data", ColorEncoder.fingerprint, 3)


def test_ranking_preserves_source_and_unknown_capture_time_after_reopen(store):
    video_id = store.add_video("desk.mp4", "recordings/desk.mp4", None, 2)
    store.add_frames(video_id, [(0, "frames/0.jpg"), (2.5, "frames/1.jpg")], [[0, 1, 0], [1, 0, 0]])
    store.finish_video(video_id)
    reopened = Store(store.root, ColorEncoder.fingerprint, 3)
    results = reopened.search([1, 0, 0], limit=2)
    assert [result["offset_seconds"] for result in results] == [2.5, 0.0]
    assert results[0]["video_id"] == video_id
    assert results[0]["name"] == "desk.mp4"
    assert results[0]["recorded_at"] is None
    assert results[0]["similarity"] == pytest.approx(1.0)
    assert results[0]["verified"] is False


def test_indexing_and_failed_videos_are_excluded(store):
    video_id = store.add_video("partial.mp4", "recordings/partial.mp4", None, 2)
    store.add_frames(video_id, [(0, "frames/0.jpg")], [[1, 0, 0]])
    assert store.search([1, 0, 0]) == []
    store.fail_video(video_id, "encoding failed")
    assert store.search([1, 0, 0]) == []
    assert store.list_videos()[0]["frame_count"] == 0
    assert store.list_videos()[0]["status"] == "failed"


def test_encoder_revision_and_preprocessing_cannot_be_mixed(store):
    for field in ["model", "revision", "preprocessing"]:
        changed = {**ColorEncoder.fingerprint, field: "changed"}
        with pytest.raises(ValueError, match="different encoder"):
            Store(store.root, changed, 3)
    with pytest.raises(ValueError, match="different encoder"):
        Store(store.root, ColorEncoder.fingerprint, 4)


def test_invalid_vectors_do_not_partially_insert_a_batch(store):
    video_id = store.add_video("desk.mp4", "desk.mp4", None, 2)
    with pytest.raises(ValueError, match="vector"):
        store.add_frames(video_id, [(0, "0.jpg"), (1, "1.jpg")], [[1, 0, 0], [0, 0, 0]])
    store.finish_video(video_id)
    assert store.search([1, 0, 0]) == []
    for vector in [[1, 0], [float("nan"), 0, 1], [0, 0, 0]]:
        with pytest.raises(ValueError, match="vector"):
            store.search(vector)


def test_time_filters_apply_before_ranking(store):
    video_id = store.add_video("desk.mp4", "desk.mp4", None, 2)
    store.add_frames(video_id, [(0, "0.jpg"), (4, "1.jpg")], [[1, 0, 0], [0.8, 0.6, 0]])
    store.finish_video(video_id)
    results = store.search([1, 0, 0], start=3, end=5)
    assert [result["offset_seconds"] for result in results] == [4.0]
    assert store.search([1, 0, 0], video_id="missing") == []


@pytest.fixture
def video(tmp_path):
    images = tmp_path / "source"
    images.mkdir()
    for number, color in enumerate(["red", "red", "lime", "lime"]):
        Image.new("RGB", (64, 64), color).save(images / f"{number:03}.png")
    path = tmp_path / "colors.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-framerate",
            "1",
            "-i",
            str(images / "%03d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    return path


def test_frame_sampling_preserves_actual_decoded_offsets(tmp_path, video):
    frames = extract_frames(video, tmp_path / "frames", interval=1.5)
    assert [offset for offset, _ in frames] == [0.0, 2.0]
    with Image.open(frames[1][1]) as image:
        assert np.asarray(image)[:, :, 1].mean() > 200


def test_index_copies_source_and_search_finds_later_scene(store, video):
    summary = index_video(video, store, ColorEncoder(), interval=2, batch_size=1)
    results = search("green", store, ColorEncoder(), limit=2)
    assert results[0]["offset_seconds"] == 2.0
    assert results[0]["video_id"] == summary["video_id"]
    assert summary["frame_count"] == 2
    assert (store.root / results[0]["thumbnail"]).exists()
    assert (store.root / results[0]["video_path"]).read_bytes() == video.read_bytes()


def test_encoding_failure_cleans_up_partial_evidence(store, video):
    class BrokenEncoder(ColorEncoder):
        def encode_images(self, images):
            raise RuntimeError("model failed")

    with pytest.raises(RuntimeError, match="model failed"):
        index_video(video, store, BrokenEncoder())
    record = store.list_videos()[0]
    assert record["status"] == "failed"
    assert record["frame_count"] == 0
    assert not (store.root / record["path"]).exists()
    assert list((store.root / "frames").glob("*")) == []


def test_bad_video_is_reported_without_searchable_results(store, tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(ValueError, match="video"):
        index_video(bad, store, ColorEncoder())
    assert store.search([1, 0, 0]) == []
    assert store.list_videos()[0]["status"] == "failed"


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
def test_invalid_sampling_is_rejected_without_importing(store, video, interval):
    with pytest.raises(ValueError, match="interval"):
        index_video(video, store, ColorEncoder(), interval=interval)
    assert store.list_videos() == []


def test_blank_query_rejected(store):
    with pytest.raises(ValueError, match="query"):
        search("  ", store, ColorEncoder())


def test_candidate_gallery_escapes_query_and_preserves_clip_links(store, tmp_path):
    from nyx.report import write_gallery

    (store.root / "frames").mkdir()
    Image.new("RGB", (8, 8), "white").save(store.root / "frames/one.jpg")
    result = {
        "name": "<script>video</script>.mp4",
        "offset_seconds": 2.5,
        "thumbnail": "frames/one.jpg",
        "video_path": "recordings/one.mp4",
        "similarity": 0.42,
        "recorded_at": None,
        "verified": False,
    }
    destination = tmp_path / "report.html"
    write_gallery("<script>alert(1)</script>", [result], store.root, destination)
    html = destination.read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "00:02.500" in html
    assert "#t=2.5" in html
    assert "candidate" in html.lower()
    assert "Capture time unknown" in html


def test_benchmark_original_scene_labels_match_the_source_images(tmp_path):
    import importlib.util
    from pathlib import Path

    script = Path(__file__).parents[1] / "experiments/image-text-retrieval/run.py"
    spec = importlib.util.spec_from_file_location("retrieval_benchmark", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sources = tmp_path / "inputs"
    sources.mkdir()
    for name, color in [
        ("cats", "red"),
        ("coffee", "lime"),
        ("camera", "blue"),
        ("parrots", "yellow"),
    ]:
        Image.new("RGB", (640, 480), color).save(sources / f"{name}.img", format="PNG")
    output = tmp_path / "output"
    output.mkdir()
    _, labels = module.prepare(sources, output, download=False)
    assert [label["scene"] for label in labels[:4]] == [
        "cats_original",
        "coffee_original",
        "camera_original",
        "parrots_original",
    ]
    colors = []
    for number in range(4):
        with Image.open(output / "input_frames" / f"{number:03}.png") as frame:
            colors.append(frame.getpixel((480, 270)))
    assert colors == [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]


@pytest.mark.parametrize(
    "arguments",
    [
        ["index", "missing.mp4", "--interval", "0"],
        ["index", "missing.mp4", "--batch-size", "0"],
        ["search", "", "--limit", "0"],
    ],
)
def test_cli_rejects_invalid_bounds_before_loading_a_model(arguments):
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "nyx.cli", *arguments], capture_output=True, text=True, check=False
    )
    assert result.returncode == 2
    assert "must be positive" in result.stderr


@pytest.fixture
def benchmark():
    import importlib.util
    from pathlib import Path

    script = Path(__file__).parents[1] / "experiments/image-text-retrieval/run.py"
    spec = importlib.util.spec_from_file_location("retrieval_benchmark", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_spatial_views_preserve_edges_and_overlap_on_odd_sized_images(benchmark):
    image = Image.fromarray(np.arange(11 * 7 * 3, dtype=np.uint8).reshape(7, 11, 3))
    views = benchmark.spatial_views(image)
    assert [box for box, _ in views] == [
        (0, 0, 11, 7),
        (0, 0, 8, 5),
        (3, 0, 11, 5),
        (0, 2, 8, 7),
        (3, 2, 11, 7),
    ]
    assert views[0][1].tobytes() == image.tobytes()
    assert views[-1][1].getpixel((7, 4)) == image.getpixel((10, 6))
    for _, crop in views[1:]:
        assert crop.size == (8, 5)


def test_multiview_ranking_returns_each_frame_once_and_keeps_ties_stable(benchmark):
    features = np.array(
        [
            [[0, 1], [1, 0], [1, 0]],
            [[1, 0], [1, 0], [0, 1]],
            [[0.6, 0.8], [0, 1], [0, 1]],
        ]
    )
    results = benchmark.rank_frames(np.array([1, 0]), features)
    assert [row["frame_index"] for row in results] == [0, 1, 2]
    assert [row["view_index"] for row in results] == [1, 0, 0]
    assert [row["similarity"] for row in results] == pytest.approx([1, 1, 0.6])


def test_occurrence_scoring_counts_misses_beyond_top_k_and_latest_label(benchmark):
    labels = [
        {"scene": name, "objects": ["remote"] if name != "empty" else [], "start": start}
        for start, name in enumerate(["first", "empty", "second", "third", "small_latest"])
    ]
    ranked = [labels[index] for index in [0, 2, 1, 3, 4]]
    scores = benchmark.score_occurrences(ranked, "remote", labels)
    assert scores["relevant_scene_count"] == 4
    assert scores["recall_at_1"] == 0.25
    assert scores["recall_at_3"] == 0.5
    assert scores["recall_at_5"] == 1
    assert scores["average_precision"] == pytest.approx((1 + 1 + 0.75 + 0.8) / 4)
    assert scores["latest_labelled_scene_rank"] == 5
    assert scores["relevant_scene_ranks"][-1] == {"scene": "small_latest", "rank": 5}
    absent = benchmark.score_occurrences(ranked, None, labels)
    assert absent["relevant_scene_count"] == 0
    assert absent["recall_at_3"] is None
    assert absent["average_precision"] is None
    assert absent["latest_labelled_scene_rank"] is None
    assert absent["relevant_scene_ranks"] == []
