"""Opt-in real local planner/tool scenarios and bounded video checks. No hardware/cloud."""

import argparse
import base64
import json
import platform
import resource
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from nyx.app import create_app
from nyx.verification import LocalVerifier


def wait(client, identifier, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{identifier}").json()
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(0.1)
    raise TimeoutError("Local experiment job exceeded its budget")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = {
        "platform": platform.platform(),
        "cases": [],
        "planner": [],
        "synthetic_or_public_only": True,
    }
    model = None

    def factory():
        nonlocal model
        model = LocalVerifier()
        original = model.generate_json

        def record(messages, max_tokens=240):
            raw = original(messages, max_tokens)
            with (args.output / "generations.jsonl").open("a") as file:
                file.write(
                    json.dumps(
                        {
                            "messages": [
                                {
                                    "role": row["role"],
                                    "content": row["content"]
                                    if isinstance(row["content"], str)
                                    else "local image content omitted",
                                }
                                for row in messages
                            ],
                            "raw": raw,
                        }
                    )
                    + "\n"
                )
            return raw

        model.generate_json = record
        return model

    def save():
        results["process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if model:
            results["model"] = model.fingerprint
            results["model_load_seconds"] = model.load_seconds
        (args.output / "results.json").write_text(json.dumps(results, indent=2))

    with TestClient(create_app(args.output / "workspace", verifier_factory=factory)) as client:
        warm = client.post("/api/companion/warmup").json()
        assert wait(client, warm["id"])["status"] == "succeeded"
        planner_cases = [
            ("current", "Where are my glasses?", [], [], "inspect_current"),
            (
                "correction",
                "No, the thin silver reading ones",
                [
                    {
                        "transcript": "Where are my glasses?",
                        "answer": "Unclear",
                        "sources_available": True,
                    }
                ],
                [],
                "inspect_current",
            ),
            (
                "pronoun",
                "Where did you last see them?",
                [
                    {
                        "transcript": "Find my silver reading glasses",
                        "answer": "Unclear",
                        "sources_available": True,
                    }
                ],
                [],
                "search_history",
            ),
            (
                "departure",
                "Remind me to take my water bottle when I leave",
                [],
                [],
                "remind_on_departure",
            ),
            ("unsupported-time", "Remind me to call my daughter at six", [], [], "clarify"),
            (
                "fallback",
                "Where are my glasses?",
                [],
                [
                    {
                        "index": 0,
                        "kind": "snapshot",
                        "status": "uncertain",
                        "answer": "Not confirmed in the current view",
                    }
                ],
                "search_history",
            ),
            (
                "finish",
                "Find my glasses",
                [],
                [
                    {
                        "index": 0,
                        "kind": "history",
                        "status": "seen",
                        "answer": "Last seen on the table at 10:00",
                    }
                ],
                "finish",
            ),
        ]
        for name, message, context, observations, expected in planner_cases:
            started = time.perf_counter()
            try:
                decision = model.decide(
                    {
                        "message": message,
                        "conversation": context,
                        "observations": observations,
                        "reminders": [],
                        "now": datetime.now(UTC).isoformat(),
                    }
                )
            except (ValueError, TypeError, RuntimeError) as exc:
                decision = {"error": str(exc)}
            row = {
                "name": name,
                "decision": decision,
                "expected_action": expected,
                "action_matched": decision.get("action") == expected,
                "seconds": time.perf_counter() - started,
            }
            results["planner"].append(row)
            print(json.dumps(row), flush=True)
            save()

        video = (args.fixture / "scenes.mp4").read_bytes()
        for name, hours in [("old", 240), ("recent", 1)]:
            stamp = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
            job = client.post(
                "/api/import", params={"name": name + ".mp4", "recorded_at": stamp}, content=video
            ).json()
            assert wait(client, job["id"])["status"] == "succeeded"
        scenarios = [
            ("current-remote", "Where is the television remote control?", "000.png"),
            ("recent-followup", "Where did you last see it?", None),
            ("departure-request", "Remind me to take my water bottle when I leave", None),
            ("cancel-departure", "Cancel that departure reminder", None),
        ]
        for name, message, frame in scenarios:
            body = {"message": message, "request_id": name}
            if frame:
                body.update(
                    snapshot=base64.b64encode(
                        (args.fixture / "input_frames" / frame).read_bytes()
                    ).decode(),
                    captured_at=datetime.now(UTC).isoformat(),
                )
            started = time.perf_counter()
            response = client.post("/api/agent", json=body)
            job = wait(client, response.json()["id"])
            row = {"name": name, "seconds": time.perf_counter() - started, "job": job}
            results["cases"].append(row)
            print(
                json.dumps(
                    {
                        "name": name,
                        "seconds": row["seconds"],
                        "status": job["status"],
                        "answer": job.get("result", {}).get("answer"),
                        "steps": job.get("result", {}).get("steps"),
                    }
                ),
                flush=True,
            )
            save()


if __name__ == "__main__":
    main()
