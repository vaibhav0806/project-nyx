"""Labeled, offline sampling replay. No inference, devices or private input discovery."""

import argparse
import hashlib
import json
import math
import platform
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from nyx.attention import select_activity_frames
from nyx.memory import aware_time


def validate_manifest(manifest):
    if manifest.get("version") != 1 or not manifest.get("cases"):
        raise ValueError("Expected version 1 and nonempty replay cases")
    ids, groups, sources = set(), {}, {}
    for row in manifest["cases"]:
        if not row.get("id") or row["id"] in ids:
            raise ValueError("Replay case IDs must be unique")
        ids.add(row["id"])
        split, group = row.get("split"), row.get("group")
        if split not in {"development", "holdout"} or not group:
            raise ValueError("Each case needs a source group and split")
        source = row.get("source", {})
        digest = source.get("sha256", "")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Source needs a SHA256 digest")
        if source.get("kind") not in {"synthetic", "permitted_frames"}:
            raise ValueError("Declare synthetic or permitted_frames source")
        for mapping, key in [(groups, group), (sources, digest)]:
            if key in mapping and mapping[key] != split:
                raise ValueError("Source/episode leakage between replay splits")
            mapping[key] = split
        for value in [source.get("captured_at"), row.get("replay_at")]:
            if value is not None:
                aware_time(value)
        duration = row.get("duration_seconds", 0)
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Replay duration must be finite and positive")
        for interval in row.get("visible_intervals", []):
            if len(interval) != 2 or any(not math.isfinite(t) for t in interval):
                raise ValueError("Invalid evidence interval")
            if not 0 <= interval[0] < interval[1] <= duration:
                raise ValueError("Evidence interval is outside its source")
        if not row.get("query", "").strip():
            raise ValueError("Replay query is required")
    return manifest


def score_selection(case, offsets):
    if any(not math.isfinite(t) or not 0 <= t < case["duration_seconds"] for t in offsets):
        raise ValueError("Selected offset is outside the source")
    if offsets != sorted(set(offsets)):
        raise ValueError("Selected offsets must be ordered and unique")
    intervals = case["visible_intervals"]
    retained = sum(any(start <= t < end for t in offsets) for start, end in intervals)
    return {
        "events": len(intervals),
        "events_retained": retained,
        "event_recall": retained / len(intervals) if intervals else None,
        "sample_count": len(offsets),
        "selected_offsets": offsets,
    }


def replay_frames(case, root):
    source = case["source"]
    if source["kind"] == "synthetic":
        recipe = source["recipe"]
        if (
            hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("Synthetic source recipe digest changed")
        if recipe["duration_seconds"] != case["duration_seconds"]:
            raise ValueError("Recipe duration differs from labels")
        background = Image.new(
            "RGB", (recipe["width"], recipe["height"]), (recipe["background"],) * 3
        )
        visible = background.copy()
        ImageDraw.Draw(visible).rectangle(recipe["box"], fill=(recipe["foreground"],) * 3)
        return [
            (
                tick / 10,
                visible
                if any(a <= tick / 10 < b for a, b in recipe["visible_intervals"])
                else background,
            )
            for tick in range(math.ceil(case["duration_seconds"] * 10))
        ]
    frames = []
    root = Path(root).resolve()
    samples = source.get("frames", [])
    if not samples:
        raise ValueError("Permitted source requires hashed frame samples")
    digest = hashlib.sha256()
    for sample in samples:
        path = (root / sample["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Replay frame escapes its manifest directory")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != sample["sha256"]:
            raise ValueError("Replay frame digest changed")
        digest.update(f"{sample['offset_seconds']}:{actual}\n".encode())
        frames.append((sample["offset_seconds"], path))
    if digest.hexdigest() != source["sha256"]:
        raise ValueError("Replay frame-stream digest changed")
    score_selection(case, [t for t, _ in frames])
    return frames


def compare_selectors(case, root=Path("."), coverage_interval=2):
    frames = replay_frames(case, root)
    return {
        name: score_selection(
            case, [at for at, _ in select_activity_frames(frames, coverage_interval=interval)]
        )
        for name, interval in [
            ("activity_only", None),
            ("coverage_plus_activity", coverage_interval),
        ]
    }


def generated_manifest(count=100):
    if not 2 <= count <= 200:
        raise ValueError("Generate between 2 and 200 synthetic conditions")
    evaluation_at = datetime(2026, 11, 15, 12, tzinfo=UTC)
    cases = []
    for i in range(count):
        start = round(0.3 + (i * 13 % 65) / 10, 1)
        end = round(start + 0.2 + (i % 8) * 0.4, 1)
        intervals = [] if i % 5 == 0 else [[start, end]]
        left, top = 400 + i % 11 * 7, 280 + i % 13 * 3
        recipe = {
            "width": 1280,
            "height": 720,
            "background": 80 + i % 20,
            "foreground": 180 + i % 30,
            "box": [left, top, left + 15 + i % 50, top + 10 + i % 20],
            "duration_seconds": 10,
            "visible_intervals": intervals,
        }
        cases.append(
            {
                "id": f"generated-{i:03}",
                "group": f"scene-{i:03}",
                "split": "development" if i < count * 0.6 else "holdout",
                "source": {
                    "kind": "synthetic",
                    "recipe": recipe,
                    "captured_at": None,
                    "sha256": hashlib.sha256(
                        json.dumps(recipe, sort_keys=True).encode()
                    ).hexdigest(),
                },
                "replay_at": (evaluation_at - timedelta(days=i % 12)).isoformat(),
                "duration_seconds": 10,
                "visible_intervals": intervals,
                "query": "Find the small placed object",
            }
        )
    return validate_manifest(
        {"version": 1, "generator": "small-object-conditions-v1", "cases": cases}
    )


def run(manifest, root, coverage_interval=2, split="development"):
    validate_manifest(manifest)
    if split not in {"development", "holdout", "all"}:
        raise ValueError("Unknown replay split")
    results = [
        {
            "id": r["id"],
            "group": r["group"],
            "split": r["split"],
            "selectors": compare_selectors(r, root, coverage_interval),
        }
        for r in manifest["cases"]
        if split == "all" or r["split"] == split
    ]
    summary = {}
    for partition in ["development", "holdout"]:
        rows = [r for r in results if r["split"] == partition]
        summary[partition] = {}
        for selector in ["activity_only", "coverage_plus_activity"]:
            events = sum(r["selectors"][selector]["events"] for r in rows)
            retained = sum(r["selectors"][selector]["events_retained"] for r in rows)
            summary[partition][selector] = {
                "cases": len(rows),
                "events": events,
                "events_retained": retained,
                "event_recall": retained / events if events else None,
                "samples": sum(r["selectors"][selector]["sample_count"] for r in rows),
            }
    return {
        "kind": "sampling-condition-replay",
        "python": platform.python_version(),
        "coverage_interval": coverage_interval,
        "summary": summary,
        "cases": results,
        "limitations": "Synthetic conditions are not household semantic retrieval accuracy; no inference or elapsed-time soak measured.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--coverage-interval", type=float, default=2)
    parser.add_argument("--split", choices=["development", "holdout", "all"], default="development")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text()) if args.manifest else generated_manifest()
    result = run(
        manifest,
        args.manifest.parent if args.manifest else Path("."),
        args.coverage_interval,
        args.split,
    )
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
