"""Physical-object versus embedded-picture diagnostic on permitted public/synthetic scenes."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from experiments.companion.correction_replay import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.visual_cases import QUERIES, score
from nyx.verification import CloudVerifier


def prepare(data, output):
    output.mkdir(parents=True, exist_ok=False)
    source = json.loads((data / "manifest.json").read_text())
    annotations = json.loads((data / "instances_val2017.json").read_text())["annotations"]
    rows = []
    for split in ["development", "holdout"]:
        for category, query in QUERIES.items():
            record = next(
                row
                for row in source["images"]
                if row["split"] == split and row["category"] == category
            )
            original = data / "images" / record["file_name"]
            if hashlib.sha256(original.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError("Source identity changed")
            count = sum(
                r["image_id"] == record["id"] and r["category_id"] == category for r in annotations
            )
            with Image.open(original) as image:
                for condition in ["original", "monitor", "poster"]:
                    if condition == "original":
                        fixture = image.copy()
                    else:
                        fixture = Image.new("RGB", (800, 600), "#c9c3b8")
                        draw = ImageDraw.Draw(fixture)
                        if condition == "monitor":
                            draw.rectangle((0, 510, 800, 600), fill="#74513e")
                            draw.rectangle((65, 35, 735, 465), fill="#16181b")
                            draw.rectangle((365, 465, 435, 510), fill="#313238")
                            draw.rectangle((300, 505, 500, 520), fill="#313238")
                            content = ImageOps.contain(image.convert("RGB"), (630, 390))
                            fixture.paste(
                                content,
                                ((800 - content.width) // 2, 55 + (390 - content.height) // 2),
                            )
                        else:
                            draw.rectangle(
                                (105, 50, 695, 530), fill="white", outline="#777777", width=2
                            )
                            content = ImageOps.contain(image.convert("RGB"), (550, 400))
                            fixture.paste(
                                content,
                                ((800 - content.width) // 2, 85 + (400 - content.height) // 2),
                            )
                    identifier = f"{record['id']}-{condition}"
                    path = output / (identifier + ".jpg")
                    fixture.save(path, quality=95)
                    rows.append(
                        {
                            "id": identifier,
                            "split": split,
                            "category": category,
                            "query": query,
                            "condition": condition,
                            "source_id": record["id"],
                            "source_sha256": record["sha256"],
                            "source_count": count,
                            "file": path.name,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "expected": "single"
                            if condition == "original" and count == 1
                            else "ambiguous"
                            if condition == "original"
                            else "absent",
                        }
                    )
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "cases": rows,
                "limitations": "Eight previously used public sources, source-separated synthetic condition split. Original annotation counts remain proxy controls. Monitor/poster composites contain depictions only, no physical target in the outer scene. Generated contexts and source timestamps unknown; not natural household accuracy.",
            },
            indent=2,
        )
        + "\n"
    )
    return {"cases": len(rows)}


class AuditVerifier(CloudVerifier):
    last_primary = None

    def confirm_positive(self, image, object_query, judgment):
        self.last_primary = judgment
        return super().confirm_positive(image, object_query, judgment)


def run(data, output, split, max_spend):
    manifest = json.loads((data / "manifest.json").read_text())
    cases = [row for row in manifest["cases"] if row["split"] == split]
    output.mkdir(parents=True, exist_ok=False)
    client = BudgetedClient(max_spend, max_requests=48)
    verifier = AuditVerifier(client=client, model="google/gemini-3.5-flash")
    if not verifier.visual_confirmation:
        raise ValueError("Set NYX_VISUAL_CONFIRMATION=1 for this selected-route diagnostic")
    report = {
        "status": "running",
        "model": verifier.fingerprint,
        "budget_before": client.initial,
        "cases": [{**case, "status": "not_run", "correct": False} for case in cases],
        "manifest_sha256": hashlib.sha256((data / "manifest.json").read_bytes()).hexdigest(),
        "limitations": manifest["limitations"],
    }

    def checkpoint():
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")

    checkpoint()
    try:
        for row in report["cases"]:
            path = (data / row["file"]).resolve()
            if (
                not path.is_relative_to(data.resolve())
                or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]
            ):
                raise ValueError("Fixture identity changed")
            verifier.last_primary = None
            began = time.perf_counter()
            with Image.open(path) as image:
                judgment = verifier.inspect(image, row["query"])
            row.update(
                status="complete",
                judgment=judgment,
                primary_judgment=verifier.last_primary or judgment,
                elapsed_ms=round((time.perf_counter() - began) * 1000),
                **score(row["expected"], judgment),
            )
            checkpoint()
        report["status"] = "complete"
    finally:
        if report["status"] != "complete":
            report["status"] = "failed"
        report["budget_after"] = budget_snapshot(client)
        checkpoint()
    return {
        "correct": sum(r["correct"] for r in report["cases"]),
        "total": len(cases),
        "incomplete": sum(r["status"] != "complete" for r in report["cases"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--max-spend", type=float, default=0.15)
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(args.data, args.output)
            if args.prepare
            else run(args.data, args.output, args.split, args.max_spend)
        )
    )
