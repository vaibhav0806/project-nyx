"""Offline freshness stress test using cached COCO vectors and explicitly synthetic ages."""

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from experiments.companion.embedding_replay import score_candidates
from nyx.memory_policy import memory_priority


def run(data, embeddings, output):
    manifest = json.loads((data / "manifest.json").read_text())
    metadata = json.loads((embeddings.parent / "results.json").read_text())
    if (
        metadata["status"] != "complete"
        or metadata["encoder"]["model"] != "google/gemini-embedding-2"
    ):
        raise ValueError("Use the completed compatible COCO embedding artifact")
    records = manifest["images"]
    with np.load(embeddings) as cached:
        if list(cached["image_ids"]) != [r["id"] for r in records]:
            raise ValueError("Embedding/source identity mismatch")
        features = cached["vectors"]
    if features.shape != (len(records), 768) or not np.isfinite(features).all():
        raise ValueError("Invalid cached vector matrix")
    now = datetime(2026, 11, 15, 12, tzinfo=UTC)
    results = {
        "encoder": metadata["encoder"],
        "source_sha256": hashlib.sha256(embeddings.read_bytes()).hexdigest(),
        "clock": now.isoformat(),
        "selected_weight": 0,
        "limitations": "Image-to-image category retrieval with invented age schedules; these are not capture timestamps, natural report chronology, or household accuracy. This stress test cannot justify promoting recency weights.",
        "comparisons": [],
    }
    for split in ["development", "holdout"]:
        indices = [i for i, r in enumerate(records) if r["split"] == split]
        for chronology in ["relevant_old", "relevant_new", "mixed"]:
            for intent in ["current", "historical"]:
                for half_life in [1, 3, 7, 30]:
                    for weight in [0, 0.25, 0.5]:
                        queries = []
                        for q in indices:
                            candidates = []
                            relevant = set()
                            for i in indices:
                                if i == q:
                                    continue
                                target = records[q]["category"] in records[i]["all_categories"]
                                age = (
                                    (9 if target else 0.01)
                                    if chronology == "relevant_old"
                                    else (0.01 if target else 9)
                                )
                                if chronology == "mixed":
                                    age = records[i]["id"] % 10
                                at = (
                                    None
                                    if i % 11 == 0
                                    else now - timedelta(days=-1 if i % 13 == 0 else age)
                                )
                                if intent == "historical" and at is None:
                                    continue
                                policy = memory_priority(
                                    float(np.dot(features[q], features[i])),
                                    at,
                                    now=now,
                                    half_life_days=half_life,
                                    recency_weight=weight,
                                    intent=intent,
                                )
                                if policy["eligible"]:
                                    candidates.append(
                                        {"id": records[i]["id"], "priority": policy["priority"]}
                                    )
                                    if target:
                                        relevant.add(records[i]["id"])
                            candidates.sort(key=lambda r: (-r["priority"], r["id"]))
                            queries.append(
                                {
                                    "query_image": records[q]["id"],
                                    "top_ids": [r["id"] for r in candidates[:3]],
                                    **score_candidates(candidates, relevant),
                                }
                            )
                        positives = [r for r in queries if r["positive"]]
                        results["comparisons"].append(
                            {
                                "split": split,
                                "chronology": chronology,
                                "intent": intent,
                                "half_life_days": half_life,
                                "weight": weight,
                                "queries": queries,
                                "mean_recall_at_3": sum(r["recall_at_3"] for r in positives)
                                / len(positives),
                                "mean_reciprocal_rank": sum(r["reciprocal_rank"] for r in positives)
                                / len(positives),
                            }
                        )
    output.mkdir(parents=True, exist_ok=False)
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.data, args.embeddings, args.output)
    print(
        json.dumps(
            {
                "comparisons": len(result["comparisons"]),
                "selected_weight": 0,
                "provider_requests": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
