"""Actual plain-JavaScript transport boundaries, without browser/hardware/provider IO."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_browser_audio_gate_tracks_activity_and_preserves_idle_privacy():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the browser transport regression")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("voice_transport_smoke.cjs"))],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
