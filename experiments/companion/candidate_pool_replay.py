"""Offline candidate-pool crowding test on cached public-photo vectors, not final answers."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from nyx.answers import diverse_candidates
from nyx.memory import Store


def compare_pool(records, features, query_index, root, *, fingerprint=None):
    query = features[query_index]
    candidates = [i for i in range(len(records)) if i != query_index]
    relevant = {
        records[i]["id"]
        for i in candidates
        if records[query_index]["category"] in records[i]["all_categories"]
    }
    irrelevant = [i for i in candidates if records[i]["id"] not in relevant]
    dominant = max(irrelevant, key=lambda i: float(np.dot(features[i], query)))
    result = {
        "query_image": records[query_index]["id"],
        "dominant_irrelevant_image": records[dominant]["id"],
    }
    for condition in ["uncrowded", "crowded"]:
        store = Store(
            root / condition,
            fingerprint or {"model": "synthetic-candidate-vectors"},
            features.shape[1],
        )
        for i in candidates:
            record = records[i]
            copies = 80 if condition == "crowded" and i == dominant else 1
            video = store.add_video(
                str(record["id"]),
                f"synthetic/{record['id']}.mp4",
                "2026-11-06T12:00:00Z",
                2,
                f"{record['id']:032x}",
            )
            store.add_frames(
                video,
                [(2 * n, f"synthetic/{record['id']}-{n}.jpg") for n in range(copies)],
                np.repeat(features[i][None, :], copies, axis=0),
            )
            store.finish_video(video)
        result[condition] = {}
        for name, balanced in [("flat", False), ("balanced", True)]:
            started = time.perf_counter()
            pool = store.search(query, limit=64, known_time_only=True, source_balanced=balanced)
            selected = diverse_candidates(pool, 12)
            selected_ids = {int(row["name"]) for row in selected}
            result[condition][name] = {
                "recall_at_12": len(selected_ids & relevant) / len(relevant) if relevant else None,
                "relevant_sources": sorted(relevant),
                "selected_sources": sorted(selected_ids),
                "pool_distinct_sources": len({row["video_id"] for row in pool}),
                "query_ms": (time.perf_counter() - started) * 1000,
            }
    return result


def run(data, embeddings, output, split):
    records = json.loads((data / "manifest.json").read_text())["images"]
    metadata = json.loads((embeddings.parent / "results.json").read_text())
    if (
        metadata["status"] != "complete"
        or metadata["encoder"]["model"] != "google/gemini-embedding-2"
    ):
        raise ValueError("Use completed compatible COCO vectors")
    with np.load(embeddings) as cached:
        if list(cached["image_ids"]) != [row["id"] for row in records]:
            raise ValueError("Source/vector identity mismatch")
        vectors = cached["vectors"]
    if vectors.shape != (len(records), 768) or not np.isfinite(vectors).all():
        raise ValueError("Invalid cached vectors")
    indices = [i for i, record in enumerate(records) if record["split"] == split]
    documents, features = [records[i] for i in indices], vectors[indices]
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "split": split,
        "encoder": metadata["encoder"],
        "cases": [],
        "vectors_sha256": hashlib.sha256(embeddings.read_bytes()).hexdigest(),
        "policy": "four-per-source-round/known-session-minute-otherwise-video",
        "limitations": "Previously evaluated public COCO photos with unchanged cached vectors. Image-to-image category nomination under simulated repeated frames/timestamps, not fresh household/instance or text-query accuracy. No media files are represented as available; this experiment never verifies or answers from its metadata-only stores.",
    }
    for q in range(len(documents)):
        result["cases"].append(
            compare_pool(
                documents, features, q, output / f"query-{q:02d}", fingerprint=metadata["encoder"]
            )
        )
    result["summary"] = {}
    for condition in ["uncrowded", "crowded"]:
        result["summary"][condition] = {}
        for name in ["flat", "balanced"]:
            rows = [case[condition][name] for case in result["cases"]]
            result["summary"][condition][name] = {
                "queries": len(rows),
                "mean_recall_at_12": sum(r["recall_at_12"] for r in rows) / len(rows),
                "mean_pool_distinct_sources": sum(r["pool_distinct_sources"] for r in rows)
                / len(rows),
                "mean_query_ms": sum(r["query_ms"] for r in rows) / len(rows),
            }
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    args = parser.parse_args()
    result = run(args.data, args.embeddings, args.output, args.split)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
