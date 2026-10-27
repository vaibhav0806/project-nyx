"""Isolated browser integration with fake media and model boundaries; no real hardware."""

import argparse
import json
import os
import re
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
    parser.add_argument("--review-fixture", type=Path)
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
class ReviewPlanner(Planner):
    def decide(self,state):
        if state['message']=='Thanks, pause':
            return {'action':'chat','message':'Okay, paused.'}
        candidate=state.get('available',{}).get('presented_candidate')
        if candidate and not state['observations']:
            previous=next((r['plan']['candidate'].get('excluded_frame_ids',[]) for r in reversed(state['conversation']) if (r.get('plan',{}).get('candidate') or {}).get('frame_id')==candidate['frame_id']),[])
            return {'action':'search_matches','query':candidate['object_query'],'excluded_frame_ids':previous+[candidate['frame_id']]}
        return super().decide(state)
factory=(lambda root:Voice(root,Speech(),lambda pcm:'',agent_mode=True)) if sys.argv[3]=='1' else None
uvicorn.run(create_app(sys.argv[1], encoder_factory=ColorEncoder, verifier_factory=ReviewPlanner,voice_factory=factory), host='127.0.0.1',port=int(sys.argv[2]))"""
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
                    held_claims = []
                    if args.speech:

                        def hold_claim(route):
                            held_claims.append((route, route.fetch()))

                        page.route("**/api/deliveries/*/claim", hold_claim)
                        page.add_init_script("""window.reminderAudioStarts=0;
                            const originalPlay=HTMLAudioElement.prototype.play;
                            HTMLAudioElement.prototype.play=function(){
                                window.reminderAudioStarts++;return originalPlay.call(this);
                            };""")
                    page.add_init_script("""navigator.mediaDevices.getUserMedia = async constraints => {
                        if (constraints.audio && constraints.video===false) {
                            window.fakeMicContext=new AudioContext({sampleRate:16000});
                            return window.fakeMicContext.createMediaStreamDestination().stream;
                        }
                        const canvas = document.createElement('canvas'); canvas.width=640; canvas.height=480;
                        const ctx=canvas.getContext('2d'); let i=0;
                        window.fakeScene='quiet';window.fakeFlashUntil=0;
                        ctx.fillStyle='gray'; ctx.fillRect(0,0,640,480);
                        window.fakeTimer=setInterval(()=>{
                            ctx.fillStyle=performance.now()<window.fakeFlashUntil?'white':
                                window.fakeScene==='active'&&Math.floor(i++/16)%2?'white':'gray';
                            ctx.fillRect(0,0,640,480);
                        },50);
                        window.fakeStream=canvas.captureStream(10);return window.fakeStream;
                    };""")
                    page.goto(url)
                    expect(page.locator("#companion-message")).to_be_visible()
                    page.locator("#companion-message").fill("Remind me about water when I leave")
                    page.locator("#companion-send").click()
                    expect(page.locator("#reminders")).to_contain_text(
                        "Take your water bottle", timeout=15000
                    )
                    expect(page.locator("#reminders")).to_contain_text(
                        "Waiting for your next departure"
                    )
                    if not args.speech:
                        page.locator("#start").click()
                    expect(page.locator("#camera-state")).to_have_text("Recording video")
                    # A brief disturbance followed by the same scene must never invoke
                    # the positive vision fixture or create a notification.
                    page.wait_for_timeout(400)
                    page.evaluate("window.fakeFlashUntil=performance.now()+100")
                    page.wait_for_timeout(1500)
                    state = page.request.get(url + "/api/companion").json()
                    assert state["reminders"][0]["state"] == "armed"
                    assert state["pending"] == []
                    assert not state["observation"].get("job_id")
                    page.evaluate("window.fakeScene='active'")
                    if args.speech:
                        expect(page.locator("#reminders")).to_contain_text(
                            "Speaking", timeout=20000
                        )
                        page.get_by_role("button", name=re.compile("^Cancel reminder:")).click()
                        expect(page.locator("#reminders")).to_contain_text("Cancelled")
                        assert len(held_claims) == 1
                        route, response = held_claims[0]
                        route.fulfill(response=response)
                        page.unroute("**/api/deliveries/*/claim", hold_claim)
                        page.wait_for_function("!companion.delivering")
                        assert page.evaluate("window.reminderAudioStarts") == 0
                        requests.clear()
                        page.locator("#companion-message").fill(
                            "Remind me about water when I leave"
                        )
                        page.locator("#companion-send").click()
                    expect(page.locator("#reminders")).to_contain_text(
                        "Spoken; awaiting your acknowledgement"
                        if args.speech
                        else "Could not speak",
                        timeout=20000,
                    )
                    if args.speech:
                        page.get_by_role("button", name="Got it", exact=True).click()
                        expect(page.locator("#reminders")).to_contain_text("Acknowledged")
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
                        page.evaluate("""() => { window.testReminderPlay=HTMLAudioElement.prototype.play;
                            HTMLAudioElement.prototype.play=()=>Promise.reject(
                                new DOMException('Synthetic playback denial','NotAllowedError')); };""")
                        page.locator("#companion-message").fill(
                            "Remind me about water when I leave"
                        )
                        page.locator("#companion-send").click()
                        expect(page.locator("#reminders")).to_contain_text(
                            "Could not speak", timeout=20000
                        )
                        assert (
                            page.request.get(url + "/api/companion").json()["reminders"][0]["state"]
                            == "failed"
                        )
                        page.evaluate(
                            "() => { HTMLAudioElement.prototype.play=window.testReminderPlay; }"
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
                    if args.review_fixture:
                        imported = page.request.post(
                            url
                            + "/api/import?name=review-fixture.mp4&recorded_at=2026-10-19T10:00:00Z",
                            data=args.review_fixture.read_bytes(),
                            headers={"content-type": "application/octet-stream"},
                        ).json()
                        deadline = time.monotonic() + 30
                        while True:
                            imported_job = page.request.get(
                                url + "/api/jobs/" + imported["id"]
                            ).json()
                            if (
                                imported_job["status"] in {"succeeded", "failed"}
                                or time.monotonic() > deadline
                            ):
                                break
                            page.wait_for_timeout(100)
                        assert imported_job["status"] == "succeeded", imported_job
                        page.evaluate("refreshLibrary()")
                        page.locator("#scope").select_option(imported_job["result"]["video_id"])
                        page.locator("#object-query").fill("green")
                        page.locator("#history-mode").select_option("relevance")
                        page.locator("#ask-history").click()
                        confirm = page.get_by_role("button", name="This is the item", exact=True)
                        expect(confirm).to_be_visible(timeout=15000)
                        expect(page.locator("#answer-text")).to_contain_text("Is this the item")
                        before = page.locator("#answer-evidence img").get_attribute("src")
                        page.get_by_role("button", name="Not this item", exact=True).click()
                        expect(page.locator("#answer-evidence img")).not_to_have_attribute(
                            "src", before, timeout=15000
                        )
                        second_image = page.locator("#answer-evidence img").get_attribute("src")
                        page.locator("#companion-message").fill("nah man its not this item")
                        page.locator("#companion-send").click()
                        expect(page.locator("#answer-evidence img")).not_to_have_attribute(
                            "src", second_image, timeout=15000
                        )
                        assert page.locator("#answer-evidence img").get_attribute("src") != before
                        expect(page.locator("#companion-thread")).to_contain_text(
                            "nah man its not this item"
                        )
                        reviewed_result = page.request.get(
                            url + "/api/jobs/" + page.evaluate("companion.job")
                        ).json()["result"]["visual"]
                        page.locator("#companion-message").fill("Thanks, pause")
                        page.locator("#companion-send").click()
                        expect(page.locator("#companion-thread")).to_contain_text("Okay, paused.")
                        assert page.evaluate("companion.reviewCandidate === null")
                        expect(page.locator("#answer-panel")).to_be_hidden()
                        # Explicitly displaying a saved result establishes a new reference.
                        page.evaluate("output => showAnswer(output)", reviewed_result)
                        confirm.click()
                        expect(page.locator("#answer-text")).to_contain_text(
                            "You confirmed", timeout=10000
                        )
                        expect(page.locator("#answer-evidence")).to_contain_text(
                            "You confirmed this item"
                        )
                        assert (
                            page.request.get(url + "/api/companion").json()["conversations"][-1][
                                "plan"
                            ]["mode"]
                            == "user_confirmation"
                        )
                    library = [
                        {
                            "id": f"{index:032x}",
                            "name": f"Synthetic saved clip {index}",
                            "status": "ready",
                            "frame_count": 1,
                            "recorded_at": None,
                        }
                        for index in range(151)
                    ]
                    page.route(url + "/api/videos", lambda route: route.fulfill(json=library))
                    page.evaluate("refreshLibrary()")
                    expect(page.locator("#clips .clip-row")).to_have_count(50)
                    for count in [100, 150, 151]:
                        page.get_by_role("button", name="Show older clips", exact=True).click()
                        expect(page.locator("#clips .clip-row")).to_have_count(count)
                    expect(
                        page.locator(".clip-row")
                        .filter(has_text="Synthetic saved clip 150")
                        .get_by_role("button", name="Delete clip", exact=True)
                    ).to_be_enabled()
                    page.unroute(url + "/api/videos")
                    page.evaluate("refreshLibrary()")
                    page.screenshot(path=str(args.output / "companion.png"), full_page=True)
                    page.reload()
                    expect(page.locator("#companion-thread")).to_contain_text(
                        "Where is the green thing?", timeout=10000
                    )
                    if args.review_fixture:
                        expect(page.locator("#companion-thread")).to_contain_text(
                            "I confirmed the item", timeout=10000
                        )
                    assert not errors, errors
                    (args.output / "results.json").write_text(
                        json.dumps(
                            {
                                "browser_errors": errors,
                                "fake_devices": True,
                                "models": "deterministic boundary fixtures",
                                "synthetic_speech": args.speech,
                                "cancelled_pending_audio": args.speech,
                                "playback_denial_reports_failure": args.speech,
                                "older_library_access": True,
                                "candidate_rejection_and_confirmation": bool(args.review_fixture),
                                "conversational_rejection": bool(args.review_fixture),
                                "hidden_candidate_reference_cleared": bool(args.review_fixture),
                                "brief_flash_suppressed": True,
                                "sustained_activity_delivers": True,
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
