"""Guarded public/synthetic shown-item → durable report → later recall API workflows."""

import argparse
import base64
import hashlib
import json
import re
import subprocess
import time
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from nyx.capture import frame_image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_cases(cases):
    seen, groups = set(), {}
    for row in cases:
        if not re.fullmatch(r"[a-z0-9-]{1,80}", row["id"]) or row["id"] in seen:
            raise ValueError("Duplicate/invalid case identity")
        if row["split"] not in {"development", "holdout"} or not row["sources"]:
            raise ValueError("Invalid split/source group")
        for source in row["sources"]:
            if source in groups:
                raise ValueError("Source reuse leaks workflow groups")
            groups[source] = row["split"]
        seen.add(row["id"])
        expected = row["expected_report"]
        if expected is not None and (
            type(expected) is not int or not 0 <= expected < len(row["messages"])
        ):
            raise ValueError("Invalid expected report")
    return cases


def score_recall(result, expected):
    matches = [
        m
        for o in (result or {}).get("observations", [])
        if o.get("kind") == "statements"
        for m in o.get("matches", [])
    ]
    selected = {m["turn_id"] for m in matches}
    attributed = (
        all("transcript:" + identifier in result.get("sources", []) for identifier in selected)
        if result
        else False
    )
    negative = bool(
        result
        and (
            result.get("status") in {"clarify", "uncertain"}
            or any(
                o.get("kind") == "reference" and o.get("status") == "clarify"
                for o in result.get("observations", [])
            )
        )
    )
    return {
        "correct": bool(
            result
            and result.get("answer")
            and selected == set(expected)
            and attributed
            and (bool(expected) or negative)
        ),
        "selected": sorted(selected),
        "expected": list(expected),
        "attributed": attributed,
    }


def score_setup(case, identifiers, linked, edges):
    if case["expected_report"] is None:
        return not linked
    records = {row["turn_id"]: row for row in linked}
    for identifier in identifiers:
        row = records.get(identifier)
        if not row or row["kind"] != case["kind"]:
            return False
        resolver = row.get("resolver", {})
        resolver = json.loads(resolver) if isinstance(resolver, str) else resolver
        source = resolver.get("reference", {}).get("source")
        if source != "visual" and not (
            source == "prior_statement"
            and any(
                edge["replacement_turn_id"] == identifier
                and edge["previous_turn_id"] in identifiers
                for edge in edges
            )
        ):
            return False
    return not case.get("correction") or any(
        edge["previous_turn_id"] == identifiers[0] and edge["replacement_turn_id"] == identifiers[1]
        for edge in edges
    )


def prepare(data, cases_path, output):
    cases = validate_cases(json.loads(cases_path.read_text())["cases"])
    source = json.loads((data / "manifest.json").read_text())
    if digest(data / "instances_val2017.json") != source["annotations_sha256"]:
        raise ValueError("Annotation revision differs")
    records = {row["id"]: row for row in source["images"]}
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "recipe_version": 1,
        "cases_sha256": digest(cases_path),
        "cases": [],
        "limitations": "Edited crops of permitted public photos, two shown frames then blank. Known crop provenance is not natural household placement/identity accuracy. Original photo capture times unknown; API window clocks are simulated replay times.",
    }
    for case in cases:
        crops = []
        for identifier in case["sources"]:
            record = records[identifier]
            path = data / "images" / record["file_name"]
            if digest(path) != record["sha256"]:
                raise ValueError("Public source bytes changed")
            with Image.open(path) as image:
                x, y, w, h = record["bbox"]
                box = (
                    max(0, x - 0.15 * w),
                    max(0, y - 0.15 * h),
                    min(image.width, x + 1.15 * w),
                    min(image.height, y + 1.15 * h),
                )
                crops.append(
                    ImageOps.contain(
                        image.crop(box).convert("RGB"),
                        (260 if len(case["sources"]) > 1 else 480, 360),
                    )
                )
        shown = Image.new("RGB", (640, 480), "#c0bcb4")
        for i, crop in enumerate(crops):
            center = 320 if len(crops) == 1 else 160 + i * 320
            shown.paste(crop, (center - crop.width // 2, (480 - crop.height) // 2))
        directory = output / case["id"]
        directory.mkdir()
        for i in range(3):
            (shown if i < 2 else Image.new("RGB", (640, 480), "#c0bcb4")).save(
                directory / f"{i:03}.png"
            )
        video = directory / "shown.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-n",
                "-framerate",
                "1",
                "-i",
                str(directory / "%03d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(video),
            ],
            check=True,
            timeout=30,
        )
        manifest["cases"].append(
            {
                "id": case["id"],
                "video": str(video.relative_to(output)),
                "sha256": digest(video),
                "sources": [
                    {
                        "id": n,
                        "sha256": records[n]["sha256"],
                        "bbox": records[n]["bbox"],
                        "license_url": records[n]["license_url"],
                        "captured_at": None,
                    }
                    for n in case["sources"]
                ],
            }
        )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"prepared": len(cases)}


