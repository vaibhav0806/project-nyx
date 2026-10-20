"""Small real-model object flow using the existing public-image synthetic video."""

import argparse
import base64
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import mlx.core as mx
from fastapi.testclient import TestClient

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
        "--current-only",
        action="store_true",
        help="Check current view and correction without indexing or historical retrieval",
    )
    args = parser.parse_args()
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


if __name__ == "__main__":
    main()
