"""Check scene-change nomination without loading a model or opening hardware."""

import argparse
import json
import platform
import time
from importlib.metadata import version
from pathlib import Path

from PIL import Image, ImageDraw

from nyx.attention import sequence_changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "runtime": {name: version(name) for name in ["numpy", "pillow"]},
        "policy": "anchor-block-change-v1",
        "meaning": "Scene change nominates inspection; it does not establish departure",
        "cases": [],
    }

    def record(name, images, **metadata):
        started = time.perf_counter()
        selected = sequence_changed(images)
        row = {
            "name": name,
            **metadata,
            "motion_selected": selected,
            "seconds": time.perf_counter() - started,
        }
        results["cases"].append(row)
        print(json.dumps(row), flush=True)

    for case in json.loads(args.manifest.read_text())["cases"]:
        paths = sorted(Path(case["frames"]).glob("*.jpg"))
        images = []
        for index in case["indices"]:
            with Image.open(paths[index]) as source:
                image = source.convert("RGB")
            image.thumbnail((640, 360))
            images.append(image)
        record(case["name"], images, source=case)

    def gray(level):
        return Image.new("RGB", (160, 96), (level,) * 3)

    for name, levels, expected in [
        ("synthetic-static", [100, 100, 100], False),
        ("synthetic-noise", [100, 101, 100], False),
        ("synthetic-cumulative", [100, 105, 110], True),
    ]:
        record(name, [gray(level) for level in levels], expected_change=expected)
    changed = gray(100)
    ImageDraw.Draw(changed).rectangle((60, 40, 76, 56), fill="white")
    record("synthetic-local-change", [gray(100), changed, changed], expected_change=True)
    (args.output / "results.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