def encoded(image):
    out = BytesIO()
    image.save(out, format="JPEG", quality=90)
    return base64.b64encode(out.getvalue()).decode()


def request_turn(
    root,
    encoder,
    verifier,
    message,
    images=None,
    *,
    initial_action=None,
    offsets=None,
    client=None,
    voice_turn_id=None,
    context_at=None,
    headers=None,
):
    from fastapi.testclient import TestClient

    from nyx.app import create_app

    body = {
        "message": message,
        "request_id": __import__("uuid").uuid4().hex,
        "timezone": "Asia/Kolkata",
    }
    if initial_action is not None:
        body["initial_action"] = initial_action
    if voice_turn_id is not None:
        body["voice_turn_id"] = voice_turn_id
    if images:
        offsets = offsets if offsets is not None else list(range(len(images)))
        if (
            len(offsets) != len(images)
            or offsets != sorted(offsets)
            or offsets[-1] - offsets[0] > 15
        ):
            raise ValueError("Invalid source window offsets")
        clock = datetime.fromisoformat(context_at) if context_at else datetime.now(UTC)
        body.update(
            context_at=clock.isoformat(),
            visual_frames=[
                {
                    "snapshot": encoded(image),
                    "captured_at": (
                        clock - timedelta(seconds=offsets[-1] - offsets[i])
                    ).isoformat(),
                }
                for i, image in enumerate(images)
            ],
        )
    session = (
        nullcontext(client)
        if client is not None
        else TestClient(
            create_app(
                root,
                encoder_factory=lambda: encoder,
                verifier_factory=lambda: verifier,
                voice_factory=lambda root: None,
            )
        )
    )
    with session as api:
        response = api.post("/api/agent", json=body, headers=headers)
        response.raise_for_status()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            job = api.get("/api/jobs/" + response.json()["id"]).json()
            if job["status"] in {"succeeded", "failed"}:
                return job
            time.sleep(0.05)
        raise ValueError("Household workflow timed out")


