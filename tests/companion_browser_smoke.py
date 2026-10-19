"""Isolated browser integration with fake media and model boundaries; no real hardware."""

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--speech",
        action="store_true",
        help="Exercise synthetic proactive speech and acknowledgement",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    code = """from nyx.app import create_app
from test_companion import Planner
from test_nyx import ColorEncoder
from nyx.voice import Voice
import uvicorn,sys,base64,wave
from io import BytesIO
class Speech:
    def speak(self,text):
        out=BytesIO()
        with wave.open(out,'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\\0'*32000)
        return base64.b64encode(out.getvalue()).decode()
factory=(lambda root:Voice(root,Speech(),lambda pcm:'',agent_mode=True)) if sys.argv[3]=='1' else None
uvicorn.run(create_app(sys.argv[1], encoder_factory=ColorEncoder, verifier_factory=Planner,voice_factory=factory), host='127.0.0.1',port=int(sys.argv[2]))"""
    env = {**os.environ, "PYTHONPATH": "src:tests"}
    env.pop("SARVAM_API_KEY", None)
    with (args.output / "server.log").open("w") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-c",
                code,
                str(args.output / "data"),
                str(port),
                "1" if args.speech else "0",
            ],
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(100):
                try:
                    urlopen(url + "/api/capture", timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.1)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    channel="chrome",
                    headless=True,
                    args=["--autoplay-policy=no-user-gesture-required"],
                )
                try:
                    page = browser.new_page(viewport={"width": 1360, "height": 1000})
                    errors = []
                    requests = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("request", lambda request: requests.append(request.url))
                    page.add_init_script("""navigator.mediaDevices.getUserMedia = async constraints => {
                        if (constraints.audio && constraints.video===false) {
                            window.fakeMicContext=new AudioContext({sampleRate:16000});
                            return window.fakeMicContext.createMediaStreamDestination().stream;
                        }
                        const canvas = document.createElement('canvas'); canvas.width=640; canvas.height=360;
                        const ctx=canvas.getContext('2d'); let i=0;
                        ctx.fillStyle='gray'; ctx.fillRect(0,0,640,360);
                        window.fakeTimer=setInterval(()=>{ctx.fillStyle=i++%2?'white':'gray';ctx.fillRect(0,0,640,360);},800);
                        window.fakeStream=canvas.captureStream(10);return window.fakeStream;
                    };""")
                    page.goto(url)
                    expect(page.locator("#companion-message")).to_be_visible()
                    page.locator("#companion-message").fill("Remind me about water when I leave")
                    page.locator("#companion-send").click()
                    expect(page.locator("#reminders")).to_contain_text(
                        "Take your water bottle", timeout=15000
                    )
                    expect(page.locator("#reminders")).to_contain_text("armed")
                    if not args.speech:
                        page.locator("#start").click()
                    expect(page.locator("#camera-state")).to_have_text("Recording video")
                    expect(page.locator("#reminders")).to_contain_text(
                        "delivered" if args.speech else "failed", timeout=20000
                    )
                    if args.speech:
                        page.get_by_role("button", name="Got it", exact=True).click()
                        expect(page.locator("#reminders")).to_contain_text("acknowledged")
                        page.wait_for_timeout(2500)
                        assert (
                            len(
                                [
                                    url
                                    for url in requests
                                    if "/api/deliveries/" in url and url.endswith("/claim")
                                ]
                            )
                            == 1
                        )
                    page.locator("#companion-message").fill("Where is the green thing?")
                    page.locator("#companion-send").click()
                    expect(page.locator("#companion-thread")).to_contain_text(
                        "I can see green", timeout=15000
                    )
                    expect(page.locator("#snapshot-evidence")).to_be_visible()
                    page.locator("#stop").click()
                    expect(page.locator("#camera-state")).to_have_text("Camera off")
                    assert page.evaluate(
                        "window.fakeStream.getTracks().every(t=>t.readyState==='ended')"
                    )
                    page.screenshot(path=str(args.output / "companion.png"), full_page=True)
                    page.reload()
                    expect(page.locator("#companion-thread")).to_contain_text(
                        "Where is the green thing?", timeout=10000
                    )
                    assert not errors, errors
                    (args.output / "results.json").write_text(
                        json.dumps(
                            {
                                "browser_errors": errors,
                                "fake_devices": True,
                                "models": "deterministic boundary fixtures",
                                "synthetic_speech": args.speech,
                                "passed": True,
                            },
                            indent=2,
                        )
                    )
                finally:
                    browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
