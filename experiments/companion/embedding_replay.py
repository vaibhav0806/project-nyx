"""Opt-in paid embedding comparison on the existing permitted public still-scene fixture."""

import argparse
import hashlib
import json
import math
import shutil
import sqlite3
import time
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image

from nyx.memory import Store
from nyx.perception import CloudEncoder
from nyx.retrieval import search

QUERIES = [
    ("a television remote control", "remote"),
    ("a cup of coffee", "coffee"),
    ("a metal spoon", "spoon"),
    ("a man using a camera on a tripod", "camera"),
    ("parrots", "parrots"),
    ("two cats resting on a sofa", "cats"),
    ("टीवी का रिमोट", "remote"),
    ("कॉफी का कप", "coffee"),
    ("कैमरा", "camera"),
    ("तोते", "parrots"),
    ("mera TV remote", "remote"),
    ("coffee wala cup", "coffee"),
    ("a pair of eyeglasses", None),
    ("a set of house keys", None),
]
REFERENCES = [
    ("remote_crop", "remote"),
    ("coffee_original", "coffee"),
    ("camera_original", "camera"),
]

# User-authorized cumulative ceiling, updated 2026-11-15: $5 TOTAL, not an extra $5.
TEST_SPEND_CEILING_USD = 5.0


def check_budget(snapshot, initial_usage, max_spend, *, reported_cost=0):
    usage = snapshot.get("usage")
    limit = snapshot.get("limit")
    if not isinstance(usage, (int, float)) or not math.isfinite(usage):
        raise ValueError("Cannot establish cumulative provider spending")
    ceiling = (
        min(TEST_SPEND_CEILING_USD, limit)
        if isinstance(limit, (int, float))
        else TEST_SPEND_CEILING_USD
    )
    if not 0 < max_spend <= 0.25 or not math.isfinite(initial_usage) or usage < initial_usage:
        raise ValueError("Invalid benchmark budget or usage baseline")
    if not math.isfinite(reported_cost) or reported_cost < 0:
        raise ValueError("Invalid reported provider cost")
    usage = max(usage, initial_usage + reported_cost)
    remaining = min(ceiling - usage, max_spend - (usage - initial_usage)) - 0.02
    if remaining <= 0:
        raise ValueError("Provider/benchmark spending limit reached")
    return remaining


def score_candidates(rows, relevant):
    ranks = [rank for rank, row in enumerate(rows, 1) if row["id"] in relevant]
    return {
        "positive": bool(relevant),
        "relevant_count": len(relevant),
        "recall_at_3": sum(rank <= 3 for rank in ranks) / len(relevant) if relevant else None,
        "reciprocal_rank": 1 / min(ranks) if ranks else (0 if relevant else None),
    }


def budget_snapshot(client):
    request = Request(
        "https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + client.key}
    )
    with urlopen(request, timeout=15) as response:
        data = json.load(response)["data"]
    return {
        "usage": data.get("usage"),
        "limit": data.get("limit"),
        "limit_remaining": data.get("limit_remaining"),
    }


