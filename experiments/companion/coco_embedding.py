"""Opt-in bounded CC-BY COCO small-object embedding benchmark; no private-media discovery."""

import argparse
import hashlib
import json
import math
import re
import time
from collections import defaultdict
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from embedding_replay import budget_snapshot, check_budget, score_candidates
from PIL import Image

from nyx.perception import CloudEncoder
from nyx.retrieval import merge_candidates

ANNOTATIONS = (
    "https://huggingface.co/datasets/merve/coco/resolve/main/annotations/instances_val2017.json"
)
ANNOTATION_SHA = "e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f"
QUERIES = {
    75: ["a television remote control", "टीवी का रिमोट", "mera TV remote"],
    77: ["a mobile phone", "मोबाइल फोन", "mera mobile phone"],
    44: ["a bottle", "पानी की बोतल", "meri bottle"],
    47: ["a cup", "कॉफी का कप", "coffee wala cup"],
}


def select_records(data, per_category=10):
    if not 2 <= per_category <= 20:
        raise ValueError("Subset size must allow both splits within the download budget")
    images = {r["id"]: r for r in data["images"] if r["license"] == 4 and r["id"] != 39769}
    annotations = defaultdict(list)
    for row in data["annotations"]:
        annotations[row["image_id"]].append(row)
    used = set()
    records = []
    license_url = next(r["url"] for r in data["licenses"] if r["id"] == 4)
    for category in QUERIES:
        eligible = []
        for identifier, image in sorted(images.items()):
            if identifier in used:
                continue
            candidates = [
                a
                for a in annotations[identifier]
                if a["category_id"] == category
                and not a.get("iscrowd")
                and 0.001
                <= a["bbox"][2] * a["bbox"][3] / (image["width"] * image["height"])
                <= 0.02
                and a["bbox"][0] >= 0
                and a["bbox"][1] >= 0
                and a["bbox"][2] >= 1
                and a["bbox"][3] >= 1
            ]
            if candidates:
                eligible.append(
                    (identifier, image, max(candidates, key=lambda a: a["bbox"][2] * a["bbox"][3]))
                )
        if len(eligible) < per_category:
            raise ValueError("Insufficient distinct licensed small-object sources")
        for position, (identifier, image, annotation) in enumerate(eligible[:per_category]):
            if not re.fullmatch(r"\d{12}\.jpg", image["file_name"]):
                raise ValueError("Unexpected source filename")
            used.add(identifier)
            records.append(
                {
                    "id": identifier,
                    "group": f"coco-{identifier}",
                    "split": "development"
                    if position < min(per_category - 1, math.ceil(per_category * 0.6))
                    else "holdout",
                    "category": category,
                    "all_categories": sorted({a["category_id"] for a in annotations[identifier]}),
                    "file_name": image["file_name"],
                    "bbox": annotation["bbox"],
                    "width": image["width"],
                    "height": image["height"],
                    "license_id": 4,
                    "license_url": license_url,
                    "credit_url": image.get("flickr_url"),
                    "captured_at": None,
                }
            )
    return records


def download(url, limit):
    with urlopen(url, timeout=25) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError("Public download exceeded its byte budget")
    return body


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    annotations = root / "instances_val2017.json"
    if not annotations.exists():
        annotations.write_bytes(download(ANNOTATIONS, 25 * 1024**2))
    if hashlib.sha256(annotations.read_bytes()).hexdigest() != ANNOTATION_SHA:
        raise ValueError("Annotation revision changed")
    records = select_records(json.loads(annotations.read_text()))
    previous = (
        json.loads((root / "manifest.json").read_text())
        if (root / "manifest.json").exists()
        else None
    )
    if previous and [r["id"] for r in previous["images"]] != [r["id"] for r in records]:
        raise ValueError("Frozen source selection changed")
    saved = {r["id"]: r for r in previous["images"]} if previous else {}
    manifest = {
        "version": "coco-small-objects-v1",
        "annotations_sha256": ANNOTATION_SHA,
        "status": "downloading",
        "expected_images": len(records),
        "images": records,
    }
    total = 0
    seen = {}
    (root / "images").mkdir(exist_ok=True)
    for record in records:
        path = root / "images" / record["file_name"]
        record["source_url"] = (
            "https://huggingface.co/datasets/merve/coco/resolve/main/val2017/" + record["file_name"]
        )
        if not path.exists():
            path.write_bytes(download(record["source_url"], 2 * 1024**2))
        total += path.stat().st_size
        if total > 16 * 1024**2:
            raise ValueError("Photo subset exceeded its total byte budget")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        old = saved.get(record["id"], {}).get("sha256")
        if old and old != digest:
            raise ValueError("Cached source bytes changed")
        if digest in seen:
            raise ValueError("Duplicate source photos would leak between cases")
        seen[digest] = record["id"]
        record["sha256"] = digest
        with Image.open(path) as image:
            if image.size != (record["width"], record["height"]):
                raise ValueError("Source image dimensions differ from labels")
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    manifest.update(status="ready", photo_bytes=total)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return records


