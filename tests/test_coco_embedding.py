import importlib.util
from pathlib import Path

import pytest


def load_experiment(monkeypatch):
    script = Path(__file__).resolve().parents[1] / "experiments/companion/coco_embedding.py"
    monkeypatch.syspath_prepend(str(script.parent))
    spec = importlib.util.spec_from_file_location("coco_embedding", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def data():
    images = []
    annotations = []
    for category in [44, 47, 75, 77]:
        for n in range(2):
            identifier = category * 10 + n
            images.append(
                {
                    "id": identifier,
                    "width": 100,
                    "height": 100,
                    "license": 4,
                    "file_name": f"{identifier:012}.jpg",
                    "flickr_url": "https://flickr.com/example",
                }
            )
            annotations.append(
                {
                    "image_id": identifier,
                    "category_id": category,
                    "bbox": [5, 5, 10, 10],
                    "iscrowd": 0,
                }
            )
    return {
        "images": images,
        "annotations": annotations,
        "licenses": [{"id": 4, "url": "https://creativecommons.org/licenses/by/2.0/"}],
    }


def test_small_object_subset_has_distinct_licensed_sources_and_both_splits(monkeypatch):
    module = load_experiment(monkeypatch)
    selected = module.select_records(data(), per_category=2)
    assert len(selected) == 8
    assert len({r["id"] for r in selected}) == 8
    assert {r["split"] for r in selected} == {"development", "holdout"}
    assert all(r["license_id"] == 4 and r["captured_at"] is None for r in selected)


def test_subset_cannot_silently_replace_missing_small_licensed_targets(monkeypatch):
    module = load_experiment(monkeypatch)
    bad = data()
    bad["images"][0]["license"] = 1
    with pytest.raises(ValueError):
        module.select_records(bad, per_category=2)
