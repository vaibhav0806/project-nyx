"""Compare two small existing Torchvision detectors at live-frame dimensions."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from PIL import Image
from torchvision.models.detection import (
    FasterRCNN_MobileNet_V3_Large_FPN_Weights,
    SSDLite320_MobileNet_V3_Large_Weights,
    fasterrcnn_mobilenet_v3_large_fpn,
    ssdlite320_mobilenet_v3_large,
)

from nyx.events import normalize_detections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.manifest.read_text())
    results = {
        "manifest": manifest,
        "method": "Same three selected images resized within 640x360; CPU; common score threshold 0.6. Counts are detection coverage, not accuracy.",
        "models": [],
    }
    for name, builder, weights in [
        (
            "ssdlite320_mobilenet_v3_large",
            ssdlite320_mobilenet_v3_large,
            SSDLite320_MobileNet_V3_Large_Weights.COCO_V1,
        ),
        (
            "fasterrcnn_mobilenet_v3_large_fpn",
            fasterrcnn_mobilenet_v3_large_fpn,
            FasterRCNN_MobileNet_V3_Large_FPN_Weights.COCO_V1,
        ),
    ]:
        started = time.perf_counter()
        model = builder(weights=weights, progress=False).eval().to("cpu")
        transform = weights.transforms()
        row = {
            "model": name,
            "weights": weights.url,
            "load_seconds": time.perf_counter() - started,
            "cases": [],
        }
        for case in manifest["cases"]:
            paths = sorted(Path(case["frames"]).glob("*.jpg"))
            chosen = [paths[index] for index in case["indices"]]
            images = [Image.open(path).convert("RGB") for path in chosen]
            for image in images:
                image.thumbnail((640, 360))
            started = time.perf_counter()
            with torch.inference_mode():
                predictions = model([transform(image) for image in images])
            boxes = [
                normalize_detections(
                    {key: value.tolist() for key, value in prediction.items()}, image.size
                )
                for image, prediction in zip(images, predictions, strict=True)
            ]
            item = {
                "name": case["name"],
                "files": [
                    {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                    for path in chosen
                ],
                "observations": boxes,
                "seconds": time.perf_counter() - started,
            }
            row["cases"].append(item)
            print(
                json.dumps(
                    {
                        "model": name,
                        "case": case["name"],
                        "counts": [len(x) for x in boxes],
                        "seconds": item["seconds"],
                    }
                ),
                flush=True,
            )
        results["models"].append(row)
        (args.output / "results.json").write_text(json.dumps(results, indent=2))
        del model


if __name__ == "__main__":
    main()
