"""Replay labelled public frames through the real live API/model. No hardware/cloud."""

import argparse
import base64
import hashlib
import json
import platform
import time
from datetime import UTC, datetime
from importlib.metadata import version
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from PIL import Image

from nyx.app import create_app
from nyx.capture import extract_frames
from nyx.verification import LocalVerifier


def wait(client, identifier):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        job = client.get("/api/jobs/" + identifier).json()
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.1)
    raise TimeoutError("Local model job exceeded experiment budget")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument(
        "--full-clips",
        action="store_true",
        help="Replay complete sources, without selecting labelled excerpts",
    )
    parser.add_argument(
        "--hold-final-seconds",
        type=float,
        default=0,
        help="Synthetic repeated final image after the excerpt, to exercise pending-work drain; not additional source footage",
    )
    args = parser.parse_args()
    if not 0 <= args.hold_final_seconds <= 20:
        parser.error("Final-image hold must be between zero and twenty seconds")
    manifest = json.loads(args.manifest.read_text())
    cases = manifest["cases"]
    selected = [row for row in cases if row["name"] in args.cases]
    if len(selected) != len(set(args.cases)):
        parser.error("Every case name must exist in the manifest")
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "full_clips": args.full_clips,
        "synthetic_final_image_hold_seconds": args.hold_final_seconds,
        "platform": platform.platform(),
        "runtime": {
            name: version(name) for name in ["torch", "torchvision", "transformers", "pillow"]
        },
        "sources": [
            {
                "name": case["name"],
                "sha256": hashlib.sha256(
                    (Path(case["frames"]).parent / f"{case['name']}.mp4").read_bytes()
                ).hexdigest(),
            }
            for case in selected
        ],
    }
    (args.output / "protocol.json").write_text(json.dumps(protocol, indent=2))
    model = None
    generations = []

    def factory():
        nonlocal model
        if model is not None:
            return model
        model = LocalVerifier()
        original = model.generate_json

        def record(messages, max_tokens=240):
            raw = original(messages, max_tokens)
            generations.append(raw)
            return raw

        model.generate_json = record
        return model

    results = {
        "cases": [],
        "protocol": "Actual API clock; dense 0.1s requested decode, replay at actual decoded offsets",
        "synthetic_final_image_hold_seconds": args.hold_final_seconds,
        "full_clips": args.full_clips,
        "scope": "Actual decoded source offsets, complete clips"
        if args.full_clips
        else "Nominal two-second manifest indices locate development excerpts; replay clock is not original capture time",
    }
    for case in selected:
        with TestClient(
            create_app(
                args.output / "workspaces" / case["name"],
                verifier_factory=factory,
                voice_factory=lambda root: None,
            )
        ) as client:
            warm = client.post("/api/companion/warmup").json()
            assert wait(client, warm["id"])["status"] == "succeeded"
            results["model"] = model.fingerprint
            start_generation = len(generations)
            request = client.post(
                "/api/agent",
                json={
                    "message": "Remind me to take my water bottle when I leave",
                    "request_id": case["name"],
                },
            ).json()
            request_job = wait(client, request["id"])
            assert request_job["status"] == "succeeded", request_job
            assert request_job["result"]["status"] == "armed", request_job
            assert any(
                row["state"] == "armed" for row in client.get("/api/companion").json()["reminders"]
            ), "Scenario needs an armed request"
            session = client.post(
                "/api/capture/start", json={"at": datetime.now(UTC).isoformat()}
            ).json()
            source = Path(case["frames"]).parent / f"{case['name']}.mp4"
            lower = 0 if args.full_clips else max(0, min(case["indices"]) * 2 - 1)
            upper = float("inf") if args.full_clips else max(case["indices"]) * 2 + 3
            jobs = []
            completed = {}
            gaps = []
            with TemporaryDirectory(prefix="nyx-live-replay-") as folder:
                frames = [
                    (at, path)
                    for at, path in extract_frames(source, Path(folder) / "frames", 0.1)
                    if lower <= at <= upper
                ]
                if not frames:
                    raise ValueError("No frames in the requested development excerpt")
                started = time.monotonic()
                replay_started_at = datetime.now(UTC)
                previous = None
                replay = [(offset, offset, path, False) for offset, path in frames]
                last_offset, last_path = frames[-1]
                replay.extend(
                    (last_offset + tick / 10, last_offset, last_path, True)
                    for tick in range(1, int(args.hold_final_seconds * 10) + 1)
                )
                admissions = []
                for offset, source_offset, path, repeated in replay:
                    delay = started + offset - frames[0][0] - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    with Image.open(path) as opened:
                        image = opened.convert("RGB")
                    image.thumbnail((640, 360))
                    encoded = BytesIO()
                    image.save(encoded, format="JPEG")
                    observed_at = datetime.now(UTC)
                    if previous is not None:
                        gaps.append((observed_at - previous).total_seconds())
                    previous = observed_at
                    response = client.post(
                        "/api/observe",
                        json={
                            "session_id": session["id"],
                            "captured_at": observed_at.isoformat(),
                            "image": base64.b64encode(encoded.getvalue()).decode(),
                        },
                    )
                    assert response.status_code in {200, 202}, response.text
                    if response.status_code == 202:
                        jobs.append(response.json()["id"])
                        admissions.append(
                            {
                                "job_id": response.json()["id"],
                                "admitted_at": observed_at.isoformat(),
                                "source_offset_at_admission": source_offset,
                                "synthetic_repetition": repeated,
                            }
                        )
                    # Preserve completed jobs before the bounded runtime job list evicts them.
                    for identifier in jobs:
                        if identifier in completed:
                            continue
                        job = client.get("/api/jobs/" + identifier).json()
                        if job["status"] in {"succeeded", "failed"}:
                            completed[identifier] = {
                                **job,
                                "completion_observed_at": datetime.now(UTC).isoformat(),
                            }
            outcomes = [
                completed.get(identifier)
                or {
                    **wait(client, identifier),
                    "completion_observed_at": datetime.now(UTC).isoformat(),
                }
                for identifier in jobs
            ]
            status = client.get("/api/companion").json()
            notifications = [
                {
                    **delivery,
                    "available_source_offset": frames[0][0]
                    + (
                        datetime.fromisoformat(job["completion_observed_at"]) - replay_started_at
                    ).total_seconds(),
                }
                for job in outcomes
                for delivery in job.get("result", {}).get("deliveries", [])
            ]
            row = {
                **case,
                "request": request_job,
                "observations": outcomes,
                "source_offsets": [at for at, _ in frames],
                "replay_started_at": replay_started_at.isoformat(),
                "admissions": admissions,
                "maximum_replay_gap_seconds": max(gaps, default=0),
                "seconds_since_final_frame": (datetime.now(UTC) - observed_at).total_seconds(),
                "reminders": status["reminders"],
                "pending": status["pending"],
                "notifications": notifications,
                "generations": generations[start_generation:],
            }
            results["cases"].append(row)
            (args.output / "results.json").write_text(json.dumps(results, indent=2))
            print(
                json.dumps(
                    {
                        "name": case["name"],
                        "jobs": len(outcomes),
                        "statuses": [job["status"] for job in outcomes],
                        "judgments": [job.get("result", {}).get("judgment") for job in outcomes],
                        "pending_notifications": len(status["pending"]),
                        "total_notifications": len(notifications),
                        "maximum_replay_gap_seconds": row["maximum_replay_gap_seconds"],
                    }
                ),
                flush=True,
            )
            for task in status["reminders"]:
                if task["state"] in {"armed", "pending", "delivering"}:
                    client.delete("/api/reminders/" + task["id"])
            client.post(
                f"/api/capture/{session['id']}/state",
                json={
                    "state": "stopped",
                    "at": datetime.now(UTC).isoformat(),
                    "reason": "Synthetic replay complete",
                },
            ).raise_for_status()


if __name__ == "__main__":
    main()
