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


def run(url, video, output):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""window.cameraCalls = 0;
                navigator.mediaDevices.getUserMedia = async () => {
                    window.cameraCalls++;
                    throw new DOMException('Test denial', 'NotAllowedError');
                };""")
            page.goto(url)
            expect(
                page.get_by_role("heading", name="Record a moment. Find it again.")
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
            expect(page.locator(".candidate")).to_have_count(5, timeout=30000)
            page.locator(".candidate").first.click()
            page.wait_for_function("document.querySelector('#viewer').currentTime >= 13.5")
            assert page.locator("#viewer").get_attribute("src").endswith("#t=14")
            expect(page.locator(".candidate").first).to_contain_text("Unverified")
            page.screenshot(path=str(output / "desktop-results.png"), full_page=True)

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
            page.wait_for_timeout(2200)
            page.get_by_role("button", name="Stop recording").click()
            expect(page.get_by_role("button", name="Index clip")).to_be_visible()
            assert page.evaluate(
                "window.testStream.getTracks().every(t => t.readyState === 'ended')"
            )
            page.get_by_role("button", name="Index clip").click()
            expect(page.locator("#task")).to_contain_text("Clip indexed", timeout=30000)
            expect(page.locator("#clip-count")).to_have_text("2 clips")
            assert "Capture time unknown" not in page.locator(".clip").first.inner_text()
            page.evaluate("clearInterval(window.drawTimer)")

            page.get_by_role("button", name="Start recording").click()
            expect(page.locator("#camera-state")).to_have_text("Recording video")
            page.wait_for_timeout(1200)
            page.evaluate("window.testStream.getVideoTracks()[0].dispatchEvent(new Event('ended'))")
            expect(page.get_by_role("alert")).to_contain_text("camera stopped unexpectedly")
            expect(page.get_by_role("button", name="Discard clip")).to_be_visible()
            assert page.evaluate(
                "window.testStream.getTracks().every(t => t.readyState === 'ended')"
            )
            page.get_by_role("button", name="Discard clip").click()
            expect(page.get_by_role("button", name="Start recording")).to_be_visible()
            expect(page.locator("#clip-count")).to_have_text("2 clips")
            page.evaluate("clearInterval(window.drawTimer)")

            page.get_by_role("button", name="Start recording").click()
            expect(page.locator("#camera-state")).to_have_text("Recording video")
            page.wait_for_timeout(1200)
            page.evaluate("""() => {
                Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
                document.dispatchEvent(new Event('visibilitychange'));
            }""")
            expect(page.get_by_role("alert")).to_contain_text("tab was hidden")
            expect(page.get_by_role("button", name="Discard clip")).to_be_visible()
            assert page.evaluate(
                "window.testStream.getTracks().every(t => t.readyState === 'ended')"
            )
            page.get_by_role("button", name="Discard clip").click()
            page.evaluate("delete document.hidden; clearInterval(window.drawTimer)")

            page.get_by_role("button", name="Start recording").click()
            expect(page.locator("#camera-state")).to_have_text("Recording video")
            page.evaluate("""window.addEventListener('pagehide', () => {
                sessionStorage.setItem('tracksReleased', String(window.testStream.getTracks().every(t => t.readyState === 'ended')));
            });""")
            page.reload()
            expect(page.locator("#clip-count")).to_have_text("2 clips")
            assert page.evaluate("sessionStorage.getItem('tracksReleased')") == "true"
            assert page.evaluate("window.cameraCalls") == 0
            mobile = browser.new_page(viewport={"width": 390, "height": 844})
            mobile.add_init_script(
                "navigator.mediaDevices.getUserMedia = async () => { throw new Error('Real camera disabled in this check'); };"
            )
            mobile.on("pageerror", lambda error: errors.append(str(error)))
            mobile.goto(url)
            expect(mobile.locator("#clip-count")).to_have_text("2 clips")
            mobile.screenshot(path=str(output / "mobile.png"), full_page=True)
            assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert errors == [], errors
            result = {
                "browser": browser.version,
                "checks": [
                    "No camera request on initial load or reload",
                    "Denied camera displays recovery action",
                    "Real-model file import/search and source replay at 14 seconds",
                    "Synthetic video-only capture, stop releases tracks, index preserves capture time",
                    "Camera interruption stops and labels incomplete clip; discard leaves library unchanged",
                    "Tab hiding stops recording; navigation releases camera tracks",
                    "Library survives page reload; mobile layout has no horizontal overflow",
                    "No uncaught browser errors",
                ],
                "limitations": [
                    "Synthetic camera, not actual camera hardware or room footage",
                    "No intended-user evaluation",
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
    args = parser.parse_args()
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
            run(url, args.video.resolve(), args.output)
        finally:
            process.terminate()
            process.wait(timeout=30)


if __name__ == "__main__":
    main()
