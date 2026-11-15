import importlib.util
from pathlib import Path

import pytest


def benchmark():
    spec = importlib.util.spec_from_file_location(
        "wake_benchmark",
        Path(__file__).resolve().parents[1] / "experiments/companion/wake_benchmark.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wake_metrics_separate_misses_false_wakes_and_failed_checks():
    metrics = benchmark().summarize(
        [
            {
                "expected": True,
                "detected": True,
                "status": "complete",
                "kind": "wake",
                "seconds": 2,
            },
            {
                "expected": True,
                "detected": False,
                "status": "complete",
                "kind": "wake",
                "seconds": 2,
            },
            {
                "expected": False,
                "detected": True,
                "status": "complete",
                "kind": "near_name",
                "seconds": 3,
            },
            {
                "expected": False,
                "detected": None,
                "status": "failed",
                "kind": "ordinary",
                "seconds": 3,
            },
        ]
    )
    assert metrics["correct"] == 1 and metrics["failed"] == 1
    assert metrics["wake_recall"] == 0.5 and metrics["false_wakes"] == 1
    assert metrics["negative_seconds"] == 6


def test_probe_windows_are_bounded_and_end_on_available_audio():
    windows = benchmark().probe_windows(16000 * 5)
    assert windows and windows[-1][1] <= 80000
    assert all(9600 <= end - start <= 48000 for start, end in windows)
    assert benchmark().probe_windows(100) == []
    with pytest.raises(ValueError):
        benchmark().probe_windows(-1)
