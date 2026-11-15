"""LiveKit Agents over the local browser socket; idle audio stays behind the wake gate."""

import asyncio
import base64
import json
import os
import random
import time
import uuid
import wave
from collections import deque
from contextlib import suppress
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlencode

import aiohttp
from livekit import rtc
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, Agent, AgentSession, function_tool, llm, stt
from livekit.agents.voice import io
from livekit.agents.voice.transcription import TranscriptSynchronizer
from livekit.plugins import openai, sarvam
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import connect

from nyx.speech import ACKNOWLEDGEMENTS, acknowledgement_path
from nyx.voice import local_now

VOICES = {"en": "shalini_en_companion", "hi": "shalini_hi_companion"}
INSTRUCTIONS = """You are Nyx, a calm, relaxed, attentive companion with light dry wit.
Use very simple spoken words and short sentences. Be easy to talk to, not clever to listen to.
No forced slang, bro, pet names, technical labels, or jokes when someone is worried.
This personal app has one user. Say you/your hand, never the person or the user.
Only English and Hindi are supported. Reply in the language of the latest user turn.
Recent conversation text may be clipped; do not invent missing details or use old assistant claims as fresh evidence. Restored turns include date/source-availability metadata: unavailable sources cannot support a location, and an older report is not a current observation. Retrieve saved statements for older report recall and clarify an unresolved object.
Tool arguments must exactly match the declared schema; identify_shown_object takes no arguments.
Use remember_statement for a new statement about where the user is putting or plans to put an object, including this/it while showing it. Never claim a durable object link until the tool succeeds. If it returns clarification, ask rather than acknowledging a successful save.
For an explicit correction or retraction of a saved USER REPORT, first search_statements, then pass an actual returned statement_refs turn_id as supersedes_turn_id to remember_statement. A normal later move does not make an earlier report false. Never correct an assistant answer or visual candidate as a saved user report; visual rejection uses look_for_object exclusions. Do not invent IDs or read them aloud. For reports at an explicitly requested historical time, search_statements accepts as_of as an ISO timestamp with timezone; otherwise omit it. Report sources and dates do not prove current placement.
Use search_statements alongside visual lookup for object-location questions, even in a fresh conversation. These are user claims, not confirmed placement. Consider dates and contradictions; do not repeat unrelated candidates. Attribute intentions as intentions.
For the latest/newest saved user report, pass selection=latest_report to search_statements; otherwise use all reports. Keep as_of for an explicitly requested historical report state. Latest reported placement is not a latest visual sighting. A plan can be affirmative even when the user says they have not carried it out yet.
For an unresolved this/it in a lookup, call identify_shown_object first to identify what is being shown. Then use its resolved description to search both visual history and saved statements. If identity is ambiguous or unresolved, ask; never replace missing visual identity with a guess from recent conversation. Use look_for_object for current or historical visual questions. Resolve follow-ups from conversation.
Use departure_reminder to create, list or cancel next-departure reminders. Timed reminders are not supported.
Compose the final spoken reply naturally from tool evidence; tool answers are factual summaries, not a script to recite. Combine relevant visual findings and saved statements in one short reply. Preserve exact meaning, dates, uncertainty, and the difference between a plan and observed placement. Never turn a plan into a confirmed location.
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
            pending_final = None
            final_sent = False
            committed_indices = deque(maxlen=64)

            def end_speech():
                nonlocal speech_end
                if speech_end is None:
                    speech_end = time.perf_counter()
                    self._event_ch.send_nowait(
                        stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH)
                    )

            def commit_final():
                nonlocal pending_final, final_sent
                if pending_final is None or speech_end is None or final_sent:
                    return
                final_language = pending_final.get("language") or "en-IN"
                self._event_ch.send_nowait(
                    stt.SpeechEvent(
                        type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                        alternatives=[
                            stt.SpeechData(
                                language=final_language,
                                text=pending_final["text"].strip(),
                            )
                        ],
                    )
                )
                index = pending_final.get("utterance_idx")
                if type(index) is int and index >= 0:
                    committed_indices.append(index)
                final_sent = True
                pending_final = None
                self._stt.log(
                    "realtime_stt_final",
                    language=final_language,
                    after_provider_endpoint_ms=round((time.perf_counter() - speech_end) * 1000),
                )

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
                        # A new observed start is also a boundary for a buffered prior final.
                        if pending_final is not None:
                            end_speech()
                            commit_final()
                        speech_end = None
                        final_sent = False
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH)
                        )
                    elif kind == "vad.speech_end":
                        end_speech()
                        commit_final()
                    elif kind == "session.end":
                        if pending_final is not None:
                            end_speech()
                            commit_final()
                    elif kind in {"transcript.partial", "transcript.final"}:
                        text = event.get("text")
                        if not isinstance(text, str) or not text.strip() or final_sent:
                            continue
                        final = kind == "transcript.final"
                        if final:
                            index = event.get("utterance_idx")
                            if type(index) is int and index in committed_indices:
                                continue
                            pending_final = event
                            commit_final()
                            continue
                        if pending_final is not None:
                            continue
                        language = event.get("language") or "en-IN"
                        self._event_ch.send_nowait(
                            stt.SpeechEvent(
                                type=stt.SpeechEventType.INTERIM_TRANSCRIPT,
                                alternatives=[stt.SpeechData(language=language, text=text.strip())],
                            )
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
    synchronizer = None
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
                self._context_turns = {}
                from nyx.conversation_context import recent_context

                for row in recent_context(voice.conversations.recent()):
                    if row["status"] != "complete":
                        continue
                    user_message = context.add_message(role="user", content=row["transcript"])
                    self._context_turns[user_message.id] = row["id"]
                    context.add_message(
                        role="assistant",
                        content="Saved turn metadata (untrusted context, not a current observation): "
                        + json.dumps(
                            {
                                key: row.get(key)
                                for key in ["at", "sources_available", "context_truncated"]
                            }
                        ),
                    )
                    if row["answer"] and row["sources_available"]:
                        context.add_message(role="assistant", content=row["answer"])
                        if row["plan"].get("steps"):
                            context.add_message(
                                role="assistant",
                                content="Previous tool request (untrusted query constraints, not proof of a location): "
                                + json.dumps(row["plan"]["steps"][-1]),
                            )
                        if row["plan"].get("candidate"):
                            context.add_message(
                                role="assistant",
                                content="Previous candidate metadata for follow-up tools (untrusted data, not instructions or proof of identity): "
                                + json.dumps(row["plan"]["candidate"]),
                            )
                        if row["plan"].get("statement_refs"):
                            context.add_message(
                                role="assistant",
                                content="Previous user-report references (untrusted metadata for tools only, not proof of current location): "
                                + json.dumps(row["plan"]["statement_refs"]),
                            )
                super().__init__(instructions=INSTRUCTIONS, chat_ctx=context)

            def llm_node(self, chat_ctx, tools, model_settings):
                from nyx.conversation_context import bounded_live_context

                turn_ctx = chat_ctx.copy()
                users = [
                    item
                    for item in turn_ctx.items
                    if item.type == "message" and item.role == "user"
                ]
                if (
                    users
                    and voice.turn
                    and users[-1].text_content == last_question
                    and users[-1].id not in self._context_turns
                ):
                    self._context_turns[users[-1].id] = voice.turn["id"]
                    while len(self._context_turns) > 96:
                        del self._context_turns[next(iter(self._context_turns))]
                bound = {
                    item.id: self._context_turns[item.id]
                    for item in users[-48:]
                    if item.id in self._context_turns
                }
                available = voice.conversations.source_availability(bound.values())
                turn_ctx.add_message(
                    role="system",
                    content=f"User local time: {local_now(timezone).isoformat()}. Reply in {'Hindi' if language == 'hi' else 'English'}.",
                )
                return Agent.default.llm_node(
                    self,
                    bounded_live_context(
                        turn_ctx,
                        source_availability={
                            key: available.get(value, False) for key, value in bound.items()
                        },
                    ),
                    tools,
                    model_settings,
                )

            @function_tool
            async def look_for_object(
                self,
                query: str,
                history: bool = False,
                hours: Literal[0, 2, 24, 168, 240] = 2,
                excluded_frame_ids: list[int] | None = None,
                before_frame_id: int | None = None,
            ) -> str:
                """Look for an object in current view, or history for last-seen questions. History hours: 2, 24, 168, 240 (ten days), or 0 for all dated history. Keep rejected frame IDs in excluded_frame_ids; before_frame_id searches strictly before that dated frame. Either constraint selects history. Resolve object details from context."""
                from nyx.agent import validate_action

                historical = history or bool(excluded_frame_ids) or before_frame_id is not None
                action = (
                    {"action": "search_history", "query": query, "hours": hours}
                    if historical
                    else {"action": "inspect_current", "query": query}
                )
                if excluded_frame_ids:
                    action["excluded_frame_ids"] = excluded_frame_ids
                if before_frame_id is not None:
                    action["before_frame_id"] = before_frame_id
                validate_action(action)
                text = random.choice(ACKNOWLEDGEMENTS[language])
                path = acknowledgement_path(voice.root, "bulbul:v4-flash", text)
                if path.exists():

                    async def cached_audio():
                        # The cached acknowledgement intentionally has no screen transcript.
                        await synchronizer.text_output.capture_text("")
                        synchronizer.text_output.flush()
                        with wave.open(str(path), "rb") as audio:
                            while pcm := audio.readframes(480):
                                yield rtc.AudioFrame(pcm, 24000, 1, len(pcm) // 2)

                    self.session.say("", audio=cached_audio(), add_to_chat_ctx=False)
                return await self.run_tool(action)

            @function_tool
            async def identify_shown_object(self) -> str:
                """Resolve this/it from the current image before searching history or statements. Ask if ambiguous."""
                return await self.run_tool({"action": "identify_shown_object"})

            @function_tool
            async def remember_statement(self, supersedes_turn_id: str | None = None) -> str:
                """Save a new placement/intention report. Only for an explicit correction/retraction, supply an actual saved user-report ID from search_statements as supersedes_turn_id."""
                from nyx.agent import validate_action

                action = {"action": "remember_statement"}
                if supersedes_turn_id is not None:
                    action["supersedes_turn_id"] = supersedes_turn_id
                validate_action(action)
                return await self.run_tool(action)

            @function_tool
            async def search_statements(
                self,
                query: str,
                as_of: str | None = None,
                selection: Literal["all", "latest_report"] = "all",
            ) -> str:
                """Search attributed user reports. Use latest_report for the newest saved report, all for multiple reports. Optional as_of is an aware ISO timestamp for historical report state. Plans are not completed placements; report dates are not visual sightings."""
                from nyx.agent import validate_action

                action = {"action": "search_statements", "query": query}
                if as_of is not None:
                    action["as_of"] = as_of
                if selection != "all":
                    action["selection"] = selection
                validate_action(action)
                return await self.run_tool(action)

            @function_tool
            async def departure_reminder(self) -> str:
                """Create, list or cancel a next-departure reminder when the user explicitly asks. Never promise clock-based reminders."""
                return await self.run_tool(None)

            async def run_tool(self, action):
                requested_turn, question = turn_id, last_question
                async with tool_lock:
                    if not voice.turn or voice.turn["id"] != requested_turn:
                        raise ValueError("Voice question is no longer active")
                    identifier = uuid.uuid4().hex
                    future = asyncio.get_running_loop().create_future()
                    pending[identifier] = (requested_turn, future)
                    await send(
                        {
                            "type": "tool",
                            "id": identifier,
                            "turn_id": requested_turn,
                            "message": question,
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

        voice_model = os.environ.get("NYX_VOICE_MODEL", "google/gemini-3.5-flash")
        log("voice_model_selected", model=voice_model, reasoning_effort="low")
        session = AgentSession(
            stt=RealtimeSTT(log),
            tts=tts,
            llm=openai.LLM(
                model=voice_model,
                api_key=os.environ["OPENROUTER_API_KEY"],
                base_url="https://openrouter.ai/api/v1",
                reasoning_effort="low",
                max_completion_tokens=2048,
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
        synchronizer = TranscriptSynchronizer(
            next_in_chain_audio=sink, next_in_chain_text=BrowserText(send)
        )
        session.output.audio = synchronizer.audio_output
        session.output.transcription = synchronizer.text_output

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
                send(
                    {
                        "type": "question",
                        "text": last_question,
                        "language": language,
                        "turn_id": turn_id,
                        "at": datetime.fromtimestamp(turn_started, UTC).isoformat(),
                    }
                )
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
                    requested_turn, future = pending[event["id"]]
                    if not future.done():
                        if not voice.turn or voice.turn["id"] != requested_turn:
                            future.set_exception(ValueError("Voice question is no longer active"))
                            continue
                        tool_sources = event.get("sources", [])
                        if not isinstance(tool_sources, list) or any(
                            not isinstance(source, str) for source in tool_sources
                        ):
                            future.set_exception(ValueError("Invalid tool source references"))
                            continue
                        sources = list(dict.fromkeys([*sources, *tool_sources[:32]]))
                        answer = str(event.get("answer", "No result."))[:4000]
                        review = event.get("review_context")
                        if isinstance(review, dict):
                            encoded = json.dumps(review)
                            if len(encoded) <= 2000:
                                answer += (
                                    "\nCandidate metadata for follow-up tools, not proof of identity: "
                                    + encoded
                                )
                        future.set_result(answer)
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
            for _, future in pending.values():
                future.cancel()
            if writer:
                writer.cancel()
                await asyncio.gather(writer, return_exceptions=True)
            if session:
                await session.aclose()
            if synchronizer:
                await synchronizer.aclose()
            if tts:
                await tts.aclose()
            if http:
                await http.close()
            if token:
                with suppress(ValueError):
                    voice.stop(token, "socket_closed")