def run(fixture, output, max_spend):
    fixture = Path(fixture).resolve()
    source = fixture / "index"
    manifest = json.loads((fixture / "dataset.json").read_text())
    if (
        manifest.get("description")
        != "Twelve edited scenes from four public still images, two seconds each."
    ):
        raise ValueError("This experiment only accepts the known public R3/R9 fixture")
    encoder = CloudEncoder()
    if encoder.model != "google/gemini-embedding-2":
        raise ValueError("Select the documented Gemini embedding baseline for this experiment")
    initial = budget_snapshot(encoder.client)
    check_budget(initial, initial["usage"], max_spend)
    output.mkdir(parents=True, exist_ok=False)
    results = {
        "status": "running",
        "encoder": encoder.fingerprint,
        "budget_before": initial,
        "fixture_manifest_sha256": hashlib.sha256(
            (fixture / "dataset.json").read_bytes()
        ).hexdigest(),
        "queries": [],
        "reference_queries": [],
        "timings": [],
        "limitations": "Previously used four-source development fixture, not untouched household evaluation. Retrieval candidates do not prove presence; negatives have no calibrated abstention score.",
    }

    def checkpoint():
        results["provider_usage"] = encoder.client.usage
        (output / "results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False) + "\n"
        )

    def call(label, operation, *arguments, **keywords):
        check_budget(
            budget_snapshot(encoder.client),
            initial["usage"],
            max_spend,
            reported_cost=sum(u.get("cost") or 0 for u in encoder.client.usage),
        )
        started = time.perf_counter()
        before = len(encoder.client.usage)
        try:
            return operation(*arguments, **keywords)
        finally:
            results["timings"].append(
                {
                    "operation": label,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                    "provider_requests": len(encoder.client.usage) - before,
                }
            )
            checkpoint()

    try:
        with sqlite3.connect(f"file:{source / 'index.sqlite3'}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            videos = [dict(r) for r in db.execute("SELECT * FROM videos WHERE status='ready'")]
            frames = [
                dict(r)
                for r in db.execute(
                    "SELECT f.* FROM frames f JOIN videos v ON v.id=f.video_id WHERE v.status='ready' ORDER BY f.id"
                )
            ]
        store = Store(output / "index", encoder.fingerprint, encoder.dimensions)
        for video in videos:
            path = (source / video["path"]).resolve()
            if not path.is_relative_to(source):
                raise ValueError("Source escapes public fixture directory")
            destination = store.root / video["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            store.add_video(
                video["name"],
                video["path"],
                video["recorded_at"],
                video["interval_seconds"],
                video["id"],
            )
            selected = [r for r in frames if r["video_id"] == video["id"]]
            for begin in range(0, len(selected), 4):
                batch = selected[begin : begin + 4]
                images = []
                for row in batch:
                    path = (source / row["thumbnail"]).resolve()
                    if not path.is_relative_to(source):
                        raise ValueError("Frame escapes public fixture directory")
                    destination = store.root / row["thumbnail"]
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, destination)
                    with Image.open(path) as image:
                        images.append(image.convert("RGB"))
                vectors = call("index_images", encoder.encode_images, images)
                store.add_frames(
                    video["id"], [(r["offset_seconds"], r["thumbnail"]) for r in batch], vectors
                )
            store.finish_video(video["id"])
        with store.connection() as db:
            saved = [
                dict(r)
                for r in db.execute(
                    "SELECT id,offset_seconds,thumbnail FROM frames ORDER BY offset_seconds"
                )
            ]

        def relevant(target):
            return (
                {
                    r["id"]
                    for r in saved
                    if any(
                        s["start"] <= r["offset_seconds"] < s["end"] and target in s["objects"]
                        for s in manifest["scenes"]
                    )
                }
                if target
                else set()
            )

        for query, target in QUERIES:
            for formatting, text in [
                ("bare", query),
                ("search_instruction", "task: search result | query: " + query),
            ]:
                rows = call("query_" + formatting, search, text, store, encoder, limit=5)
                results["queries"].append(
                    {
                        "query": query,
                        "target": target,
                        "format": formatting,
                        "frame_ids": [r["id"] for r in rows],
                        **score_candidates(rows, relevant(target)),
                    }
                )
                checkpoint()
        for scene, target in REFERENCES:
            label = next(s for s in manifest["scenes"] if s["scene"] == scene)
            sample = next(r for r in saved if label["start"] <= r["offset_seconds"] < label["end"])
            with Image.open(store.root / sample["thumbnail"]) as image:
                reference = image.convert("RGB")
            query = "a small personal object"
            for route, image in [("text_only", None), ("text_and_reference", reference)]:
                rows = call(route, search, query, store, encoder, reference_image=image, limit=5)
                results["reference_queries"].append(
                    {
                        "scene": scene,
                        "target": target,
                        "route": route,
                        "frame_ids": [r["id"] for r in rows],
                        **score_candidates(rows, relevant(target)),
                    }
                )
                checkpoint()
        results["status"] = "complete"
    except Exception as error:
        results["status"] = "failed"
        results["error_type"] = type(error).__name__
        raise
    finally:
        try:
            results["budget_after"] = budget_snapshot(encoder.client)
            results["run_spend_usd"] = results["budget_after"]["usage"] - initial["usage"]
        finally:
            checkpoint()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.15)
    args = parser.parse_args()
    result = run(args.fixture, args.output, args.max_spend)
    summary = {"status": result["status"], "run_spend_usd": result["run_spend_usd"]}
    for group, key in [("queries", "format"), ("reference_queries", "route")]:
        summary[group] = {}
        for variant in sorted({r[key] for r in result[group]}):
            rows = [r for r in result[group] if r[key] == variant and r["positive"]]
            summary[group][variant] = {
                "positive_queries": len(rows),
                "mean_recall_at_3": sum(r["recall_at_3"] for r in rows) / len(rows),
                "mean_reciprocal_rank": sum(r["reciprocal_rank"] for r in rows) / len(rows),
            }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
