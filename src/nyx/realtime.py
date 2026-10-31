"""LiveKit Agents over the local browser socket; idle audio stays behind the wake gate."""

import asyncio
import base64
import json
import os
import random
import time
import uuid
import wave
from contextlib import suppress
from urllib.parse import urlencode

import aiohttp
from livekit import rtc
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, Agent, AgentSession, function_tool, llm, stt
from livekit.agents.voice import io
from livekit.plugins import openai, sarvam
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import connect

from nyx.speech import ACKNOWLEDGEMENTS, acknowledgement_path
from nyx.voice import local_now

VOICES = {"en": "ritu_en_reels", "hi": "ritu_hi_conversation"}
INSTRUCTIONS = """You are Nyx, a calm, relaxed, attentive companion with light dry wit.
Use very simple spoken words and short sentences. Be easy to talk to, not clever to listen to.
No forced slang, bro, pet names, technical labels, or jokes when someone is worried.
This personal app has one user. Say you/your hand, never the person or the user.
Only English and Hindi are supported. Reply in the language of the latest user turn.
Use look_for_object for current or historical visual questions. Resolve follow-ups from conversation.
Use departure_reminder to create, list or cancel next-departure reminders. Timed reminders are not supported.
Never guess a location or sighting. Preserve uncertainty and relative time from tool evidence.
Past conversation is not new visual evidence; use tools to check current or last-seen questions.
Use physical places, not image coordinates. Never recite verification boilerplate.
The lookup tool handles its own brief acknowledgement; do not add another let me check.
For general questions answer directly without tools or checking filler. Never claim to be human.
"""


def stt_url():
    return "wss://api.sarvam.ai/speech-to-text-realtime/ws?" + urlencode(
        {
            "model": "saaras:v4",
            "language_code": "auto",
            "encoding": "linear16",
            "sample_rate": 16000,
            "stream_type": "fast",
            "mode": "codemix",
            "endpointing": "vad",
            "silence_duration_ms": 400,
            "min_speech_duration_ms": 250,
            "keyterms": json.dumps(["Nyx"]),
            "prompt": "English and Hindi conversation with an assistant named Nyx (pronounced Niks).",
        }
    )


class RealtimeSTT(stt.STT):
    def __init__(self, log):
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=True))
        self.log = log

    async def _recognize_impl(self, buffer, *, language, conn_options):
        raise NotImplementedError("Use streaming STT")

    def stream(self, *, language=None, conn_options=DEFAULT_API_CONNECT_OPTIONS):
        return SarvamStream(stt=self, conn_options=conn_options, sample_rate=16000)


class SarvamStream(stt.SpeechStream):
    async def _run(self):
        async with connect(
            stt_url(),
            additional_headers={"api-subscription-key": os.environ["SARVAM_API_KEY"]},
            open_timeout=8,
            close_timeout=1,
            max_queue=16,
        ) as socket:
            self._stt.log("realtime_stt_connected", model="saaras:v4")

            async def send():
                async for frame in self._input_ch:
                    if isinstance(frame, rtc.AudioFrame):
                        await socket.send(
                            json.dumps(
                                {
                                    "event": "audio_input",
                                    "audio": base64.b64encode(frame.data).decode(),
                                }
                            )
                        )

            async def keepalive():
                while True:
                    await asyncio.sleep(20)
                    await socket.send(json.dumps({"event": "ping"}))

            sender = asyncio.create_task(send())
            heartbeat = asyncio.create_task(keepalive())
            speech_end = None
            try:
                async for packet in socket:
                    event = json.loads(packet)
                    kind = event.get("event")
                    if kind == "session.begin":
                        self._stt.log("realtime_stt_session", request_id=event.get("request_id"))
                    if kind == "error":
                        self._stt.log(
                            "realtime_stt_error",
                            code=event.get("code"),
                            fatal=event.get("is_fatal"),
                        )
                        if event.get("is_fatal"):
                            raise RuntimeError("Sarvam realtime transcription failed")
                        continue
                    if kind == "vad.speech_start":
                        speech_end = None
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH)
                        )
                    elif kind == "vad.speech_end":
                        speech_end = time.perf_counter()
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH)
                        )
                    elif kind in {"transcript.partial", "transcript.final"}:
                        text = event.get("text", "").strip()
                        if not text:
                            continue
                        final = kind == "transcript.final"
                        language = event.get("language", "en-IN")
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(
                                type=stt.SpeechEventType.FINAL_TRANSCRIPT
                                if final
                                else stt.SpeechEventType.INTERIM_TRANSCRIPT,
                                alternatives=[stt.SpeechData(language=language, text=text)],
                            )
                        )
                        if final:
                            self._stt.log(
                                "realtime_stt_final",
                                language=language,
                                after_provider_endpoint_ms=round(
                                    (time.perf_counter() - speech_end) * 1000
                                )
                                if speech_end
                                else None,
                            )
            finally:
                sender.cancel()
                heartbeat.cancel()
                await asyncio.gather(sender, heartbeat, return_exceptions=True)


