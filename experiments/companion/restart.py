"""Restart an existing synthetic workspace and verify saved retrieval/media. No devices."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen


def main():
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (args.workspace / "index.sqlite3").is_file():
        parser.error("Use an existing indexed synthetic workspace, after stopping its server")
    args.output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"

    def get(path, body=None):
        request = Request(
            url + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"content-type": "application/json"},
        )
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    with (args.output / "server.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "nyx.cli",
                "--data-dir",
                str(args.workspace),
                "serve",
                "--port",
                str(port),
            ],
            stdout=log,
            stderr=log,
            env={**os.environ, "HF_HUB_OFFLINE": "1"},
        )
        try:
            for _ in range(100):
                try:
                    capture = get("/api/capture")
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Server did not start; see server.log")
            assert capture["session"]["state"] != "recording", capture
            deadline = time.monotonic() + 120
            while any(
                capture["counts"].get(state, 0)
                for state in ["uploading", "staged", "queued", "indexing"]
            ):
                if time.monotonic() > deadline:
                    raise TimeoutError("Saved capture work did not recover")
                time.sleep(0.2)
                capture = get("/api/capture")
            sources = get("/api/videos")
            assert sources and all(row["status"] == "ready" for row in sources), sources
            job = get("/api/search", {"query": "a television remote control"})
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                job = get("/api/jobs/" + job["id"])
                if job["status"] in {"succeeded", "failed"}:
                    break
                time.sleep(0.2)
            assert job["status"] == "succeeded", job
            candidates = job["result"]["results"]
            assert candidates
            request = Request(url + candidates[0]["media_url"], headers={"Range": "bytes=0-99"})
            with urlopen(request, timeout=5) as response:
                media_status = response.status
                content_range = response.headers.get("content-range")
                media_bytes = len(response.read())
            assert media_status == 206 and media_bytes == 100
            result = {
                "workspace": str(args.workspace),
                "saved_sources": len(sources),
                "capture_state": capture["session"]["state"],
                "candidate_count": len(candidates),
                "media_status": media_status,
                "media_bytes": media_bytes,
                "content_range": content_range,
                "limitations": "Synthetic workspace. Server restart opens no camera/microphone; visual presence remains unverified.",
            }
            (args.output / "results.json").write_text(json.dumps(result, indent=2))
            print(json.dumps(result))
        finally:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
