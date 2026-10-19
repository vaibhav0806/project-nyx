"""Reproducible semantic smoke benchmark. Public still scenes, not household validation."""

import argparse
import hashlib
import json
import platform
import resource
import subprocess
import time
from importlib.metadata import version
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from nyx.memory import Store
from nyx.report import write_gallery
from nyx.retrieval import index_video, search

SOURCES = {
    "cats": "https://huggingface.co/datasets/merve/coco/resolve/main/val2017/000000039769.jpg",
    "parrots": "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/hub/parrots.png",
    "coffee": "https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/coffee.png",
    "camera": "https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/camera.png",
}
QUERIES = [
    ("two cats resting on a sofa", "cats"),
    ("a cup of coffee", "coffee"),
    ("a man using a camera on a tripod", "camera"),
    ("parrots", "parrots"),
    ("a television remote control", "remote"),
    ("a metal spoon", "spoon"),
    ("coffee in a cup on a saucer", "coffee"),
    ("cats next to remote controls", "remote"),
    ("a pair of eyeglasses", None),
    ("a set of house keys", None),
]


def spatial_views(image):
    width, height = image.size
    crop_width, crop_height = (2 * width + 2) // 3, (2 * height + 2) // 3
    boxes = [(0, 0, width, height)]
    boxes.extend(
        (x, y, x + crop_width, y + crop_height)
        for y in [0, height - crop_height]
        for x in [0, width - crop_width]
    )
    return [(box, image.crop(box)) for box in boxes]


def rank_frames(query_vector, features):
    similarities = features @ query_vector
    best_views = similarities.argmax(axis=1)
    rows = [
        {
            "frame_index": index,
            "view_index": int(view),
            "similarity": float(similarities[index, view]),
        }
        for index, view in enumerate(best_views)
    ]
    return sorted(rows, key=lambda row: (-row["similarity"], row["frame_index"]))


def score_occurrences(ranked_scenes, target, labels):
    relevant = [scene for scene in labels if target and target in scene["objects"]]
    ranks = [
        {"scene": scene["scene"], "rank": rank}
        for rank, scene in enumerate(ranked_scenes, 1)
        if target and target in scene["objects"]
    ]
    count = len(relevant)
    latest = max(relevant, key=lambda scene: scene["start"])["scene"] if relevant else None
    return {
        "relevant_scene_count": count,
        "relevant_scene_ranks": ranks,
        **{
            f"recall_at_{k}": sum(row["rank"] <= k for row in ranks) / count if count else None
            for k in [1, 3, 5]
        },
        "average_precision": sum(hit / row["rank"] for hit, row in enumerate(ranks, 1)) / count
        if count
        else None,
        "latest_labelled_scene_rank": next(
            (row["rank"] for row in ranks if row["scene"] == latest), None
        ),
    }


