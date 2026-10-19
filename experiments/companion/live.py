"""Replay labelled public frames through the real live API/model. No hardware/cloud."""

import argparse
import base64
import json
import time
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from nyx.app import create_app
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
    args = parser.parse_args()
    cases = json.loads(args.manifest.read_text())["cases"]
    selected = [row for row in cases if row["name"] in args.cases]
    if len(selected) != len(set(args.cases)):
        parser.error("Every case name must exist in the manifest")
    args.output.mkdir(parents=True, exist_ok=False)
    model = None
    generations = []

    def factory():
        nonlocal model
        model = LocalVerifier()
        original = model.generate_json

        def record(messages, max_tokens=240):
            raw = original(messages, max_tokens)
            generations.append(raw)
            return raw

        model.generate_json = record
        return model

    results = {"cases": [], "protocol": "Actual API clock; sampled public frames replayed 2s apart"}
    with TestClient(
        create_app(
            args.output / "workspace", verifier_factory=factory, voice_factory=lambda root: None
        )
    ) as client:
        warm = client.post("/api/companion/warmup").json()
        assert wait(client, warm["id"])["status"] == "succeeded"
        results["model"] = model.fingerprint
        for case in selected:
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
            session = client.post(
                "/api/capture/start", json={"at": datetime.now(UTC).isoformat()}
            ).json()
            paths = sorted(Path(case["frames"]).glob("*.jpg"))
            for index, frame in enumerate(case["indices"]):
                if index:
                    time.sleep(2)
                with Image.open(paths[frame]) as source:
                    image = source.convert("RGB")
                image.thumbnail((640, 360))
                encoded = BytesIO()
                image.save(encoded, format="JPEG")
                observed_at = datetime.now(UTC)
                observation = client.post(
                    "/api/observe",
                    json={
                        "session_id": session["id"],
                        "captured_at": observed_at.isoformat(),
                        "image": base64.b64encode(encoded.getvalue()).decode(),
                    },
                )
                assert observation.status_code in {200, 202}, observation.text
            outcome = (
                wait(client, observation.json()["id"])
                if observation.status_code == 202
                else observation.json()
            )
            status = client.get("/api/companion").json()
            row = {
                **case,
                "request": request_job,
                "observation": outcome,
                "seconds_since_final_frame": (datetime.now(UTC) - observed_at).total_seconds(),
                "reminders": status["reminders"],
                "pending": status["pending"],
                "generations": generations[start_generation:],
            }
            results["cases"].append(row)
            (args.output / "results.json").write_text(json.dumps(results, indent=2))
            print(json.dumps(row), flush=True)
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
