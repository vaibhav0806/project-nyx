"""Opt-in real-model browser check. Uses synthetic camera frames, never a room camera."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


def wait_capture(page, predicate, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = page.request.get(page.url.rstrip("/") + "/api/capture").json()
        if predicate(status):
            return status
        page.wait_for_timeout(200)
    raise AssertionError(f"Capture condition not reached: {status}")


def run(url, video, output, record_seconds=0, server_pid=None, visual_answers=False):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000}, timezone_id="Asia/Kolkata"
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""window.cameraCalls = 0;
                navigator.mediaDevices.getUserMedia = async () => {
                    window.cameraCalls++;
                    throw new DOMException('Test denial', 'NotAllowedError');
                };""")
            page.goto(url)
            expect(
                page.get_by_role("heading", name="Keep a little history. Find a moment.")
            ).to_be_visible()
            assert page.evaluate("window.cameraCalls") == 0
            page.screenshot(path=str(output / "desktop-empty.png"), full_page=True)

            page.get_by_role("button", name="Start recording").click()
            expect(page.get_by_role("alert")).to_contain_text("Camera access was denied")
            expect(page.locator("#camera-state")).to_have_text("Camera off")
            assert page.evaluate("window.cameraCalls") == 1

            page.locator("#file").set_input_files(str(video))
            expect(page.locator("#task")).to_contain_text("Clip indexed", timeout=60000)
            expect(page.locator("#clip-count")).to_have_text("1 clip")
            page.get_by_label("What are you looking for?").fill("a television remote control")
            page.get_by_role("button", name="Search", exact=True).click()
            expect(page.locator("#results .candidate")).to_have_count(5, timeout=30000)
            page.locator("#results .candidate").first.click()
            page.wait_for_function("document.querySelector('#replay').currentTime >= 13.5")
            assert page.locator("#replay").get_attribute("src").endswith("#t=14")
            expect(page.locator("#results .candidate").first).to_contain_text("Unverified")
            page.screenshot(path=str(output / "desktop-results.png"), full_page=True)

            if visual_answers:
                page.locator("#object-query").fill("a television remote control")
                page.get_by_role("button", name="Check history", exact=True).click()
                expect(page.locator("#answer-text")).to_contain_text(
                    "does not prove", timeout=15000
                )
                assert page.evaluate("window.cameraCalls") == 1
                dated = page.request.post(
                    url + "/api/import?name=M3-dated.mp4&recorded_at=2026-10-19T10:00:00Z",
                    data=video.read_bytes(),
                ).json()
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    job = page.request.get(url + f"/api/jobs/{dated['id']}").json()
                    if job["status"] in ["succeeded", "failed"]:
                        break
                    page.wait_for_timeout(200)
                assert job["status"] == "succeeded", job
                page.reload()
                page.locator("#object-query").fill("a television remote control")
                page.get_by_text("Limit history by time", exact=True).click()
                page.locator("#seen-after").fill("2026-10-19T15:30:13")
                page.locator("#seen-before").fill("2026-10-19T15:30:15")
                page.get_by_role("button", name="Check history", exact=True).click()
                expect(page.locator("#answer-text")).to_contain_text(
                    "Latest model-confirmed", timeout=60000
                )
                expect(page.locator("#answer-evidence")).to_contain_text("00:14")
                expect(page.locator("#answer-checks .candidate")).to_have_count(1)
                expect(page.locator("#answer-note")).to_contain_text("sampled")
                page.locator("#answer-evidence button").first.click()
                page.wait_for_function("document.querySelector('#replay').currentTime >= 13.5")
                page.screenshot(path=str(output / "desktop-answer.png"), full_page=True)
                page.locator("#seen-after").fill("")
                page.locator("#seen-before").fill("")

            page.evaluate("""() => { navigator.mediaDevices.getUserMedia = async (constraints) => {
                window.cameraCalls++;
                if (constraints.audio !== false) throw new Error('Audio must stay disabled');
                const canvas = document.createElement('canvas');
                canvas.width = 640; canvas.height = 360;
                const context = canvas.getContext('2d');
                let n = 0;
                const draw = () => {
                    context.fillStyle = n++ % 2 ? '#336699' : '#669933';
                    context.fillRect(0, 0, 640, 360);
                };
                draw();
                window.drawTimer = setInterval(draw, 100);
                window.testStream = canvas.captureStream(10);
                return window.testStream;
            }; }""")
            page.get_by_role("button", name="Start recording").click()
            expect(page.locator("#camera-state")).to_have_text("Recording video")
            recording_started = time.monotonic()
            wait_capture(page, lambda status: status["counts"].get("ready", 0) >= 2)
            resource_samples = []
            search_seconds = []
            next_search = 0
            while time.monotonic() - recording_started < record_seconds:
                health = page.request.get(url + "/api/capture").json()
                assert health["session"]["state"] == "recording", health
                assert not health["counts"].get("failed", 0), health
                rss = (
                    subprocess.check_output(["ps", "-o", "rss=", "-p", str(server_pid)], text=True)
                    if server_pid
                    else None
                )
                resource_samples.append(
                    {
                        "elapsed_seconds": time.monotonic() - recording_started,
                        "server_rss_mib": int(rss.strip()) / 1024 if rss else None,
                        "video_bytes": health["video_bytes"],
                        "pending": sum(
                            health["counts"].get(state, 0)
                            for state in ["uploading", "staged", "queued", "indexing"]
                        ),
                        "ready": health["counts"].get("ready", 0),
                    }
                )
                if time.monotonic() >= next_search:
                    page.get_by_label("What are you looking for?").fill(
                        "a television remote control"
                    )
                    search_started = time.monotonic()
                    page.get_by_role("button", name="Search", exact=True).click()
                    expect(page.get_by_role("button", name="Search", exact=True)).to_be_enabled(
                        timeout=10000
                    )
                    expect(page.locator("#task")).to_contain_text("Select a candidate")
                    search_seconds.append(time.monotonic() - search_started)
                    next_search = time.monotonic() + 15
                page.wait_for_timeout(1000)
            recording_elapsed = time.monotonic() - recording_started
            expect(page.get_by_role("button", name="Search", exact=True)).to_be_enabled()
            page.get_by_label("What are you looking for?").fill("a television remote control")
            page.get_by_role("button", name="Search", exact=True).click()
            expect(page.get_by_role("button", name="Search", exact=True)).to_be_enabled(
                timeout=10000
            )
            expect(page.locator("#task")).to_contain_text("Select a candidate")
            expect(page.get_by_role("alert")).not_to_be_visible()
            expect(page.locator("#results .candidate")).to_have_count(5)
            page.locator("#results .candidate").first.click()
            expect(page.locator("#replay-panel")).to_be_visible()
            expect(page.locator("#camera-state")).to_have_text("Recording video")
            assert page.evaluate("window.testStream.getVideoTracks()[0].readyState") == "live"
            expect(page.locator("#searchable-through")).to_contain_text("Searchable through")
            if visual_answers:
                page.get_by_role("button", name="Check current view", exact=True).click()
                expect(page.locator("#answer-text")).to_contain_text("snapshot", timeout=60000)
                expect(page.locator("#snapshot-evidence")).to_be_visible()
                expect(page.locator("#camera-state")).to_have_text("Recording video")
                page.screenshot(path=str(output / "desktop-snapshot.png"), full_page=True)
            page.screenshot(path=str(output / "desktop-continuous.png"), full_page=True)

            page.get_by_role("button", name="Pause recording").click()
            expect(page.locator("#camera-state")).to_have_text("Recording paused")
            assert page.evaluate(
                "window.testStream.getTracks().every(t => t.readyState === 'ended')"
            )
            page.evaluate("clearInterval(window.drawTimer)")
            page.get_by_role("button", name="Resume recording").click()
            expect(page.locator("#camera-state")).to_have_text("Recording video")
            page.wait_for_timeout(1400)
            page.evaluate("""() => {
                Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
                document.dispatchEvent(new Event('visibilitychange'));
            }""")
            expect(page.locator("#camera-state")).to_have_text("Recording video")
            page.evaluate("delete document.hidden")
            page.evaluate("window.testStream.getVideoTracks()[0].dispatchEvent(new Event('ended'))")
            expect(page.get_by_role("alert")).to_contain_text("camera was interrupted")
            expect(page.locator("#camera-state")).to_have_text("Camera off")
            assert page.evaluate(
                "window.testStream.getTracks().every(t => t.readyState === 'ended')"
            )
            wait_capture(
                page,
                lambda status: (
                    status["session"]["state"] == "interrupted"
                    and not any(
                        status["counts"].get(state, 0)
                        for state in ["uploading", "staged", "queued", "indexing"]
                    )
                ),
            )
            page.evaluate("clearInterval(window.drawTimer)")
            status = page.evaluate("fetch('/api/capture').then(r => r.json())")
            assert status["counts"]["ready"] >= 3
            assert any("Paused by user" in event["reason"] for event in status["events"])
            assert any("Resumed by user" in event["reason"] for event in status["events"])
            sources = page.evaluate("fetch('/api/videos').then(r => r.json())")
            indexed_count = sum(video["status"] == "ready" for video in sources)
            captured = [video for video in sources if video["name"].startswith("Recording ")]
            assert sum(bool(video["recorded_at"]) for video in captured) >= 2
            assert any(video["recorded_at"] is None for video in captured)
            assert status["timing_uncertain_count"] >= 1

            expect(page.locator(".delete-clip").first).to_be_enabled()
            before_delete = len(sources)
            imported = next(video for video in sources if video["name"] == "scenes.mp4")
            selected = page.locator(".clip-row").filter(has_text="scenes.mp4")
            page.once("dialog", lambda dialog: dialog.dismiss())
            selected.get_by_role("button", name="Delete clip", exact=True).click()
            assert len(page.request.get(url + "/api/videos").json()) == before_delete
            page.once("dialog", lambda dialog: dialog.accept())
            selected.get_by_role("button", name="Delete clip", exact=True).click()
            expect(page.locator("#task")).to_contain_text("Clip deleted")
            assert len(page.request.get(url + "/api/videos").json()) == before_delete - 1
            assert page.request.get(url + f"/api/videos/{imported['id']}/media").status == 404
            expect(page.locator("#search-results")).not_to_be_visible()
            expect(page.locator("#replay-panel")).not_to_be_visible()
            expect(page.locator("#scope")).to_have_value("")

            page.evaluate("""() => {
                window.immediateCamera = navigator.mediaDevices.getUserMedia;
                navigator.mediaDevices.getUserMedia = () => new Promise(resolve => {
                    window.resolveCamera = async () => resolve(await window.immediateCamera({audio: false}));
                });
            }""")
            page.get_by_role("button", name="Start recording").click()
            page.wait_for_function("Boolean(window.resolveCamera)")
            page.get_by_role("button", name="Stop recording").click()
            page.evaluate("window.resolveCamera()")
            page.wait_for_function(
                "window.testStream.getTracks().every(t => t.readyState === 'ended')"
            )
            expect(page.locator("#camera-state")).to_have_text("Camera off")
            page.evaluate(
                "navigator.mediaDevices.getUserMedia = window.immediateCamera; clearInterval(window.drawTimer)"
            )
            wait_capture(page, lambda status: status["session"]["state"] == "stopped")
            expect(page.get_by_role("button", name="Start recording")).to_be_visible()

            page.get_by_role("button", name="Start recording").click()
            expect(page.locator("#camera-state")).to_have_text("Recording video")
            page.wait_for_timeout(1400)
            page.evaluate("""window.addEventListener('pagehide', () => {
                sessionStorage.setItem('tracksReleased', String(window.testStream.getTracks().every(t => t.readyState === 'ended')));
            });""")
            page.reload()
            expect(page.locator("#clip-count")).to_contain_text("clips")
            assert page.evaluate("sessionStorage.getItem('tracksReleased')") == "true"
            assert page.evaluate("window.cameraCalls") == 0
            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            mobile.add_init_script(
                "navigator.mediaDevices.getUserMedia = async () => { throw new Error('Real camera disabled in this check'); };"
            )
            mobile.on("pageerror", lambda error: errors.append(str(error)))
            mobile.goto(url)
            expect(mobile.locator("#clip-count")).to_contain_text("clips")
            mobile.screenshot(path=str(output / "mobile.png"), full_page=True)
            assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert errors == [], errors
            result = {
                "browser": browser.version,
                "visual_answers_checked": visual_answers,
                "requested_recording_seconds": record_seconds,
                "recording_elapsed_seconds": recording_elapsed,
                "resource_samples": resource_samples,
                "search_round_trip_seconds": search_seconds,
                "capture_status_before_reload": status,
                "indexed_count_before_reload": indexed_count,
                "checks": [
                    "No camera request on initial load or reload; late permission resolution after Stop releases tracks",
                    "Denied camera displays recovery action",
                    "Real-model file import/search and source replay at 14 seconds",
                    "Two independently decoded segments indexed automatically while capture stays live",
                    "Search and separate source replay work while recording",
                    "Pause/resume releases and reacquires video-only tracks; capture times preserved",
                    "Camera interruption stops capture, tab hiding does not; navigation releases tracks",
                    "Library survives page reload; mobile layout has no horizontal overflow",
                    "Cancelled deletion preserves sources; confirmed deletion clears results/replay and preserves unrelated clips",
                    "No uncaught browser errors",
                ],
                "limitations": [
                    "Synthetic camera, not actual camera hardware or room footage",
                    "No intended-user evaluation",
                    "RSS samples cover only the server process, excluding FFmpeg/browser/system memory",
                ],
            }
            (output / "browser-results.json").write_text(json.dumps(result, indent=2))
            print(json.dumps(result, indent=2))
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--record-seconds",
        type=int,
        default=0,
        help="Keep synthetic capture running for at least this many seconds",
    )
    parser.add_argument(
        "--visual-answers",
        action="store_true",
        help="Also check the real local VLM, temporal history and explicit synthetic snapshot",
    )
    args = parser.parse_args()
    if args.record_seconds < 0:
        parser.error("Recording duration must be nonnegative")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Choose an empty output directory")
    args.output.mkdir(parents=True, exist_ok=True)
    with socket.socket() as socket_:
        socket_.bind(("127.0.0.1", 0))
        port = socket_.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with (args.output / "server.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "nyx.cli",
                "--data-dir",
                str(args.output / "workspace"),
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
                    with urlopen(url, timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Local server did not start; see server.log")
            run(
                url,
                args.video.resolve(),
                args.output,
                args.record_seconds,
                process.pid,
                args.visual_answers,
            )
        finally:
            process.terminate()
            process.wait(timeout=30)


if __name__ == "__main__":
    main()
