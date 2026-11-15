import importlib.util
from pathlib import Path

import numpy as np


def test_cached_pool_comparison_counts_unique_sources_and_preserves_both_conditions(tmp_path):
    path = Path(__file__).resolve().parents[1] / "experiments/companion/candidate_pool_replay.py"
    spec = importlib.util.spec_from_file_location("candidate_pool_replay", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    records = [
        {"id": 1, "category": 1, "all_categories": [1]},
        {"id": 2, "category": 2, "all_categories": [2]},
        {"id": 3, "category": 1, "all_categories": [1]},
    ]
    vectors = np.array([[1, 0], [0.99, 0.1], [0.8, 0.6]], dtype=np.float32)
    result = module.compare_pool(records, vectors, 0, tmp_path)
    assert result["uncrowded"]["flat"]["recall_at_12"] == 1
    assert result["uncrowded"]["balanced"]["recall_at_12"] == 1
    assert result["crowded"]["flat"]["recall_at_12"] == 0
    assert result["crowded"]["balanced"]["recall_at_12"] == 1
    assert result["crowded"]["balanced"]["selected_sources"] == [2, 3]