def compare_crops(encoder, store, labels, output):
    with store.connection() as db:
        frames = [
            dict(row)
            for row in db.execute("""
                SELECT f.*, v.name, v.path AS video_path, v.recorded_at
                FROM frames f JOIN videos v ON v.id = f.video_id
                WHERE v.status = 'ready' ORDER BY f.offset_seconds, f.id
            """)
        ]
    features, boxes = [], []
    started = time.perf_counter()
    for frame in frames:
        with Image.open(store.root / frame["thumbnail"]) as image:
            views = spatial_views(image.convert("RGB"))
        crops = encoder.encode_images([image for _, image in views[1:]])
        full = np.frombuffer(frame["embedding"], dtype=np.float32)
        features.append(np.vstack([full, crops]))
        boxes.append([box for box, _ in views])
    crop_seconds = time.perf_counter() - started
    features = np.stack(features)
    np.save(output / "view-features.npy", features)
    scenes = [
        next(scene for scene in labels if scene["start"] <= frame["offset_seconds"] < scene["end"])
        for frame in frames
    ]
    strategies = {"full_frame": features[:, :1], "full_plus_crops": features}
    rows = []
    for number, (query, target) in enumerate(QUERIES):
        started = time.perf_counter()
        query_vector = encoder.encode_text(query)
        query_seconds = time.perf_counter() - started
        row = {"query": query, "target": target, "text_encode_seconds": query_seconds}
        for name, vectors in strategies.items():
            started = time.perf_counter()
            ranked = rank_frames(query_vector, vectors)
            rank_seconds = time.perf_counter() - started
            candidates = []
            for match in ranked:
                index = match["frame_index"]
                candidates.append(
                    {
                        **{
                            key: value for key, value in frames[index].items() if key != "embedding"
                        },
                        **match,
                        "scene": scenes[index]["scene"],
                        "objects": scenes[index]["objects"],
                        "view_box": boxes[index][match["view_index"]],
                        "verified": False,
                    }
                )
            row[name] = {
                **score_occurrences(
                    [scenes[match["frame_index"]] for match in ranked], target, labels
                ),
                "rank_seconds": rank_seconds,
                "candidates": candidates,
            }
            write_gallery(
                f"{query} ({name})",
                candidates[:5],
                store.root,
                output / "galleries" / f"{number:02}-{name}.html",
            )
        rows.append(row)
    result = {
        "encoder": encoder.fingerprint,
        "device": encoder.device,
        "policy": "Full frame plus four overlapping corner crops, each ceil(2/3) of each axis; max score per source frame.",
        "frame_count": len(frames),
        "full_frame_view_count": len(frames),
        "full_plus_crops_view_count": int(features.shape[0] * features.shape[1]),
        "additional_crop_encode_seconds": crop_seconds,
        "summary": {
            name: {
                metric: float(np.mean([row[name][metric] for row in rows if row["target"]]))
                for metric in ["recall_at_1", "recall_at_3", "recall_at_5", "average_precision"]
            }
            for name in strategies
        },
        "queries": rows,
        "limitations": [
            "Same small correlated fixture; labels informed this experiment, not held-out evaluation.",
            "Category labels do not verify spatial relations or last-seen answers.",
            "Max over more views changes the score distribution; no presence threshold is calibrated.",
            "Additional crop timing includes decode/preprocess/inference; no standalone peak-memory comparison.",
            "Five-view results are experimental and do not change the application's full-frame index.",
        ],
    }
    (output / "crop-comparison.json").write_text(json.dumps(result, indent=2))
    print(
        "Crop comparison:",
        json.dumps({key: value for key, value in result.items() if key != "queries"}, indent=2),
    )


def prepare(sources_dir, output, download):
    sources_dir.mkdir(parents=True, exist_ok=True)
    originals = {}
    for name, url in SOURCES.items():
        path = sources_dir / f"{name}.img"
        if not path.exists():
            if not download:
                raise ValueError(
                    "Sample images missing; pass --download-samples to fetch public fixtures"
                )
            with urlopen(url, timeout=60) as response:
                path.write_bytes(response.read())
        with Image.open(path) as image:
            originals[name] = image.convert("RGB")
    cats = originals["cats"]
    coffee = originals["coffee"]
    camera = originals["camera"]
    parrots = originals["parrots"]
    covered = cats.copy()
    draw = ImageDraw.Draw(covered)
    draw.rectangle((30, 65, 181, 126), fill="#802c56")
    draw.rectangle((325, 68, 379, 194), fill="#802c56")
    remote = cats.crop((34, 66, 181, 124))
    small_coffee = Image.new("RGB", (960, 540), "#b8b8b8")
    small_coffee.paste(ImageOps.contain(coffee, (150, 100)), (400, 220))
    small_remote = Image.new("RGB", (960, 540), "#b8b8b8")
    small_remote.paste(ImageOps.contain(remote, (100, 45)), (410, 240))
    scenes = [
        ("cats_original", cats, ["cats", "remote"]),
        ("coffee_original", coffee, ["coffee", "spoon"]),
        ("camera_original", camera, ["camera"]),
        ("parrots_original", parrots, ["parrots"]),
        ("cats_mirrored", ImageOps.mirror(cats), ["cats", "remote"]),
        ("coffee_small", small_coffee, ["coffee", "spoon"]),
        ("remotes_covered", covered, ["cats"]),
        ("remote_crop", remote, ["remote"]),
        ("remote_small", small_remote, ["remote"]),
        ("empty", Image.new("RGB", (960, 540), "#b8b8b8"), []),
        ("coffee_grayscale", ImageOps.grayscale(coffee).convert("RGB"), ["coffee", "spoon"]),
        ("one_parrot", parrots.crop((365, 0, 768, 512)), ["parrots"]),
    ]
    frames = output / "input_frames"
    frames.mkdir()
    labels = []
    for number, (name, image, objects) in enumerate(scenes):
        frame = ImageOps.pad(image, (960, 540), color="#b8b8b8")
        frame.save(frames / f"{number:03}.png")
        labels.append(
            {"scene": name, "start": number * 2, "end": (number + 1) * 2, "objects": objects}
        )
    video = output / "scenes.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-framerate",
            "1/2",
            "-i",
            str(frames / "%03d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    (output / "dataset.json").write_text(
        json.dumps(
            {
                "description": "Twelve edited scenes from four public still images, two seconds each.",
                "sources": [
                    {
                        "name": name,
                        "url": url,
                        "sha256": hashlib.sha256(
                            (sources_dir / f"{name}.img").read_bytes()
                        ).hexdigest(),
                    }
                    for name, url in SOURCES.items()
                ],
                "scenes": labels,
            },
            indent=2,
        )
    )
    return video, labels


