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
            page.evaluate(
                "async () => { voice.token = 'fixture'; await voice.hear(new Int16Array(1600)); }"
            )
            expect(page.locator("#conversation-answer")).to_have_text(
                "Hello Vaibhav. What would you like to know?"
            )
            expect(page.locator("#conversation-question")).to_have_text("Hello Nyx")
            assert acknowledgements == []
            expect(page.locator("#view-source")).not_to_be_visible()
            expect(page.locator("#talk")).to_have_attribute("aria-label", "Talk to Nyx")
            page.evaluate("voice.stop('Microphone muted.')")
            expect(page.locator("#conversation-state")).to_have_text("Microphone muted.")
            expect(page.locator("#mute .mic-slash")).to_be_visible()
            expect(page.locator("#talk .mic-slash")).to_be_visible()
            page.route(
                "**/api/voice/utterance",
                lambda route: route.fulfill(
                    content_type="application/json",
                    body=json.dumps({"state": "listening", "reason": "wake_not_recognized"}),
                ),
            )
            page.evaluate(
                "async () => { voice.token = 'fixture'; await voice.hear(new Int16Array(1600)); }"
            )
            expect(page.locator("#conversation-state")).not_to_contain_text("not recognized")
            assert page.evaluate("""async () => {
                const originalApi = api, OriginalAudio = window.Audio;
                let resolve, active = true, played = 0;
                api = () => new Promise(done => { resolve = done; });
                window.Audio = class {
                    async play() { played++; }
                    pause() {}
                    removeAttribute() {}
                };
                try {
                    const first = voice.sayChecking({id: 'fixture'}, () => active);
                    resolve({audio: btoa('synthetic audio')});
                    await first;
                    const started = played === 1 && voice.playing;
                    voice.stopPlayback();
                    const late = voice.sayChecking({id: 'fixture'}, () => active);
                    active = false;
                    resolve({audio: btoa('late synthetic audio')});
                    await late;
                    return started && played === 1 && !voice.playing;
                } finally { api = originalApi; window.Audio = OriginalAudio; }
            }""")
            assert page.evaluate(r"""async () => {
                const originalFetch = window.fetch;
                const context = new AudioContext({sampleRate: 16000});
                await context.resume();
                voice.context = context;
                voice.token = 'stream-fixture';
                let controller;
                const stream = new ReadableStream({start(c) { controller = c; }});
                window.fetch = async () => new Response(stream, {headers: {'content-type': 'application/x-ndjson'}});
                const encode = new TextEncoder();
                const send = event => controller.enqueue(encode.encode(JSON.stringify(event) + '\n'));
                const pending = voice.streamReply({id: 'stream-fixture'}, null, () => true, 'attempt', performance.now());
                try {
                    controller.enqueue(encode.encode('{"type":"te'));
                    controller.enqueue(encode.encode('xt","text":"First sentence."}\n'));
                    send({type: 'audio', pcm: btoa('\0'.repeat(480)), sample_rate: 24000});
                    await new Promise(resolve => setTimeout(resolve, 40));
                    const early = document.getElementById('conversation-answer').textContent === 'First sentence.' && voice.playing;
                    send({type: 'text', text: ' Second sentence.'});
                    send({type: 'done', answer: 'First sentence. Second sentence.', timings: {}});
                    controller.close();
                    const result = await pending;
                    const completed = result.answer === 'First sentence. Second sentence.' && !voice.playing;
                    let secondController, active = true;
                    const second = new ReadableStream({start(c) { secondController = c; }});
                    window.fetch = async () => new Response(second, {headers: {'content-type': 'application/x-ndjson'}});
                    const cancelled = voice.streamReply({id: 'cancelled'}, null, () => active, 'attempt', performance.now()).then(() => false, () => true);
                    secondController.enqueue(encode.encode(JSON.stringify({type: 'audio', pcm: btoa('\0'.repeat(48000)), sample_rate: 24000}) + '\n'));
                    await new Promise(resolve => setTimeout(resolve, 30));
                    const queued = voice.pcmSources.size > 0;
                    active = false;
                    voice.stopPlayback();
                    secondController.enqueue(encode.encode(JSON.stringify({type: 'text', text: 'STALE'}) + '\n'));
                    secondController.close();
                    return early && completed && queued && await cancelled && !voice.playing && voice.pcmSources.size === 0 && !document.getElementById('conversation-answer').textContent.includes('STALE');
                } finally {
                    window.fetch = originalFetch;
                    voice.stopPlayback();
                    await context.close();
                    voice.context = null;
                }
            }""")
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(tmp_path / "conversation-mobile.png"))
            assert errors == []
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
