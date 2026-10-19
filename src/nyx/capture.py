import math
import re
import subprocess
from pathlib import Path


def extract_frames(video: Path, destination: Path, interval=2.0):
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("Sampling interval must be finite and positive")
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError("Frame destination must be empty")
    filters = (
        "setpts=PTS-STARTPTS,"
        f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{interval})',"
        "scale=w='min(960,iw)':h=-2,showinfo"
    )
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-i",
                str(video),
                "-an",
                "-vf",
                filters,
                "-fps_mode",
                "vfr",
                "-q:v",
                "2",
                str(destination / "%06d.jpg"),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Video decoding exceeded two minutes; try a shorter clip") from exc
    if result.returncode:
        raise ValueError(f"Could not decode video: {result.stderr[-1500:].strip()}")
    offsets = [
        float(value) for value in re.findall(r"\bn:\s*\d+.*?pts_time:([-+\d.eE]+)", result.stderr)
    ]
    paths = sorted(destination.glob("*.jpg"))
    if not paths or len(paths) != len(offsets):
        raise ValueError("Video produced no frames or frame timestamps could not be matched")
    return list(zip(offsets, paths, strict=True))
