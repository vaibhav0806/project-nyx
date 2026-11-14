import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def replay():
    script = Path(__file__).resolve().parents[1] / "experiments/companion/memory_replay.py"
    assert script.exists(), "Labeled replay harness is not implemented"
    spec = importlib.util.spec_from_file_location("memory_replay", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case():
    recipe = {
        "width": 1280,
        "height": 720,
        "background": 100,
        "foreground": 210,
        "box": [600, 350, 624, 362],
        "duration_seconds": 10,
        "visible_intervals": [[3, 6]],
    }
    return {
        "id": "small-object",
        "group": "episode-a",
        "split": "development",
        "source": {
            "kind": "synthetic",
            "sha256": hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest(),
            "captured_at": None,
            "recipe": recipe,
        },
        "replay_at": "2026-11-06T10:00:00+00:00",
        "duration_seconds": 10,
        "visible_intervals": [[3, 6]],
        "query": "Find the small object",
    }


def test_replay_keeps_unknown_capture_time_separate_from_simulated_clock(replay):
    manifest = {"version": 1, "cases": [case()]}
    before = copy.deepcopy(manifest)
    replay.validate_manifest(manifest)
    assert manifest == before
    assert manifest["cases"][0]["source"]["captured_at"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("duration_seconds", float("nan")),
        ("duration_seconds", 0),
        ("visible_intervals", [[-1, 4]]),
        ("visible_intervals", [[3, 11]]),
        ("visible_intervals", [[4, 3]]),
        ("replay_at", "2026-11-15T12:00:00"),
    ],
)
def test_bad_replay_labels_are_rejected(replay, field, value):
    row = case()
    row[field] = value
    with pytest.raises(ValueError):
        replay.validate_manifest({"version": 1, "cases": [row]})


def test_same_source_or_episode_cannot_leak_between_splits(replay):
    first = case()
    for same_field in ["source", "group"]:
        second = copy.deepcopy(first)
        second.update(id="other", group="episode-b", split="holdout")
        second["source"]["sha256"] = "b" * 64
        second[same_field] = first[same_field]
        with pytest.raises(ValueError, match="split"):
            replay.validate_manifest({"version": 1, "cases": [first, second]})


def test_event_retention_uses_half_open_source_intervals(replay):
    row = case()
    assert replay.score_selection(row, [0, 6, 8])["events_retained"] == 0
    assert replay.score_selection(row, [0, 4, 6])["events_retained"] == 1
    row["visible_intervals"] = []
    assert replay.score_selection(row, [0, 4])["event_recall"] is None


def test_sampling_comparison_runs_real_selector_and_counts_added_samples(replay):
    row = case()
    results = replay.compare_selectors(row)
    assert results["activity_only"]["events_retained"] == 0
    assert results["coverage_plus_activity"]["events_retained"] == 1
    assert (
        results["coverage_plus_activity"]["sample_count"] > results["activity_only"]["sample_count"]
    )


def test_development_run_does_not_evaluate_holdout_sources(replay, monkeypatch):
    manifest = replay.generated_manifest(10)
    seen = []
    actual = replay.compare_selectors

    def checked(row, root, interval):
        seen.append(row["split"])
        return actual(row, root, interval)

    monkeypatch.setattr(replay, "compare_selectors", checked)
    result = replay.run(manifest, Path("."), split="development")
    assert set(seen) == {"development"}
    assert len(result["cases"]) == 6


def test_source_recipe_tampering_is_rejected(replay):
    row = case()
    row["source"]["recipe"]["foreground"] = 255
    with pytest.raises(ValueError, match="digest"):
        replay.compare_selectors(row)


def test_permitted_frame_samples_are_hashed_and_scoped_to_manifest(replay, tmp_path):
    from PIL import Image

    image = tmp_path / "frame.png"
    Image.new("RGB", (32, 32), "gray").save(image)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    row = case()
    row["source"] = {
        "kind": "permitted_frames",
        "captured_at": None,
        "sha256": hashlib.sha256(f"0:{digest}\n".encode()).hexdigest(),
        "frames": [{"path": "frame.png", "offset_seconds": 0, "sha256": digest}],
    }
    assert replay.compare_selectors(row, tmp_path)["coverage_plus_activity"]["sample_count"] == 1
    image.write_bytes(b"changed input")
    with pytest.raises(ValueError, match="digest"):
        replay.compare_selectors(row, tmp_path)
    row["source"]["frames"][0]["path"] = "../elsewhere.png"
    with pytest.raises(ValueError, match="escapes"):
        replay.compare_selectors(row, tmp_path)
