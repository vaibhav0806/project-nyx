"""Opt-in hands-free browser smoke. Fake camera/mic, local ASR, fake cloud/vision."""

import argparse
import base64
import json
import os
import re
import socket
import subprocess
import sys
import time
import wave
from io import BytesIO
from pathlib import Path
from typing import ClassVar
from urllib.request import urlopen


def serve(root, port, conversation=False):
    import uvicorn
    from test_nyx import ColorEncoder

    from nyx.app import create_app
    from nyx.voice import Voice, WakeRecognizer

    class Provider:
        def transcribe(self, pcm):
            return "Hey Nyx, what's up?" if conversation else "Where are my glasses?"

        def route(self, transcript, context):
            return {
                "mode": "current",
                "object_query": "glasses",
                "seen_after": None,
                "seen_before": None,
            }

        def speak(self, text):
            output = BytesIO()
            with wave.open(output, "wb") as file:
                file.setnchannels(1)
                file.setsampwidth(2)
                file.setframerate(16000)
                file.writeframes(b"\0" * 16000)
            return base64.b64encode(output.getvalue()).decode()

    class Verifier:
        fingerprint: ClassVar = {"model": "synthetic-browser-verifier"}

        def inspect(self, image, query):
            return {
                "visibility": "visible",
                "location": "beside the laptop",
                "description": "synthetic glasses",
                "ambiguous": False,
            }

        def decide(self, state):
            return (
                {"action": "finish", "observation": 0}
                if state["observations"]
                else {"action": "inspect_current", "query": "glasses"}
            )

    uvicorn.run(
        create_app(
            root,
            encoder_factory=ColorEncoder,
            verifier_factory=Verifier,
            voice_factory=lambda root: Voice(root, Provider(), WakeRecognizer(), agent_mode=True),
        ),
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )


