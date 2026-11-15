"""Paid public/synthetic still-video history workflow, separate from household accuracy."""

import argparse
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image

from experiments.companion.correction_replay import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from nyx.answers import history_steps
from nyx.capture import frame_image
from nyx.memory import Store
from nyx.perception import CloudEncoder
from nyx.verification import CloudVerifier

QUERIES = [
    (44, "a bottle"),
    (47, "a cup"),
    (75, "a television remote control"),
    (77, "a mobile phone"),
]


def consume(steps):
    while True:
        try:
            next(steps)
        except StopIteration as finished:
            return finished.value


def run(data, output, max_spend):
    manifest = json.loads((data / "manifest.json").read_text())
    records = [
        next(
            r
            for r in manifest["images"]
            if r["split"] == "development" and r["category"] == category
        )
        for category, _ in QUERIES
    ]
    output.mkdir(parents=True, exist_ok=False)
    client = BudgetedClient(max_spend, max_requests=96)
    encoder, verifier = CloudEncoder(client=client), CloudVerifier(client=client)
    clock = datetime.now(UTC) - timedelta(days=1)
    stores = {
        name: Store(output / name, encoder.fingerprint, encoder.dimensions)
        for name in ["positive", "negative"]
    }
    report = {
        "status": "running",
        "encoder": encoder.fingerprint,
        "verifier": verifier.fingerprint,
        "budget_before": client.initial,
        "source_manifest_sha256": hashlib.sha256((data / "manifest.json").read_bytes()).hexdigest(),
        "sources": [],
        "cases": [
            {"query": query, "category": category, "status": "not_run"}
            for category, query in QUERIES
        ]
        + [{"query": "a bottle", "negative": True, "status": "not_run"}],
        "limitations": "Four earlier-used public COCO development photos plus a generated blank scene. Generated still-video timestamps are simulated replay clocks; original photo capture times remain unknown. Candidate-category/source attribution, not instance identity, location wording, natural-video or household accuracy. Clarification and missed positives are reported separately.",
    }

    def checkpoint():
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")

    try:
        inputs = [(record, data / "images" / record["file_name"], "positive") for record in records]
        blank = output / "blank.png"
        Image.new("RGB", (640, 480), "gray").save(blank)
        inputs.append(
            ({"id": 999999999, "all_categories": [], "category": None}, blank, "negative")
        )
        for index, (record, original, group) in enumerate(inputs):
            store = stores[group]
            identifier = f"{record['id']:032x}"
            video = store.root / "recordings" / (identifier + ".mp4")
            video.parent.mkdir(exist_ok=True)
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-n",
                    "-loop",
                    "1",
                    "-i",
                    str(original),
                    "-t",
                    "2",
                    "-r",
                    "1",
                    "-vf",
                    "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(video),
                ],
                check=True,
                timeout=30,
            )
            image = frame_image(video, 0)
            features = encoder.encode_images([image])
            thumbnail = store.root / "frames" / (identifier + ".jpg")
            thumbnail.parent.mkdir(exist_ok=True)
            image.save(thumbnail, quality=90)
            at = (clock + timedelta(minutes=index)).isoformat()
            store.add_video(
                f"Synthetic replay of public image {record['id']}"
                if group == "positive"
                else "Generated empty scene",
                str(video.relative_to(store.root)),
                at,
                2,
                identifier,
            )
            store.add_frames(identifier, [(0, str(thumbnail.relative_to(store.root)))], features)
            store.finish_video(identifier)
            report["sources"].append(
                {
                    "video_id": identifier,
                    "image_id": record["id"],
                    "category": record["category"],
                    "all_categories": record["all_categories"],
                    "group": group,
                    "original_captured_at": None,
                    "simulated_replay_at": at,
                    "source_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
                }
            )
        for case in report["cases"]:
            store = stores["negative" if case.get("negative") else "positive"]
            began = time.perf_counter()
            result = consume(
                history_steps(
                    case["query"],
                    store,
                    encoder,
                    lambda: verifier,
                    semantic_latest=True,
                    mode="latest",
                )
            )
            evidence = result.get("evidence")
            selected = next(
                (
                    source
                    for source in report["sources"]
                    if evidence and source["video_id"] == evidence["video_id"]
                ),
                None,
            )
            if case.get("negative"):
                correct = result["status"] == "uncertain" and evidence is None
            else:
                correct = bool(
                    selected
                    and case["category"] in selected["all_categories"]
                    and evidence["offset_seconds"] == 0
                    and evidence["observed_at"] == selected["simulated_replay_at"]
                    and (store.root / evidence["video_path"]).is_file()
                )
            case.update(
                status="complete",
                correct=correct,
                outcome=result["status"],
                result=result,
                elapsed_ms=round((time.perf_counter() - began) * 1000),
            )
            checkpoint()
        report["status"] = "complete"
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError):
        report["status"] = "failed"
        raise
    finally:
        report["budget_after"] = budget_snapshot(client)
        report["run_spend_usd"] = report["budget_after"]["usage"] - client.initial["usage"]
        checkpoint()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.10)
    args = parser.parse_args()
    report = run(args.data, args.output, args.max_spend)
    print(
        json.dumps(
            {
                "status": report["status"],
                "cases": len(report["cases"]),
                "correct": sum(case.get("correct", False) for case in report["cases"]),
                "incomplete": sum(case["status"] != "complete" for case in report["cases"]),
                "run_spend_usd": report["run_spend_usd"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