class BrowserInput(io.AudioInput):
    def __init__(self):
        super().__init__(label="nyx-browser")
        self.frames = asyncio.Queue(100)

    async def __anext__(self):
        frame = await self.frames.get()
        if frame is None:
            raise StopAsyncIteration
        return frame


class BrowserAudio(io.AudioOutput):
    def __init__(self, send, emit):
        super().__init__(
            label="nyx-browser",
            capabilities=io.AudioOutputCapabilities(pause=False),
            sample_rate=24000,
        )
        self.send = send
        self.emit_event = emit
        self.pending = {}
        self.segment = 0
        self.seconds = 0

    async def capture_frame(self, frame):
        await super().capture_frame(frame)
        self.seconds += frame.duration
        await self.send(
            {
                "type": "audio",
                "segment": self.segment,
                "pcm": base64.b64encode(frame.data).decode(),
                "sample_rate": frame.sample_rate,
            }
        )

    def flush(self):
        super().flush()
        if not self.seconds:
            return
        self.pending[self.segment] = self.seconds
        self.emit_event({"type": "flush", "segment": self.segment})
        self.segment += 1
        self.seconds = 0

    def played(self, segment):
        if not self.pending or segment != next(iter(self.pending)):
            return
        seconds = self.pending.pop(segment)
        self.on_playback_finished(playback_position=seconds, interrupted=False)

    def clear_buffer(self):
        super().flush()
        while self._pending_playback_count:
            self.on_playback_finished(playback_position=0, interrupted=True)
        self.pending.clear()
        self.segment += 1
        self.seconds = 0
        self.emit_event({"type": "clear", "segment": self.segment})


class BrowserText(io.TextOutput):
    def __init__(self, send):
        super().__init__(label="nyx-browser", next_in_chain=None)
        self.send = send

    async def capture_text(self, text):
        await self.send({"type": "text", "text": text})

    def flush(self):
        pass