def ranked(documents, features, vector):
    scores = features @ vector
    return [
        {"id": documents[i]["id"], "similarity": float(scores[i])}
        for i in sorted(range(len(documents)), key=lambda i: (-scores[i], documents[i]["id"]))
    ]


def run(root, output, max_spend):
    records = prepare(root)
    encoder = CloudEncoder()
    if encoder.model != "google/gemini-embedding-2":
        raise ValueError("Use the measured Gemini embedding baseline")
    initial = budget_snapshot(encoder.client)
    check_budget(initial, initial["usage"], max_spend)
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "status": "running",
        "encoder": encoder.fingerprint,
        "budget_before": initial,
        "manifest_sha256": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(),
        "queries": [],
        "references": [],
        "timings": [],
        "limitations": "Category retrieval and same-photo crop matching on a small COCO subset; not cross-view household identity, final answer accuracy or live app latency.",
    }

    def checkpoint():
        result["provider_usage"] = encoder.client.usage
        (output / "results.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        )

    def call(label, operation, *args, **kwargs):
        check_budget(
            budget_snapshot(encoder.client),
            initial["usage"],
            max_spend,
            reported_cost=sum(u.get("cost") or 0 for u in encoder.client.usage),
        )
        start = time.perf_counter()
        before = len(encoder.client.usage)
        try:
            return operation(*args, **kwargs)
        finally:
            result["timings"].append(
                {
                    "label": label,
                    "elapsed_ms": round((time.perf_counter() - start) * 1000),
                    "provider_requests": len(encoder.client.usage) - before,
                }
            )
            checkpoint()

    try:
        vectors = []
        for start in range(0, len(records), 4):
            images = []
            for record in records[start : start + 4]:
                with Image.open(root / "images" / record["file_name"]) as image:
                    images.append(image.convert("RGB"))
            vectors.extend(call("index_photos", encoder.encode_images, images))
        features = np.asarray(vectors, dtype=np.float32)
        np.savez_compressed(
            output / "embeddings.npz", image_ids=[r["id"] for r in records], vectors=features
        )
        for split in ["development", "holdout"]:
            indices = [i for i, r in enumerate(records) if r["split"] == split]
            documents = [records[i] for i in indices]
            matrix = features[indices]
            for category, texts in QUERIES.items():
                relevant = {r["id"] for r in documents if category in r["all_categories"]}
                for text in texts:
                    for formatting, query in [
                        ("bare", text),
                        ("search_instruction", "task: search result | query: " + text),
                    ]:
                        vector = call("query_" + formatting, encoder.encode_text, query)
                        rows = ranked(documents, matrix, vector)
                        result["queries"].append(
                            {
                                "split": split,
                                "category": category,
                                "query": text,
                                "format": formatting,
                                "ranked_ids": [r["id"] for r in rows[:12]],
                                **score_candidates(rows[:12], relevant),
                            }
                        )
                        checkpoint()
                for record in [r for r in documents if r["category"] == category][:2]:
                    with Image.open(root / "images" / record["file_name"]) as image:
                        x, y, w, h = record["bbox"]
                        crop = image.convert("RGB").crop(
                            (int(x), int(y), math.ceil(x + w), math.ceil(y + h))
                        )
                    query = call("reference_text", encoder.encode_text, texts[0])
                    reference = call("reference_crop", encoder.encode_images, [crop])[0]
                    text_rows = ranked(documents, matrix, query)
                    image_rows = ranked(documents, matrix, reference)
                    for route, rows in [
                        ("text_only", text_rows[:12]),
                        ("text_and_reference", merge_candidates(text_rows, image_rows, 12)),
                    ]:
                        result["references"].append(
                            {
                                "split": split,
                                "category": category,
                                "target_image_id": record["id"],
                                "route": route,
                                "ranked_ids": [r["id"] for r in rows],
                                **score_candidates(rows, {record["id"]}),
                            }
                        )
                    checkpoint()
        result["status"] = "complete"
    except Exception as error:
        result.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        try:
            result["budget_after"] = budget_snapshot(encoder.client)
            result["run_spend_usd"] = result["budget_after"]["usage"] - initial["usage"]
        finally:
            checkpoint()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.15)
    args = parser.parse_args()
    result = run(args.data, args.output, args.max_spend)
    summary = {"status": result["status"], "run_spend_usd": result["run_spend_usd"]}
    for split in ["development", "holdout"]:
        summary[split] = {}
        for group, key in [("queries", "format"), ("references", "route")]:
            summary[split][group] = {}
            for variant in sorted({r[key] for r in result[group]}):
                rows = [r for r in result[group] if r["split"] == split and r[key] == variant]
                summary[split][group][variant] = {
                    "queries": len(rows),
                    "mean_recall_at_3": sum(r["recall_at_3"] for r in rows) / len(rows),
                    "mean_reciprocal_rank": sum(r["reciprocal_rank"] for r in rows) / len(rows),
                }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
