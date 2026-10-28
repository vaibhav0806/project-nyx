"""Replay cheap temporal nomination on generated scenes and optional local public clips.

No vision model, device, cloud call or semantic departure judgment is involved.
"""

import argparse
import hashlib
import json
import platform
from collections import Counter
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from nyx import observation
from nyx.attention import select_activity_frames
from nyx.capture import extract_frames


def scene(position=None):
    image = Image.new("RGB", (160, 96), "gray")
    if position is not None:
        ImageDraw.Draw(image).rectangle((position, 35, position + 18, 58), fill="white")
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "runtime": {name: version(name) for name in ["numpy", "pillow"]},
        "policy": "ActivityWindow + Observer; 0.1s requested decode interval",
        "meaning": "Nominations only, not model interpretations or semantic accuracy",
        "cases": [],
    }
    base = datetime.now(UTC)
    clock = [base]
    original = observation.datetime

    class ReplayClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    def run(name, frames, **metadata):
        observer = observation.Observer()
        phases = Counter()
        nominations = []
        for at, source in frames:
            if isinstance(source, Image.Image):
                image = source
            else:
                with Image.open(source) as opened:
                    image = opened.convert("RGB")
            clock[0] = base + timedelta(seconds=at)
            burst = observer.feed(name, image, clock[0].isoformat())
            phases[observer.phase] += 1
            if burst:
                observer.accept(burst)
                nominations.append(
                    {"offset": at, "event_id": burst["event_id"], "frame_times": burst["times"]}
                )
        selected = select_activity_frames(frames)
        row = {
            "name": name,
            **metadata,
            "decoded_samples": len(frames),
            "selected_offsets": [at for at, _ in selected],
            "nominations": nominations,
            "phases": dict(phases),
            "episode_count": len({row["event_id"] for row in nominations}),
        }
        results["cases"].append(row)
        (args.output / "results.json").write_text(json.dumps(results, indent=2))
        print(
            json.dumps(
                {
                    "name": name,
                    "decoded": len(frames),
                    "indexed": len(selected),
                    "nominations": len(nominations),
                    "episodes": row["episode_count"],
                }
            ),
            flush=True,
        )

    observation.datetime = ReplayClock
    try:
        run("synthetic-static-120s", [(tick / 10, scene()) for tick in range(1201)])
        run(
            "synthetic-flash-100ms",
            [(tick / 10, scene(60) if tick == 10 else scene()) for tick in range(41)],
        )
        run(
            "synthetic-persistent-placement",
            [(tick / 10, scene(60) if tick >= 10 else scene()) for tick in range(41)],
        )
        run(
            "synthetic-continuous-motion",
            [
                (tick / 10, scene(30 + tick % 4 * 20) if tick >= 5 else scene())
                for tick in range(101)
            ],
        )
        if args.manifest:
            for case in json.loads(args.manifest.read_text())["cases"]:
                source = Path(case["frames"]).parent / f"{case['name']}.mp4"
                with TemporaryDirectory(prefix="nyx-temporal-") as folder:
                    frames = extract_frames(source, Path(folder) / "frames", 0.1)
                    run(
                        case["name"],
                        frames,
                        source=str(source),
                        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                        label_note="Full clip nomination; existing departure labels describe selected subsequences only",
                    )
    finally:
        observation.datetime = original


if __name__ == "__main__":
    main()