def run(audio, output, conversation=False):
    from playwright.sync_api import expect, sync_playwright

    output.mkdir(parents=True, exist_ok=False)
    with wave.open(str(audio)) as source:
        assert (source.getnchannels(), source.getsampwidth(), source.getframerate()) == (
            1,
            2,
            16000,
        )
        pcm = source.readframes(source.getnframes())
    padded = output / "fake-microphone.wav"
    with wave.open(str(padded), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(16000)
        file.writeframes(b"\0" * 16000 * 2 * 3 + pcm + b"\0" * 16000 * 2 * 8)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if k not in {"SARVAM_API_KEY", "OPENROUTER_API_KEY"}}
    env["HF_HUB_OFFLINE"] = "1"
    process = subprocess.Popen(
        [sys.executable, __file__, "--serve", str(output / "data"), "--port", str(port)]
        + (["--conversation"] if conversation else []),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=(output / "server.log").open("w"),
    )
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(150):
            try:
                with urlopen(url + "/api/voice", timeout=1):
                    break
            except OSError:
                if process.poll() is not None:
                    raise AssertionError("Smoke server exited; check server.log")
                time.sleep(0.1)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel="chrome",
                headless=True,
                args=[
                    "--use-fake-device-for-media-stream",
                    "--use-fake-ui-for-media-stream",
                    f"--use-file-for-fake-audio-capture={padded.resolve()}",
                    "--autoplay-policy=no-user-gesture-required",
                ],
            )
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            requests = []
            page.on("request", lambda request: requests.append(request.url))
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""window.playbackWakeWindows = [];
                const originalPlay = HTMLMediaElement.prototype.play;
                HTMLMediaElement.prototype.play = function() {
                    if (this.src.startsWith('blob:')) window.playbackWakeWindows.push(voice.wakeUntil);
                    return originalPlay.call(this);
                };""")
            page.goto(url)
            expect(page.locator("#camera-state")).to_have_text("Recording video", timeout=15000)
            expect(page.locator("#voice-mute")).to_be_visible(timeout=15000)
            if conversation:
                expect(page.locator("#voice-question")).to_contain_text("what's up", timeout=30000)
                expect(page.locator("#voice-answer")).to_contain_text(
                    "What can I help with", timeout=15000
                )
                assert not any(
                    "/api/inspect?" in request or "/api/answer" in request for request in requests
                )
            else:
                expect(page.locator("#voice-question")).to_contain_text("glasses", timeout=30000)
                expect(page.locator("#voice-answer")).to_contain_text(
                    "beside the laptop", timeout=15000
                )
            expect(page.locator("#voice-state")).to_contain_text(
                re.compile("Listening"), timeout=15000
            )
            assert page.evaluate("stream.getAudioTracks().length") == 0
            assert page.evaluate("voice.mic.getAudioTracks().length") == 1
            page.wait_for_function("!voice.working")
            assert page.evaluate(
                "window.playbackWakeWindows.length > 0 && window.playbackWakeWindows.every(value => value === 0)"
            )
            interrupted = page.evaluate(
                """async (encoded) => {
                await voice.cancel();
                window.syntheticPlaybackStopped = false;
                voice.player = {pause() { window.syntheticPlaybackStopped = true; }, removeAttribute() {}, onended: null, onerror: null};
                voice.playing = true;
                const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
                const samples = new Int16Array(bytes.buffer).slice(0, 40000);
                voice.parts = [samples];
                voice.length = samples.length;
                voice.lastProbe = 0;
                voice.wakeUntil = 0;
                voice.maybeProbe();
                if (voice.probePromise) await voice.probePromise;
                voice.reset();
                return window.syntheticPlaybackStopped && !voice.playing;
            }""",
                base64.b64encode(pcm).decode(),
            )
            assert interrupted, "A locally recognized wake phrase must stop existing playback"
            page.screenshot(path=str(output / "handsfree.png"), full_page=True)
            page.locator("#voice-mute").click()
            expect(page.locator("#voice-state")).to_contain_text("Microphone muted")
            assert page.evaluate("voice.mic === null && voice.context === null")
            expect(page.locator("#camera-state")).to_have_text("Recording video")
            page.locator("#stop").click()
            expect(page.locator("#camera-state")).to_have_text("Camera off")
            audio_checks = page.evaluate("""() => {
                const hear = voice.hear;
                const probe = voice.maybeProbe;
                const captured = [];
                voice.hear = async (pcm) => captured.push(pcm.length);
                voice.maybeProbe = () => {};
                voice.token = 'synthetic-no-network';
                voice.noise = 0.001;
                voice.reset();
                for (let i=0; i<40; i++) voice.samples(new Float32Array(320));
                const silenceIgnored = captured.length === 0;
                voice.working = true;
                for (let i=0; i<15; i++) voice.samples(new Float32Array(320).fill(0.006));
                for (let i=0; i<30; i++) voice.samples(new Float32Array(320));
                const retainedWhileBusy = voice.pending !== null && captured.length === 0;
                voice.working = false;
                voice.samples(new Float32Array(320));
                const quietSpeechCaptured = captured.length === 1;
                voice.hear = hear;
                voice.maybeProbe = probe;
                voice.token = null;
                voice.pending = null;
                voice.reset();
                return {silenceIgnored, retainedWhileBusy, quietSpeechCaptured};
            }""")
            assert all(audio_checks.values()), audio_checks
            page.reload()
            expect(page.locator("#voice-history")).to_contain_text(
                "what's up" if conversation else "Where are my glasses?", timeout=15000
            )
            page.locator("#voice-mute").click()
            page.locator("#stop").click()
            denied = browser.new_page()
            denied.add_init_script("""navigator.mediaDevices.getUserMedia = async () => {
                throw new DOMException('Synthetic permission denial', 'NotAllowedError');
            };""")
            denied.goto(url)
            expect(denied.locator("#voice-enable")).to_be_visible(timeout=10000)
            denied.wait_for_function("voice.token === null && !voice.starting")
            assert denied.evaluate("voice.mic === null")
            denied.close()

            late = browser.new_page()
            late.add_init_script("""window.originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                navigator.mediaDevices.getUserMedia = (options) => options.audio
                  ? new Promise((resolve) => { window.resolveMicrophone = resolve; })
                  : window.originalGetUserMedia(options);""")
            late.goto(url)
            late.wait_for_function('typeof window.resolveMicrophone === "function"')
            late.locator("#voice-mute").click()
            late.evaluate("""async () => {
                window.lateMic = await window.originalGetUserMedia({audio: true});
                window.resolveMicrophone(window.lateMic);
            }""")
            late.wait_for_function(
                'window.lateMic.getTracks().every(track => track.readyState === "ended")'
            )
            assert late.evaluate("voice.mic === null && voice.token === null")
            late.locator("#stop").click()
            late.close()
            assert not errors, errors
            result = {
                "browser": browser.version,
                "conversation_mode": conversation,
                "checks": [
                    "quiet speech detection and one utterance retained while busy; silence ignored",
                    "automatic camera and microphone request",
                    "real local ASR wake from synthetic speech",
                    "greeting skips vision" if conversation else "current-view tool dispatch",
                    "local wake probe stops existing playback",
                    "grounded response playback",
                    "video recordings have no audio track",
                    "independent microphone mute releases audio tracks/context",
                    "stop recording also mutes",
                    "conversation history survives reload",
                    "permission denial releases the local voice session",
                    "mute during permission request releases late-arriving microphone tracks",
                ],
                "limitations": [
                    "Cloud STT/TTS, agent decisions and visual judgment mocked in this browser check",
                    "this check makes no hosted-provider calls; provider validation is separate",
                    "no actual webcam or microphone opened",
                ],
            }
            (output / "results.json").write_text(json.dumps(result, indent=2))
            print(json.dumps(result, indent=2))
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--conversation", action="store_true")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.port, args.conversation)
    else:
        run(args.audio, args.output, args.conversation)