def run(data, cases_path, output, split, max_spend, case_id=None):
    from experiments.companion.correction_replay import BudgetedClient
    from experiments.companion.embedding_replay import budget_snapshot
    from nyx.perception import CloudEncoder
    from nyx.statements import Statements
    from nyx.verification import CloudVerifier
    from nyx.voice import Conversations

    cases = validate_cases(json.loads(cases_path.read_text())["cases"])
    manifest = json.loads((data / "manifest.json").read_text())
    if manifest["cases_sha256"] != digest(cases_path):
        raise ValueError("Frozen cases changed")
    assets = {r["id"]: r for r in manifest["cases"]}
    chosen = [c for c in cases if c["split"] == split and (case_id is None or c["id"] == case_id)]
    if not chosen:
        raise ValueError("No frozen workflows match this selection")
    for case in cases:
        path = (data / assets[case["id"]]["video"]).resolve()
        if not path.is_relative_to(data.resolve()) or digest(path) != assets[case["id"]]["sha256"]:
            raise ValueError("Video provenance differs")
    output.mkdir(parents=True, exist_ok=False)

    class AuditedClient(BudgetedClient):
        def __init__(self):
            super().__init__(max_spend, max_requests=96)
            self.generations = []

        def generate(self, messages, model, max_tokens, **kwargs):
            raw = super().generate(messages, model, max_tokens, **kwargs)
            self.generations.append(
                {
                    "model": model,
                    "schema_fields": list((kwargs.get("schema") or {}).get("properties", {})),
                    "response": raw,
                }
            )
            return raw

    client = AuditedClient()
    encoder = CloudEncoder(client)
    verifier = CloudVerifier(client)
    report = {
        "status": "running",
        "scorer_version": 2,
        "split": split,
        "case_filter": case_id,
        "cases_sha256": digest(cases_path),
        "fixture_manifest_sha256": digest(data / "manifest.json"),
        "verifier": verifier.fingerprint,
        "encoder": encoder.fingerprint,
        "budget_before": client.initial,
        "cases": [{**c, "status": "not_run", "correct": False, "stages": []} for c in chosen],
        "limitations": manifest["limitations"],
    }

    def checkpoint():
        report["provider_usage"] = client.usage
        (output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )

    checkpoint()
    try:
        for row in report["cases"]:
            row["status"] = "running"
            root = output / row["id"]
            video = data / assets[row["id"]]["video"]
            offsets = assets[row["id"]].get("offsets", [0, 1, 2])
            images = [frame_image(video, offset) for offset in offsets]
            ids = []
            for message in row["messages"]:
                start = len(client.generations)
                job = request_turn(root, encoder, verifier, message, images, offsets=offsets)
                row["stages"].append(
                    {"phase": "save", "job": job, "generations": client.generations[start:]}
                )
                checkpoint()
                if job["status"] != "succeeded":
                    raise ValueError("Save stage failed; inspect before further spending")
                ids.append(job["result"]["turn_id"])
            conversations = Conversations(root)
            Statements(conversations)
            with conversations.connect() as db:
                linked = [
                    dict(x) for x in db.execute("SELECT turn_id,kind,resolver FROM statements")
                ]
                edges = [
                    dict(x)
                    for x in db.execute(
                        "SELECT previous_turn_id,replacement_turn_id FROM statement_corrections"
                    )
                ]
            row["linked"] = [{**x, "resolver": json.loads(x["resolver"] or "{}")} for x in linked]
            row["corrections"] = edges
            for n in range(32):
                filler = conversations.begin(f"Unrelated conversation number {n}", {})
                conversations.finish(filler, "Okay.")
            start = len(client.generations)
            recall_offsets = assets[row["id"]].get("recall_offsets", offsets[:2])
            recall_images = [frame_image(video, offset) for offset in recall_offsets]
            job = request_turn(
                root, encoder, verifier, row["query"], recall_images, offsets=recall_offsets
            )
            row["stages"].append(
                {"phase": "recall", "job": job, "generations": client.generations[start:]}
            )
            expected = [] if row["expected_report"] is None else [ids[row["expected_report"]]]
            row["recall_score"] = score_recall(job.get("result"), expected)
            setup = score_setup(row, ids, linked, edges)
            row.update(
                status="complete" if job["status"] == "succeeded" else "failed",
                correct=bool(setup and row["recall_score"]["correct"]),
                setup_correct=setup,
            )
            checkpoint()
        report["status"] = "complete"
    finally:
        if report["status"] != "complete":
            report["status"] = "failed"
        report["budget_after"] = budget_snapshot(client)
        checkpoint()
    return {
        "status": report["status"],
        "complete": sum(r["status"] == "complete" for r in report["cases"]),
        "correct": sum(r["correct"] for r in report["cases"]),
        "total": len(report["cases"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_suffix(".json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--split", choices=["development", "holdout"], default="development")
    parser.add_argument("--max-spend", type=float, default=0.20)
    parser.add_argument("--case-id", help="Replay one existing frozen case as a diagnostic")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(args.data, args.cases, args.output)
            if args.prepare
            else run(args.data, args.cases, args.output, args.split, args.max_spend, args.case_id)
        )
    )
