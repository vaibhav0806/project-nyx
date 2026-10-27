"""Small real-model object flow using the existing public-image synthetic video."""

import argparse
import base64
import json
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import mlx.core as mx
from fastapi.testclient import TestClient
from PIL import Image

from nyx.app import create_app
from nyx.verification import LocalVerifier


def wait(client, identifier):
    until = time.monotonic() + 90
    while time.monotonic() < until:
        job = client.get("/api/jobs/" + identifier).json()
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.1)
    raise TimeoutError("MVP job exceeded 90 seconds")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--review-history",
        action="store_true",
        help="Simulate review using known fixture provenance; not a recognition score",
    )
    parser.add_argument(
        "--current-only",
        action="store_true",
        help="Check current view and correction without indexing or historical retrieval",
    )
    parser.add_argument(
        "--acceptance",
        action="store_true",
        help="Score finding, conversational rejection and task switching",
    )
    parser.add_argument(
        "--negative-only",
        action="store_true",
        help="Check an empty synthetic view through the actual inspection API",
    )
    args = parser.parse_args()
    if args.negative_only and (args.acceptance or args.review_history or args.current_only):
        parser.error("--negative-only cannot be combined with other flow modes")
    if args.acceptance:
        args.review_history = True
    if args.review_history and args.current_only:
        parser.error("History review requires the history turn")
    args.output.mkdir(parents=True, exist_ok=False)
    mx.set_memory_limit(6 * 1024**3)
    mx.set_cache_limit(128 * 1024**2)
    model = None

    def factory():
        nonlocal model
        if model is None:
            model = LocalVerifier()
        return model

    results = {
        "scope": "Real local API/models, public-image synthetic video, simulated recording dates; no devices or voice",
        "current_only": args.current_only,
        "cases": [],
    }
    with TestClient(
        create_app(
            args.output / "workspace",
            device="cpu",
            verifier_factory=factory,
            voice_factory=lambda root: None,
        )
    ) as client:
        if args.negative_only:
            pixels = BytesIO()
            Image.new("RGB", (320, 240), "white").save(pixels, format="PNG")
            started = time.perf_counter()
            response = client.post(
                "/api/inspect",
                params={
                    "object_query": "television remote control",
                    "captured_at": datetime.now(UTC).isoformat(),
                },
                content=pixels.getvalue(),
            )
            response.raise_for_status()
            job = wait(client, response.json()["id"])
            result = job.get("result", {})
            passed = (
                job["status"] == "succeeded"
                and result.get("status") == "uncertain"
                and not result.get("judgment", {}).get("location")
            )
            report = {
                "scope": "Synthetic blank image through real local inspection API; not household absence accuracy",
                "passed": passed,
                "seconds": time.perf_counter() - started,
                "job": job,
                "model": model.fingerprint if model else None,
                "mlx_peak_bytes": mx.get_peak_memory(),
            }
            (args.output / "results.json").write_text(json.dumps(report, indent=2))
            print(
                json.dumps(
                    {"passed": passed, "answer": result.get("answer"), "seconds": report["seconds"]}
                ),
                flush=True,
            )
            if not passed:
                raise SystemExit(1)
            return
        imports = [] if args.current_only else [("old", 240), ("recent", 1)]
        video = (args.fixture / "scenes.mp4").read_bytes() if imports else None
        for name, hours in imports:
            response = client.post(
                "/api/import",
                params={
                    "name": name + ".mp4",
                    "recorded_at": (datetime.now(UTC) - timedelta(hours=hours)).isoformat(),
                },
                content=video,
            )
            response.raise_for_status()
            job = wait(client, response.json()["id"])
            assert job["status"] == "succeeded", job
        cases = [
            ("current", "Where is the television remote control?", True),
            ("correction", "I mean the remote on the right of the picture.", True),
            ("history", "Where did you last see it?", False),
        ]
        if args.current_only:
            cases = cases[:2]
        for name, message, current in cases:
            body = {"message": message, "request_id": name}
            if current:
                body.update(
                    snapshot=base64.b64encode(
                        (args.fixture / "input_frames" / "000.png").read_bytes()
                    ).decode(),
                    captured_at=datetime.now(UTC).isoformat(),
                )
            started = time.perf_counter()
            response = client.post("/api/agent", json=body)
            response.raise_for_status()
            job = wait(client, response.json()["id"])
            row = {"name": name, "seconds": time.perf_counter() - started, "job": job}
            results["cases"].append(row)
            results["model"] = model.fingerprint if model else None
            results["mlx_peak_bytes"] = mx.get_peak_memory()
            (args.output / "results.json").write_text(json.dumps(results, indent=2))
            result = job.get("result", {})
            print(
                json.dumps(
                    {
                        "name": name,
                        "status": job["status"],
                        "answer": result.get("answer"),
                        "steps": result.get("steps"),
                        "seconds": row["seconds"],
                    }
                ),
                flush=True,
            )

        if args.review_history:
            candidate = job.get("result", {}).get("visual") or {}
            review = {
                "simulated_user": True,
                "rule": "Fixture offsets 0 and 8 contain the selected right remote; offsets 14/16 are crops of the other remote. This oracle is only for this development fixture.",
                "attempts": [],
                "confirmation": None,
            }
            for _ in range(4):
                if candidate.get("status") != "candidate":
                    break
                evidence = candidate["evidence"]
                review["attempts"].append(
                    {
                        "frame_id": evidence["id"],
                        "offset_seconds": evidence["offset_seconds"],
                        "observed_at": evidence["observed_at"],
                    }
                )
                if evidence["offset_seconds"] in {0, 8}:
                    response = client.post(
                        "/api/matches/confirm",
                        json={
                            "frame_id": evidence["id"],
                            "object_query": candidate["object_query"],
                            "request_id": str(uuid4()),
                        },
                    )
                    response.raise_for_status()
                    review["confirmation"] = response.json()
                    break
                response = client.post(
                    "/api/agent",
                    json={
                        "message": "Nah, that is not the item I meant. Please keep looking.",
                        "request_id": str(uuid4()),
                        "presented_frame_id": evidence["id"],
                        "presented_query": candidate["object_query"],
                    },
                )
                response.raise_for_status()
                review_job = wait(client, response.json()["id"])
                review["attempts"][-1]["rejection_job"] = review_job
                candidate = review_job.get("result", {}).get("visual") or {}
            results["review"] = review
            results["mlx_peak_bytes"] = mx.get_peak_memory()
            (args.output / "results.json").write_text(json.dumps(results, indent=2))
            print(json.dumps(review), flush=True)

        if args.acceptance:
            for name, message, current in [
                ("switch", "New task: check the current camera for the cat on the left.", True),
                ("stop", "Thanks, stop looking for now.", False),
            ]:
                body = {"message": message, "request_id": name}
                if current:
                    body.update(
                        snapshot=base64.b64encode(
                            (args.fixture / "input_frames" / "000.png").read_bytes()
                        ).decode(),
                        captured_at=datetime.now(UTC).isoformat(),
                    )
                started = time.perf_counter()
                response = client.post("/api/agent", json=body)
                response.raise_for_status()
                job = wait(client, response.json()["id"])
                results["cases"].append(
                    {"name": name, "seconds": time.perf_counter() - started, "job": job}
                )
                print(
                    json.dumps(
                        {
                            "name": name,
                            "job_status": job["status"],
                            "answer": job.get("result", {}).get("answer"),
                            "steps": job.get("result", {}).get("steps"),
                        }
                    ),
                    flush=True,
                )
                (args.output / "results.json").write_text(json.dumps(results, indent=2))
            turns = {row["name"]: row["job"].get("result", {}) for row in results["cases"]}

            def query(turn):
                return next(
                    (
                        step["query"].lower()
                        for step in reversed(turn.get("steps", []))
                        if "query" in step
                    ),
                    "",
                )

            history = turns["history"].get("visual") or {}
            observed = (history.get("evidence") or {}).get("observed_at")
            reviewed = results["review"]
            rejections = [
                row["rejection_job"] for row in reviewed["attempts"] if "rejection_job" in row
            ]
            checks = {
                "current_ambiguity": turns["current"].get("status") == "clarify",
                "correction": turns["correction"].get("status") == "seen"
                and "right" in query(turns["correction"]),
                "recent_history": history.get("status") == "candidate"
                and "right" in query(turns["history"])
                and bool(observed)
                and datetime.fromisoformat(observed) > datetime.now(UTC) - timedelta(hours=2),
                "conversational_rejection": bool(rejections)
                and all(row.get("status") == "succeeded" for row in rejections)
                and len({row["frame_id"] for row in reviewed["attempts"]})
                == len(reviewed["attempts"]),
                "user_confirmation": bool(reviewed["confirmation"])
                and reviewed["confirmation"].get("confirmation") == "user",
                "task_switch": turns["switch"].get("status") == "seen"
                and "cat" in query(turns["switch"])
                and "left" in query(turns["switch"])
                and "remote" not in query(turns["switch"]),
                "stop": turns["stop"].get("status") == "chat"
                and len(turns["stop"].get("steps", [])) == 1,
            }
            results["acceptance"] = {
                "checks": checks,
                "passed": all(checks.values()),
                "limits": "Public still/slideshow and simulated user review; manual visual/answer review still required. Not household or voice acceptance.",
            }
            results["mlx_peak_bytes"] = mx.get_peak_memory()
            (args.output / "results.json").write_text(json.dumps(results, indent=2))
            print(json.dumps(results["acceptance"]), flush=True)
            if not all(checks.values()):
                raise SystemExit(1)


if __name__ == "__main__":
    main()
