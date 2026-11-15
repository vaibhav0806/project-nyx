"""Pinned category/count proxy labels, independent of runtime inference."""

from collections import Counter

QUERIES = {44: "a bottle", 47: "a cup", 75: "a remote control", 77: "a mobile phone"}


def build_cases(records, annotations):
    counts = Counter((row["image_id"], row["category_id"]) for row in annotations)
    seen, hashes, cases = set(), set(), []
    for record in records:
        if record["id"] in seen or record["sha256"] in hashes:
            raise ValueError("Duplicate source could leak across splits")
        seen.add(record["id"])
        hashes.add(record["sha256"])
        category = record["category"]
        negative = next((c for c in QUERIES if not counts[record["id"], c]), None)
        if negative is None:
            raise ValueError("Source has no eligible annotated-negative category")
        for target in [category, negative]:
            count = counts[record["id"], target]
            cases.append(
                {
                    "id": f"coco-{record['id']}-{target}",
                    "image_id": record["id"],
                    "file_name": record["file_name"],
                    "sha256": record["sha256"],
                    "split": record["split"],
                    "query": QUERIES[target],
                    "category": target,
                    "annotated_count": count,
                    "expected": "single" if count == 1 else "ambiguous" if count > 1 else "absent",
                }
            )
    return cases


def score(expected, judgment):
    if not isinstance(judgment, dict):
        return {"correct": False, "unsafe_positive": False}
    visible = judgment.get("visibility") == "visible"
    if expected == "single":
        correct = visible and bool(judgment.get("location"))
    elif expected == "absent":
        correct = judgment.get("visibility") in {"not_visible", "uncertain"}
    elif expected == "ambiguous":
        correct = judgment.get("visibility") == "uncertain"
    else:
        raise ValueError("Unknown proxy label")
    return {"correct": correct, "unsafe_positive": visible and expected != "single"}