def main():
    import torch

    from nyx.perception import SiglipEncoder

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=Path("data/evaluation/source"))
    parser.add_argument("--download-samples", action="store_true")
    parser.add_argument("--device", choices=["auto", "mps", "cpu"], default="auto")
    parser.add_argument("--compare-crops", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Choose an empty output directory to keep runs independent")
    args.output.mkdir(parents=True, exist_ok=True)
    video, labels = prepare(args.sources, args.output, args.download_samples)
    encoder = SiglipEncoder(args.device)
    store = Store(args.output / "index", encoder.fingerprint, encoder.dimensions)
    first = Image.open(args.output / "input_frames/000.png").convert("RGB")
    started = time.perf_counter()
    encoder.encode_images([first])
    first_image_seconds = time.perf_counter() - started
    indexed = index_video(video, store, encoder, interval=2, batch_size=4)
    rows = []
    for number, (query, target) in enumerate(QUERIES):
        started = time.perf_counter()
        results = search(query, store, encoder, limit=3)
        elapsed = time.perf_counter() - started
        hits = []
        for result in results:
            scene = labels[int(result["offset_seconds"] // 2)]
            hits.append(
                {
                    "scene": scene["scene"],
                    "objects": scene["objects"],
                    "offset_seconds": result["offset_seconds"],
                    "similarity": result["similarity"],
                }
            )
        rows.append(
            {
                "query": query,
                "target": target,
                "seconds": elapsed,
                "candidates": hits,
                "hit_at_1": target in hits[0]["objects"] if target else None,
                "hit_at_3": any(target in hit["objects"] for hit in hits) if target else None,
                "relevant_scene_count": sum(target in scene["objects"] for scene in labels)
                if target
                else 0,
                "relevant_scenes_in_top_3": sum(target in hit["objects"] for hit in hits)
                if target
                else 0,
            }
        )
        write_gallery(query, results, store.root, args.output / "galleries" / f"{number:02}.html")
    positives = [row for row in rows if row["target"]]
    durations = [row["seconds"] for row in rows[1:]]
    result = {
        "machine": {"system": platform.platform(), "processor": platform.processor()},
        "versions": {
            name: version(name)
            for name in ["torch", "transformers", "numpy", "sqlite-vec", "pillow"]
        },
        "encoder": encoder.fingerprint,
        "device": encoder.device,
        "model_load_seconds": encoder.load_seconds,
        "first_image_seconds": first_image_seconds,
        "index": indexed,
        "positive_query_hit_rate_at_1": sum(row["hit_at_1"] for row in positives) / len(positives),
        "positive_query_hit_rate_at_3": sum(row["hit_at_3"] for row in positives) / len(positives),
        "first_query_seconds": rows[0]["seconds"],
        "warm_query_p50_seconds": float(np.median(durations)),
        "warm_query_p95_seconds": float(np.percentile(durations, 95)),
        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "mps_driver_allocated_bytes_at_end": torch.mps.driver_allocated_memory()
        if encoder.device == "mps"
        else None,
        "queries": rows,
        "limitations": [
            "Four source images with derived scenes; no independent household-video validation.",
            "No motion/arrival evaluation; these are still frames assembled into video.",
            "Descriptive queries only; no VLM verification or automatic absence decision.",
            "Whole-frame retrieval may miss small objects; scores are not probabilities.",
            "Metrics are single-run smoke results; load time excludes first-time weight download.",
        ],
    }
    (args.output / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({key: value for key, value in result.items() if key != "queries"}, indent=2))
    print("Queries:", json.dumps(rows, indent=2))
    if args.compare_crops:
        compare_crops(encoder, store, labels, args.output)


if __name__ == "__main__":
    main()