async def serve(socket, voice):
    origin = socket.headers.get("origin")
    if origin and origin not in {
        "http://" + socket.headers.get("host", ""),
        "https://" + socket.headers.get("host", ""),
    }:
        await socket.close(code=1008)
        return
    await socket.accept()
    session = None
    writer = None
    http = None
    tts = None
    pending = {}
    tool_lock = asyncio.Lock()
    token = None
    try:
        auth = await asyncio.wait_for(socket.receive_json(), 5)
        token = auth.get("token")
        voice.check(token)
        timezone = auth.get("timezone")
        local_now(timezone)
        outgoing = asyncio.Queue(128)

        async def send(event):
            await outgoing.put(event)

        async def write():
            while True:
                await socket.send_json(await outgoing.get())

        writer = asyncio.create_task(write())

        def log(event, **details):
            voice.conversations.event(event, **details)

        source = BrowserInput()
        sink = BrowserAudio(send, outgoing.put_nowait)
        language = "en"
        last_question = ""
        turn_id = None
        turn_started = 0
        sources = []
        http = aiohttp.ClientSession()
        tts = sarvam.TTS(
            http_session=http,
            model="bulbul:v4-flash",
            speaker=VOICES["en"],
            target_language_code="en-IN",
            speech_sample_rate=24000,
            output_audio_codec="linear16",
            enable_preprocessing=True,
        )

        class Companion(Agent):
            def __init__(self):
                context = llm.ChatContext()
                for row in voice.conversations.recent()[-12:]:
                    if row["status"] != "complete":
                        continue
                    context.add_message(role="user", content=row["transcript"])
                    if row["answer"] and row["sources_available"]:
                        context.add_message(role="assistant", content=row["answer"])
                super().__init__(instructions=INSTRUCTIONS, chat_ctx=context)

            def llm_node(self, chat_ctx, tools, model_settings):
                turn_ctx = chat_ctx.copy()
                turn_ctx.add_message(
                    role="system",
                    content=f"User local time: {local_now(timezone).isoformat()}. Reply in {'Hindi' if language == 'hi' else 'English'}.",
                )
                return Agent.default.llm_node(self, turn_ctx, tools, model_settings)

            @function_tool
            async def look_for_object(
                self, query: str, history: bool = False, hours: int = 2
            ) -> str:
                """Look for an object in current view, or history for last-seen questions. Resolve the object description from context. History hours may be 2, 24, 168 or 0 for all dated history."""
                if hours not in {0, 2, 24, 168}:
                    hours = 2
                text = random.choice(ACKNOWLEDGEMENTS[language])
                path = acknowledgement_path(voice.root, "bulbul:v4-flash", text)
                if path.exists():

                    async def cached_audio():
                        with wave.open(str(path), "rb") as audio:
                            while pcm := audio.readframes(480):
                                yield rtc.AudioFrame(pcm, 24000, 1, len(pcm) // 2)

                    self.session.say("", audio=cached_audio(), add_to_chat_ctx=False)
                action = (
                    {"action": "search_history", "query": query, "hours": hours}
                    if history
                    else {"action": "inspect_current", "query": query}
                )
                return await self.run_tool(action)

            @function_tool
            async def departure_reminder(self) -> str:
                """Create, list or cancel a next-departure reminder when the user explicitly asks. Never promise clock-based reminders."""
                return await self.run_tool(None)

            async def run_tool(self, action):
                async with tool_lock:
                    identifier = uuid.uuid4().hex
                    future = asyncio.get_running_loop().create_future()
                    pending[identifier] = future
                    await send(
                        {
                            "type": "tool",
                            "id": identifier,
                            "turn_id": turn_id,
                            "message": last_question,
                            "action": action,
                        }
                    )
                    try:
                        result = await asyncio.wait_for(future, 90)
                        return result
                    finally:
                        pending.pop(identifier, None)
                        if not future.done() or future.cancelled():
                            await send({"type": "cancel_tool", "id": identifier})

        session = AgentSession(
            stt=RealtimeSTT(log),
            tts=tts,
            llm=openai.LLM(
                model="openai/gpt-6-luna",
                api_key=os.environ["OPENROUTER_API_KEY"],
                base_url="https://openrouter.ai/api/v1",
                reasoning_effort="low",
                max_completion_tokens=700,
                parallel_tool_calls=True,
                extra_body={"provider": {"data_collection": "deny"}},
            ),
            turn_handling={
                "turn_detection": "stt",
                "endpointing": {"min_delay": 0, "max_delay": 1.5},
                "interruption": {
                    "mode": "vad",
                    "min_duration": 0.5,
                    "resume_false_interruption": False,
                },
                "preemptive_generation": {"enabled": True},
            },
            user_away_timeout=None,
        )
        session.input.audio = source
        session.output.audio = sink
        session.output.transcription = BrowserText(send)

        @session.on("user_input_transcribed")
        def transcribed(event):
            nonlocal language, last_question, turn_id, sources, turn_started
            if not event.is_final:
                return
            detected = "hi" if (event.language or "").startswith("hi") else "en"
            if detected != language:
                language = detected
                tts.update_options(
                    target_language_code="hi-IN" if language == "hi" else "en-IN",
                    speaker=VOICES[language],
                )
            last_question = event.transcript
            sources = []
            if voice.turn and not any(
                row["id"] == voice.turn["id"] and row["status"] == "complete"
                for row in voice.conversations.recent()
            ):
                voice.conversations.finish(voice.turn["id"], status="interrupted")
            turn_started = time.time()
            turn_id = voice.conversations.begin(
                last_question, {"mode": "livekit", "language": language}
            )
            voice.turn = {"id": turn_id, "transcript": last_question}
            asyncio.create_task(
                send({"type": "question", "text": last_question, "language": language})
            )

        @session.on("conversation_item_added")
        def item_added(event):
            if (
                getattr(event.item, "role", None) == "assistant"
                and turn_id
                and event.item.text_content
                and not event.item.interrupted
                and event.item.created_at >= turn_started
            ):
                voice.conversations.finish(turn_id, event.item.text_content, sources)

        @session.on("agent_state_changed")
        def state_changed(event):
            if event.new_state == "listening" and last_question:
                voice.awake_until = time.monotonic() + 10
            asyncio.create_task(send({"type": "state", "state": event.new_state}))

        @session.on("error")
        def session_error(event):
            recoverable = getattr(event.error, "recoverable", False)
            log("livekit_error", error_type=type(event.error).__name__, recoverable=recoverable)
            if not recoverable:
                asyncio.create_task(
                    send(
                        {"type": "error", "message": "Voice connection stopped. Please reconnect."}
                    )
                )

        @session.on("metrics_collected")
        def metrics(event):
            value = event.metrics.model_dump()
            log(
                "livekit_metrics",
                metrics={
                    k: v
                    for k, v in value.items()
                    if isinstance(v, (str, int, float, bool, type(None)))
                },
            )

        await session.start(agent=Companion(), session_host=False)
        tts.prewarm()
        await send({"type": "ready"})
        while True:
            packet = await socket.receive()
            if packet["type"] == "websocket.disconnect":
                break
            voice.check(token)
            if packet.get("bytes") is not None:
                pcm = packet["bytes"]
                if not 0 < len(pcm) <= 96000 or len(pcm) % 2:
                    raise ValueError("Invalid microphone frame")
                if time.monotonic() < voice.awake_until:
                    await source.frames.put(rtc.AudioFrame(pcm, 16000, 1, len(pcm) // 2))
            else:
                event = json.loads(packet["text"])
                if event.get("type") == "played":
                    sink.played(event.get("segment"))
                elif event.get("type") == "playback_started":
                    segment = event.get("segment")
                    if segment == sink.segment or segment in sink.pending:
                        sink.on_playback_started(created_at=time.time())
                        log(
                            "browser_playback_started",
                            after_transcript_ms=event.get("after_transcript_ms"),
                        )
                elif event.get("type") == "interrupt":
                    session.interrupt()
                elif event.get("type") == "tool_result" and event.get("id") in pending:
                    future = pending[event["id"]]
                    if not future.done():
                        sources = event.get("sources", [])[:32]
                        future.set_result(str(event.get("answer", "No result."))[:4000])
    except (TimeoutError, WebSocketDisconnect):
        pass
    except Exception:
        with suppress(Exception):
            await socket.send_json(
                {"type": "error", "message": "Voice connection stopped. Please reconnect."}
            )
        raise
    finally:
        from anyio import CancelScope

        with CancelScope(shield=True):
            for future in pending.values():
                future.cancel()
            if writer:
                writer.cancel()
                await asyncio.gather(writer, return_exceptions=True)
            if session:
                await session.aclose()
            if tts:
                await tts.aclose()
            if http:
                await http.close()
            if token:
                with suppress(ValueError):
                    voice.stop(token, "socket_closed")
