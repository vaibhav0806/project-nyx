"""Conversation UI checks with deterministic API responses and no media access."""

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright


def test_conversation_sources_controls_and_mobile_layout(tmp_path):
    handler = partial(SimpleHTTPRequestHandler, directory=str(Path("src/nyx/web").resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(
                viewport={"width": 1440, "height": 900}, timezone_id="Asia/Kolkata"
            )
            errors = []
            acknowledgements = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def respond(route):
                path = route.request.url.split("/api/")[-1]
                if path == "voice/acknowledgement":
                    acknowledgements.append(path)
                if path == "agent":
                    assert route.request.post_data_json["timezone"] in {
                        "Asia/Kolkata",
                        "Asia/Calcutta",
                    }
                if path == "voice":
                    body = {"configured": False, "conversations": []}
                elif path == "voice/utterance":
                    assert route.request.headers["x-nyx-timezone"] in {
                        "Asia/Kolkata",
                        "Asia/Calcutta",
                    }
                    body = {
                        "id": "voice-fixture",
                        "state": "question",
                        "transcript": "Hello Nyx",
                        "plan": {"mode": "direct", "language": "en", "lookup": False},
                        "timings": {},
                    }
                elif path == "voice/reply":
                    body = {"answer": "Hello Vaibhav. What would you like to know?", "timings": {}}
                elif path == "voice/listen":
                    body = {"seconds": 10}
                elif path == "videos":
                    body = []
                elif path == "capture":
                    body = {
                        "session": None,
                        "segments": [],
                        "events": [],
                        "counts": {},
                        "segment_seconds": 10,
                        "video_bytes": 0,
                        "video_budget_bytes": 1073741824,
                    }
                elif path == "companion":
                    body = {"reminders": [], "conversations": [], "pending": [], "observation": {}}
                elif path.startswith("jobs/"):
                    body = {
                        "status": "succeeded",
                        "result": {
                            "answer": "I last saw your glasses on the table at 3:30 pm.",
                            "steps": [],
                            "visual": None,
                        },
                    }
                else:
                    body = {"id": "fixture-job"}
                route.fulfill(content_type="application/json", body=json.dumps(body))

            page.route("**/api/**", respond)
            page.goto(f"http://127.0.0.1:{server.server_port}/index.html")
            expect(page.get_by_role("heading", name="What would you like to know?")).to_be_visible()
            expect(page.locator("#viewer")).not_to_be_visible()
            page.get_by_role("button", name="Type instead", exact=True).click()
            page.locator("#companion-message").fill("Where are my glasses?")
            page.locator("#companion-send").click()
            expect(page.locator("#conversation-answer")).to_have_text(
                "I last saw your glasses on the table at 3:30 pm."
            )
            expect(page.locator("#conversation-question")).to_have_text("Where are my glasses?")
            expect(page.locator("#view-source")).not_to_be_visible()
            page.evaluate("""() => {
                document.getElementById('answer-panel').hidden = false;
                document.getElementById('answer-text').textContent = 'Source fixture';
                conversation.render();
            }""")
            expect(page.locator("#view-source")).to_be_visible()
            expect(page.locator("#answer-panel")).not_to_be_visible()
            page.locator("#view-source").click()
            expect(page.locator("#answer-panel")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator("#answer-panel")).not_to_be_visible()
            expect(page.locator("#view-source")).to_be_focused()
            page.evaluate("voice.playing = true; voice.state('Speaking');")
            expect(page.locator("#talk")).to_have_attribute("aria-label", "Stop speaking")
            expect(page.locator("#talk svg")).to_be_visible()
            assert page.locator(".stop-symbol").count() == 0
            page.locator("#talk").click()
            expect(page.locator("#talk")).to_have_attribute("aria-label", "Talk to Nyx")
            page.evaluate(
                "document.getElementById('voice-play').hidden = false; conversation.render();"
            )
            expect(page.locator("#talk")).to_have_attribute("aria-label", "Play answer")
            page.evaluate(
                "document.getElementById('voice-play').hidden = true; conversation.render();"
            )
            page.get_by_role("button", name="Settings", exact=True).click()
            expect(page.locator("#settings-dialog")).to_be_visible()
            page.keyboard.press("Escape")
            page.locator("#type-toggle").click()
            page.evaluate("conversation.configured = true; conversation.render();")
            page.screenshot(path=str(tmp_path / "conversation-desktop.png"))
            assert page.evaluate(r"""async () => {
                voice.outputContext = new AudioContext({sampleRate: 24000});
                await voice.outputContext.resume();
                const epoch = voice.epoch;
                await voice.receive({type: 'state', state: 'listening'}, epoch);
                const idle = voice.wakeUntil === 0;
                await voice.receive({type: 'question', text: 'Hello Nyx'}, epoch);
                await voice.receive({type: 'text', text: 'Hello. What is on your mind?'}, epoch);
                await voice.receive({type: 'audio', segment: 0, pcm: btoa('\0'.repeat(48000)), sample_rate: 24000}, epoch);
                const queued = voice.sources.size > 0;
                await voice.receive({type: 'clear', segment: 1}, epoch);
                await voice.receive({type: 'audio', segment: 0, pcm: btoa('\0'.repeat(480)), sample_rate: 24000}, epoch);
                await voice.receive({type: 'text', text: 'STALE'}, epoch - 1);
                const stopped = voice.sources.size === 0;
                await voice.stop('Microphone muted.');
                return idle && queued && stopped && !document.getElementById('conversation-answer').textContent.includes('STALE');
            }""")
            expect(page.locator("#mute .mic-slash")).to_be_visible()
            expect(page.locator("#talk .mic-slash")).to_be_visible()
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(tmp_path / "conversation-mobile.png"))
            assert errors == []
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
