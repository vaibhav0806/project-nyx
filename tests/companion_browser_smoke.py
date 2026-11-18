"""Real browser/API contract replay with synthetic camera/model IO; no paid inference/hardware."""

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    code = """import sys,uvicorn
from nyx.app import create_app
from test_companion import Planner
from test_nyx import ColorEncoder
uvicorn.run(create_app(sys.argv[1],encoder_factory=ColorEncoder,verifier_factory=Planner,voice_factory=lambda _:None),host='127.0.0.1',port=int(sys.argv[2]))"""
    env = {**os.environ, "PYTHONPATH": "src:tests", "OPENROUTER_API_KEY": "fixture"}
    env.pop("SARVAM_API_KEY", None)
    with (args.output / "server.log").open("w") as log:
        server = subprocess.Popen(
            [sys.executable, "-c", code, str(args.output / "workspace"), str(port)],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    with urlopen(origin + "/api/videos", timeout=1):
                        break
                except OSError:
                    if server.poll() is not None:
                        raise RuntimeError("Synthetic API server stopped") from None
                    time.sleep(0.1)
            else:
                raise RuntimeError("Synthetic API server did not start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1360, "height": 1000})
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.route(
                        "**/*",
                        lambda route: (
                            route.continue_()
                            if route.request.url.startswith(origin)
                            else route.abort()
                        ),
                    )
                    page.add_init_script("""navigator.mediaDevices.getUserMedia = async () => {
                        const canvas=document.createElement('canvas'); canvas.width=640;canvas.height=480;
                        const context=canvas.getContext('2d');let frame=0;
                        window.syntheticTimer=setInterval(()=>{
                            context.fillStyle='green';context.fillRect(0,0,640,480);
                            context.fillStyle='white';context.fillRect(frame++%640,0,1,1);
                        },100);
                        window.syntheticCamera=canvas.captureStream(10);
                        return window.syntheticCamera;
                    };""")
                    page.goto(origin)
                    if page.locator("#camera-state").inner_text() != "Camera on":
                        page.locator("#camera-toggle").click()
                    expect(page.locator("#camera-state")).to_have_text("Camera on", timeout=15000)
                    if not page.locator("#companion-message").is_visible():
                        page.get_by_role("button", name="Type instead", exact=True).click()
                    page.locator("#companion-message").fill("Where is the green object?")
                    page.locator("#companion-send").click()
                    page.wait_for_function("!companion.working", timeout=20000)
                    state = page.request.get(origin + "/api/companion").json()
                    turn = state["conversations"][-1]
                    assert turn["status"] == "complete" and turn["answer"], turn
                    assert turn["transcript"] == "Where is the green object?"
                    assert turn["plan"]["steps"] == [
                        {"action": "inspect_current", "query": "green"}
                    ]
                    assert state["observation"]["state"] == "inactive" and state["pending"] == []
                    assert page.evaluate("window.syntheticCamera.getAudioTracks().length") == 0
                    page.screenshot(path=str(args.output / "typed-lookup.png"), full_page=True)
                    page.locator("#camera-toggle").click()
                    page.wait_for_function("!stream", timeout=10000)
                    page.wait_for_timeout(300)
                    assert not errors, errors
                    report = {
                        "status": "complete",
                        "synthetic_media_only": True,
                        "provider_requests": 0,
                        "typed_lookup": "passed",
                        "inactive_polling": "passed",
                        "camera_stop": "passed",
                        "page_errors": errors,
                        "limitations": "Real browser and backend; model responses and camera frames are fixtures. This is transport/UI compatibility, not recognition, acoustic or household accuracy.",
                    }
                    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
                    print(json.dumps(report))
                finally:
                    browser.close()
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
