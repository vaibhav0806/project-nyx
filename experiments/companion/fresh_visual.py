"""Prepare a small new licensed public source split, without models or private-media discovery."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.request import urlopen

from PIL import Image

from experiments.companion.visual_cases import build_cases

ANNOTATION_SHA = "e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_ids(value):
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"id", "image_id", "source_id"} and type(item) is int:
                found.add(item)
            if key == "sources" and isinstance(item, list):
                found.update(n for n in item if type(n) is int)
            found.update(public_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(public_ids(item))
    return found


def prepare(annotations, existing, recipe_path, output, cases_path):
    if digest(annotations) != ANNOTATION_SHA:
        raise ValueError("Annotation version changed")
    recipe = json.loads(recipe_path.read_text())
    exclusions, snapshots = set(), []
    for path in sorted(existing.rglob("manifest.json")):
        exclusions.update(public_ids(json.loads(path.read_text())))
        snapshots.append({"manifest": str(path.relative_to(existing)), "sha256": digest(path)})
    if any(row["id"] in exclusions for row in recipe["images"]):
        raise ValueError("Frozen fresh source already appears in an earlier public manifest")
    metadata = json.loads(annotations.read_text())
    images = {row["id"]: row for row in metadata["images"]}
    license_url = next(row["url"] for row in metadata["licenses"] if row["id"] == 4)
    records = []
    for chosen in recipe["images"]:
        image = images[chosen["id"]]
        if image["license"] != 4 or not re.fullmatch(r"\d{12}\.jpg", image["file_name"]):
            raise ValueError("Unexpected source license/name")
        records.append(
            {
                **chosen,
                "file_name": image["file_name"],
                "width": image["width"],
                "height": image["height"],
                "license_url": license_url,
                "credit_url": image.get("flickr_url"),
                "captured_at": None,
                "source_url": "https://huggingface.co/datasets/merve/coco/resolve/main/val2017/"
                + image["file_name"],
            }
        )
    output.mkdir(parents=True, exist_ok=False)
    (output / "images").mkdir()
    manifest = {
        "version": 1,
        "status": "downloading",
        "annotations_sha256": ANNOTATION_SHA,
        "recipe_sha256": digest(recipe_path),
        "excluded_manifest_snapshots": snapshots,
        "images": records,
        "limitations": "New against recorded public evaluation manifests, not unseen model training data. Category/count annotation proxies can omit/occlude objects; no physical identity, natural-video, speech or household accuracy claim. Original photo times unknown. CC-BY license/credit links retained; no demo/public redistribution in this pass.",
    }
    shutil.copyfile(annotations, output / "instances_val2017.json")
    total = 0
    for record in records:
        with urlopen(record["source_url"], timeout=25) as response:
            body = response.read(2 * 1024**2 + 1)
        total += len(body)
        if len(body) > 2 * 1024**2 or total > 16 * 1024**2:
            raise ValueError("Public photo download budget exceeded")
        path = output / "images" / record["file_name"]
        path.write_bytes(body)
        with Image.open(path) as photo:
            if photo.size != (record["width"], record["height"]):
                raise ValueError("Source dimensions differ from frozen labels")
            photo.verify()
        record["sha256"] = digest(path)
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    cases = build_cases(records, metadata["annotations"])
    with cases_path.open("x") as handle:
        json.dump(
            {"version": 1, "recipe_sha256": digest(recipe_path), "cases": cases}, handle, indent=2
        )
        handle.write("\n")
    manifest.update(status="ready", photo_bytes=total, cases_sha256=digest(cases_path))
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {
        "images": len(records),
        "conditions": len(cases),
        "photo_bytes": total,
        "cases_sha256": digest(cases_path),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--existing", type=Path, required=True)
    parser.add_argument(
        "--recipe", type=Path, default=Path(__file__).with_name("visual_fresh_sources.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(prepare(args.annotations, args.existing, args.recipe, args.output, args.cases))
    )
