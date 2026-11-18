import asyncio
import json
import time
from types import SimpleNamespace
from typing import ClassVar
from urllib.parse import parse_qs, urlparse

from livekit import rtc

from nyx import realtime
from nyx.voice import Voice


def test_text_waits_for_actual_playback_and_stops_on_interruption():
    async def run():
        events = []

        async def send(event):
            events.append(event)

        sink = realtime.BrowserAudio(send, events.append)
        sync = realtime.TranscriptSynchronizer(
            next_in_chain_audio=sink, next_in_chain_text=realtime.BrowserText(send)
        )
        try:
            await sync.text_output.capture_text("Your phone is on the table beside your glasses.")
            sync.text_output.flush()
            await sync.audio_output.capture_frame(
                rtc.AudioFrame(bytes(24000 * 2 * 4), 24000, 1, 24000 * 4)
            )
            sync.audio_output.flush()
            await asyncio.sleep(0.1)
            assert not [e for e in events if e["type"] == "text"]
            sink.on_playback_started(created_at=time.time())
            async with asyncio.timeout(2):
                while not any(e["type"] == "text" for e in events):
                    await asyncio.sleep(0.02)
            sync.audio_output.clear_buffer()
            await asyncio.sleep(0.05)
            count = sum(e["type"] == "text" for e in events)
            await asyncio.sleep(0.2)
            assert sum(e["type"] == "text" for e in events) == count
        finally:
            await sync.aclose()

    asyncio.run(run())


def test_sarvam_partials_language_and_vad_reach_livekit(monkeypatch):
    packets = [
        {"event": "session.begin", "request_id": "fixture"},
        {"event": "vad.speech_start"},
        {"event": "transcript.partial", "text": "मेरा फोन", "language": "hi-IN"},
        {"event": "vad.speech_end"},
        {"event": "transcript.final", "text": "मेरा फोन कहाँ है?", "language": "hi-IN"},
    ]
    sent = []

    class Socket:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def send(self, data):
            sent.append(json.loads(data))

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(0)
            if packets:
                return json.dumps(packets.pop(0))
            await asyncio.Event().wait()

    monkeypatch.setenv("SARVAM_API_KEY", "fixture")
    monkeypatch.setattr(realtime, "connect", lambda *args, **kwargs: Socket())

    async def run():
        provider = realtime.RealtimeSTT(lambda *args, **kwargs: None)
        events = []
        async with provider.stream() as stream:
            stream.push_frame(rtc.AudioFrame(bytes(640), 16000, 1, 320))
            async with asyncio.timeout(2):
                async for event in stream:
                    events.append(event)
                    if event.type == realtime.stt.SpeechEventType.FINAL_TRANSCRIPT:
                        break
        await provider.aclose()
        assert [e.type.value for e in events] == [
            "start_of_speech",
            "interim_transcript",
            "end_of_speech",
            "final_transcript",
        ]
        assert events[-1].alternatives[0].language == "hi-IN"
        assert sent[0]["event"] == "audio_input"

    asyncio.run(run())


def test_realtime_endpoint_uses_native_vad_partials_and_wake_hint():
    url = urlparse(realtime.stt_url())
    query = parse_qs(url.query)
    assert url.path == "/speech-to-text-realtime/ws"
    assert query["model"] == ["saaras:v4"]
    assert query["stream_type"] == ["fast"]
    assert query["endpointing"] == ["vad"]
    assert query["language_code"] == ["auto"]
    assert json.loads(query["keyterms"][0]) == ["Nyx"]


def test_browser_playback_segments_ignore_duplicate_and_cancelled_acknowledgements():
    async def run():
        events = []

        async def send(event):
            events.append(event)

        sink = realtime.BrowserAudio(send, events.append)
        frame = rtc.AudioFrame(bytes(960), 24000, 1, 480)
        await sink.capture_frame(frame)
        sink.flush()
        await sink.capture_frame(frame)
        sink.flush()
        assert [e["segment"] for e in events if e["type"] == "flush"] == [0, 1]
        sink.played(0)
        sink.played(0)
        assert sink._pending_playback_count == 1
        sink.clear_buffer()
        sink.played(1)
        assert sink._pending_playback_count == 0
        assert not sink.pending
        await sink.capture_frame(frame)
        sink.flush()
        sink.played(3)
        assert sink._pending_playback_count == 0

    asyncio.run(run())


def test_initial_livekit_listening_does_not_open_cloud_audio_gate(tmp_path, monkeypatch):
    sessions = []

    class Session:
        def __init__(self, **options):
            self.options = options
            self.input = SimpleNamespace()
            self.output = SimpleNamespace()
            self.handlers = {}
            sessions.append(self)

        def on(self, event):
            def register(callback):
                self.handlers[event] = callback
                return callback

            return register

        async def start(self, **kwargs):
            self.handlers["agent_state_changed"](SimpleNamespace(new_state="listening"))

        async def aclose(self):
            self.closed = True

    class TTS:
        def __init__(self, **kwargs):
            pass

        def prewarm(self):
            pass

        async def aclose(self):
            pass

    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture")
    monkeypatch.setattr(realtime, "AgentSession", Session)
    monkeypatch.setattr(realtime.sarvam, "TTS", TTS)
    monkeypatch.setattr(realtime.openai, "LLM", lambda **kwargs: None)
    voice = Voice(tmp_path, None)
    token = voice.start()["token"]

    class Socket:
        headers: ClassVar = {"origin": "http://localhost", "host": "localhost"}
        packets = 0

        async def accept(self):
            pass

        async def receive_json(self):
            return {"token": token, "timezone": "Asia/Kolkata"}

        async def send_json(self, event):
            pass

        async def receive(self):
            self.packets += 1
            if self.packets == 1:
                assert voice.awake_until == 0
            if self.packets == 2:
                voice.awake_until = time.monotonic() + 30
            if self.packets == 3:
                return {"type": "websocket.disconnect"}
            return {"type": "websocket.receive", "bytes": bytes(640)}

    asyncio.run(realtime.serve(Socket(), voice, None))
    assert sessions[0].input.audio.frames.qsize() == 1
    assert sessions[0].closed


def replay_voice_tools(
    tmp_path,
    monkeypatch,
    scenario,
    *,
    memory_reply=None,
    session_factory=None,
    before_memory=None,
    visual_frames=None,
    calls=None,
):
    """Exercise our real socket/turn persistence with only speech/model IO replaced."""
    sessions = []

    class Session:
        def __init__(self, **options):
            self.options = options
            self.sdk = session_factory(**options) if session_factory else None
            self.input = self.sdk.input if self.sdk else SimpleNamespace()
            self.output = self.sdk.output if self.sdk else SimpleNamespace()
            self.handlers = {}
            sessions.append(self)

        def on(self, name):
            def register(callback):
                self.handlers[name] = callback
                if self.sdk:
                    self.sdk.on(name, callback)
                return callback

            return register

        async def start(self, *, agent, **options):
            self.agent = agent
            if self.sdk:
                await self.sdk.start(agent=agent, **options)

        async def aclose(self):
            if self.sdk:
                await self.sdk.aclose()

    class TTS:
        def __init__(self, **options):
            pass

        def prewarm(self):
            pass

        async def aclose(self):
            pass

    class HTTP:
        async def close(self):
            pass

    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture")
    monkeypatch.setattr(realtime, "AgentSession", Session)
    monkeypatch.setattr(realtime.sarvam, "TTS", TTS)
    monkeypatch.setattr(realtime.openai, "LLM", lambda **options: SimpleNamespace(**options))
    monkeypatch.setattr(realtime.aiohttp, "ClientSession", HTTP)
    voice = Voice(tmp_path, None)
    token = voice.start()["token"]

    class Socket:
        headers: ClassVar = {"origin": "http://localhost", "host": "localhost"}

        def __init__(self):
            self.incoming = asyncio.Queue()
            self.tools = asyncio.Queue()
            self.sent = []
            self.scenario = None

        async def accept(self):
            pass

        async def receive_json(self):
            return {"token": token, "timezone": "Asia/Kolkata"}

        async def send_json(self, event):
            self.sent.append(event)
            if event.get("type") == "freeze_context":
                await self.incoming.put(
                    {
                        "type": "websocket.receive",
                        "text": json.dumps(
                            {
                                "type": "visual_context",
                                "id": event["id"],
                                "visual_frames": visual_frames(event) if visual_frames else [],
                            }
                        ),
                    }
                )
            if event.get("type") == "tool":
                await self.tools.put(event)

        async def receive(self):
            if self.scenario is None:
                sessions[0].memory_lane = self.memory_lane
                self.scenario = asyncio.create_task(scenario(sessions[0], self, voice))
            return await self.incoming.get()

        async def reply(self, tool, sources, review=None):
            if voice.turn and voice.turn["id"] == tool["turn_id"]:
                with voice.conversations.connect() as db:
                    saved_plan = json.loads(
                        db.execute(
                            "SELECT plan FROM turns WHERE id=?", (tool["turn_id"],)
                        ).fetchone()[0]
                    )
                saved_plan["last_tool"] = {
                    "action": tool["action"],
                    "result": {
                        "answer": "Checked.",
                        "sources": sources,
                        **({"review_context": review} if review else {}),
                    },
                }
                voice.conversations.update_plan(tool["turn_id"], saved_plan, sources=sources)

            await self.incoming.put(
                {
                    "type": "websocket.receive",
                    "text": json.dumps(
                        {
                            "type": "tool_result",
                            "id": tool["id"],
                            "answer": "Checked.",
                            "sources": sources,
                            "review_context": review,
                        }
                    ),
                }
            )

    async def run():
        from test_personal_memory import Encoder, response

        from nyx.background_memory import BackgroundMemory
        from nyx.personal_memory import PersonalMemory

        loop = asyncio.get_running_loop()
        component = PersonalMemory(
            voice.conversations, Encoder(), memory_reply or (lambda *args: response())
        )
        process = component.process

        def prepare(turn_id, **kwargs):
            if before_memory:
                asyncio.run_coroutine_threadsafe(before_memory({"turn_id": turn_id}), loop).result(
                    timeout=4
                )
            return process(turn_id, **kwargs)

        component.process = prepare
        lane = BackgroundMemory(
            SimpleNamespace(conversations=voice.conversations, personal_memory=lambda: component)
        )
        socket = Socket()
        socket.memory_lane = lane
        async with asyncio.timeout(5):
            serving = asyncio.create_task(realtime.serve(socket, voice, lane, calls))
            while socket.scenario is None:
                await asyncio.sleep(0)
            try:
                await socket.scenario
            finally:
                await socket.incoming.put({"type": "websocket.disconnect"})
                await serving
                await asyncio.to_thread(lane.close)

    asyncio.run(run())
    return voice.conversations


async def transcribe(session, text):
    from livekit.agents import llm

    session.handlers["user_input_transcribed"](
        SimpleNamespace(is_final=True, language="en", transcript=text)
    )
    message = llm.ChatMessage(role="user", content=[text])
    await session.agent.on_user_turn_completed(llm.ChatContext(), message)


def complete_reply(session):
    session.handlers["conversation_item_added"](
        SimpleNamespace(
            item=SimpleNamespace(
                role="assistant",
                text_content="An evidence-backed reply.",
                interrupted=False,
                created_at=time.time(),
            )
        )
    )


def test_spoken_turn_preserves_all_tool_sources_for_deletion(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        await transcribe(session, "Where are my glasses?")
        for action, sources in [
            ({"action": "search_history", "query": "glasses", "hours": 2}, ["video-a"]),
            ({"action": "search_history", "query": "glasses", "hours": 24}, ["video-a", "video-b"]),
            ({"action": "search_statements", "query": "glasses"}, []),
        ]:
            call = asyncio.create_task(session.agent.run_tool(action))
            tool = await socket.tools.get()
            await socket.reply(tool, sources)
            await call
        complete_reply(session)

    conversations = replay_voice_tools(tmp_path, monkeypatch, scenario)
    saved = conversations.recent()[-1]
    assert saved["sources"] == ["video-a", "video-b"]
    assert saved["status"] == "complete"
    conversations.invalidate("video-a")
    assert not conversations.recent()[-1]["sources_available"]


def test_spoken_context_restores_source_state_and_bounds_actual_model_continuation(
    tmp_path, monkeypatch
):
    from livekit.agents import llm

    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    old = conversations.begin("Find my striped glasses case", {})
    conversations.finish(old, "Deleted-only sighting beside the orange vase", ["deleted-video"])
    with conversations.connect() as db:
        db.execute("UPDATE turns SET at='2026-11-06T12:00:00Z' WHERE id=?", (old,))
    conversations.invalidate("deleted-video")
    calls = []
    monkeypatch.setattr(
        realtime.Agent.default, "llm_node", lambda agent, ctx, tools, settings: calls.append(ctx)
    )

    async def scenario(session, socket, voice):
        restored = " ".join(
            item.text_content for item in session.agent.chat_ctx.items if item.type == "message"
        )
        assert "Deleted-only sighting" not in restored
        assert '"sources_available": false' in restored
        assert "2026-11-06T12:00:00Z" in restored
        context = llm.ChatContext()
        context.add_message(role="system", content="Trusted instructions")
        for index in range(80):
            context.add_message(role="user", content=f"Old request {index}")
            context.add_message(role="assistant", content="Old answer " * 200)
        context.add_message(role="user", content="What about that striped case?")
        context.items.extend(
            [
                llm.FunctionCall(
                    call_id="active", name="search_statements", arguments='{"query":"striped case"}'
                ),
                llm.FunctionCallOutput(
                    call_id="active",
                    name="search_statements",
                    output="Checked reports",
                    is_error=False,
                ),
            ]
        )
        await consume_node(session.agent.llm_node(context, [], {}))
        assert len(calls[0].items) <= 48
        active = [
            item.call_id
            for item in calls[0].items
            if item.type in {"function_call", "function_call_output"}
        ]
        assert active == ["active", "active"]
        assert len(context.items) > 160

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_live_continuation_withholds_evidence_deleted_after_session_start(tmp_path, monkeypatch):
    from livekit.agents import llm

    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    old = conversations.begin("Find my green notebook", {})
    conversations.finish(old, "Deleted sighting beside the orange vase", ["video-later-deleted"])
    calls = []
    monkeypatch.setattr(
        realtime.Agent.default, "llm_node", lambda agent, ctx, tools, settings: calls.append(ctx)
    )

    async def scenario(session, socket, voice):
        context = session.agent.chat_ctx.copy()
        context.items.extend(
            [
                llm.FunctionCall(
                    call_id="old-call",
                    name="look_for_object",
                    arguments='{"query":"green notebook"}',
                ),
                llm.FunctionCallOutput(
                    call_id="old-call",
                    name="look_for_object",
                    output="Unsafe deleted tool result: orange vase",
                    is_error=False,
                ),
            ]
        )
        voice.conversations.invalidate("video-later-deleted")
        await transcribe(session, "Where is that notebook?")
        context.add_message(role="user", content="Where is that notebook?")
        await consume_node(session.agent.llm_node(context, [], {}))
        sent = " ".join(
            getattr(item, "text_content", "") or getattr(item, "output", "")
            for item in calls[-1].items
        )
        assert "orange vase" not in sent
        assert '"sources_available": false' in sent
        assert "Where is that notebook?" in sent
        # The SDK keeps its copy; filtering must be repeated on subsequent continuations.
        assert any(
            getattr(item, "output", "").startswith("Unsafe deleted") for item in context.items
        )
        voice.conversations.finish(
            voice.turn["id"], "Second dynamic answer: red cabinet", ["dynamic-video"]
        )
        context.add_message(role="assistant", content="Second dynamic answer: red cabinet")
        voice.conversations.invalidate("dynamic-video")
        await transcribe(session, "Check again")
        context.add_message(role="user", content="Check again")
        await consume_node(session.agent.llm_node(context.copy(), [], {}))
        assert all(
            "orange vase" not in (getattr(item, "text_content", "") or getattr(item, "output", ""))
            for item in calls[-1].items
        )
        assert all(
            "red cabinet" not in (getattr(item, "text_content", "") or getattr(item, "output", ""))
            for item in calls[-1].items
        )

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_live_followup_retains_prior_answer_dependency(tmp_path, monkeypatch):
    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    old = conversations.begin("Where were my keys?", {})
    conversations.finish(old, "Possible keys beside the amber jar", ["video"])
    monkeypatch.setattr(realtime.Agent.default, "llm_node", lambda *args: None)

    async def scenario(session, socket, voice):
        await transcribe(session, "Repeat that location")
        context = session.agent.chat_ctx.copy()
        context.add_message(role="user", content="Repeat that location")
        await consume_node(session.agent.llm_node(context, [], {}))
        turn = voice.turn["id"]
        voice.conversations.finish(turn, "Beside the amber jar")
        assert voice.conversations.source_availability([turn])[turn]
        voice.conversations.invalidate("video")
        assert not voice.conversations.source_availability([turn])[turn]
        assert voice.conversations.source_availability([turn], input_only=True)[turn]

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_live_historical_recall_scopes_automatic_memory_on_continuation(tmp_path, monkeypatch):
    from test_personal_memory import Encoder, operation, response

    from nyx.personal_memory import PersonalMemory
    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    current = conversations.begin("My camera is in the cupboard", {})
    memory = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response(
            [operation(current, "My camera is in the cupboard", "CURRENT_CUPBOARD")]
        ),
    )
    memory_id = memory.process(current)["saved_ids"][0]
    conversations.finish(current, "Noted")
    with conversations.connect() as db:
        db.execute("UPDATE turns SET at='2026-11-12T12:00:00Z' WHERE id=?", (current,))
    calls = []
    monkeypatch.setattr(
        realtime.Agent.default, "llm_node", lambda agent, ctx, tools, settings: calls.append(ctx)
    )

    async def scenario(session, socket, voice):
        await transcribe(session, "What did I report as of November 11?")
        await asyncio.to_thread(session.memory_lane.wait, voice.turn["id"])
        context = session.agent.chat_ctx.copy()
        context.add_message(role="user", content="What did I report as of November 11?")
        await consume_node(session.agent.llm_node(context, [], {}))

        def background():
            return next(
                item.text_content
                for item in calls[-1].items
                if item.type == "message" and item.text_content.startswith("Memory context: ")
            )

        assert "CURRENT_CUPBOARD" in background()
        turn = voice.turn["id"]
        for cutoff in ["2026-11-11T12:00:00Z", None]:
            voice.conversations.update_plan(
                turn,
                {
                    "steps": [
                        {
                            "action": "recall_memory",
                            "query": "camera",
                            **({"as_of": cutoff} if cutoff else {}),
                        },
                        {"action": "inspect_current", "query": "camera"},
                    ]
                },
            )
            await consume_node(session.agent.llm_node(context, [], {}))
            assert ("CURRENT_CUPBOARD" in background()) is (cutoff is None)

    replay_voice_tools(
        tmp_path,
        monkeypatch,
        scenario,
        memory_reply=lambda *args: response(relevant_ids=[memory_id]),
    )


def test_spoken_restart_restores_previous_report_query_constraints(tmp_path, monkeypatch):
    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    old = conversations.begin(
        "Tell me the most recent report at that time",
        {
            "steps": [
                {
                    "action": "search_statements",
                    "query": "green phone",
                    "selection": "latest_report",
                    "as_of": "2026-11-07T12:00:00Z",
                }
            ]
        },
    )
    conversations.finish(old, "A saved report", [])

    async def scenario(session, socket, voice):
        restored = " ".join(
            item.text_content for item in session.agent.chat_ctx.items if item.type == "message"
        )
        assert '"selection": "latest_report"' in restored
        assert '"as_of": "2026-11-07T12:00:00Z"' in restored
        assert '"query": "green phone"' in restored

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_spoken_recall_dispatches_historical_time_and_preserves_sources(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        await transcribe(session, "What did I report that day?")
        call = asyncio.create_task(
            session.agent.recall_memory(query="phone", as_of="2026-11-06T18:00:00Z")
        )
        tool = await asyncio.wait_for(socket.tools.get(), 2)
        assert tool["action"] == {
            "action": "recall_memory",
            "query": "phone",
            "as_of": "2026-11-06T18:00:00Z",
        }
        await socket.reply(tool, ["transcript:claim-1"])
        assert json.loads(await call)["answer"] == "Checked."
        complete_reply(session)

    conversations = replay_voice_tools(tmp_path, monkeypatch, scenario)
    assert conversations.recent()[-1]["sources"] == ["transcript:claim-1"]


def test_late_tool_result_does_not_attach_to_a_new_spoken_turn(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        await transcribe(session, "Where are my glasses?")
        call = asyncio.create_task(
            session.agent.run_tool({"action": "search_statements", "query": "glasses"})
        )
        old_tool = await socket.tools.get()
        # LiveKit interrupts the old generation before invoking the next completed-turn hook.
        call.cancel()
        await asyncio.gather(call, return_exceptions=True)
        await transcribe(session, "Actually, tell me the time.")
        await socket.reply(old_tool, ["obsolete-video"])
        await asyncio.gather(call, return_exceptions=True)
        complete_reply(session)

    conversations = replay_voice_tools(tmp_path, monkeypatch, scenario)
    turns = conversations.recent()
    assert turns[0]["status"] == "interrupted"
    assert turns[1]["status"] == "complete"
    assert turns[1]["sources"] == []


def test_spoken_history_schema_advertises_only_executable_windows(tmp_path, monkeypatch):
    from livekit.agents import llm

    from nyx.agent import HISTORY_WINDOWS

    async def scenario(session, socket, voice):
        schemas = llm.ToolContext(session.agent.tools).parse_function_tools("openai")
        lookup = next(
            row["function"] for row in schemas if row["function"]["name"] == "look_for_object"
        )
        # Strict provider schemas allow null for optional parameters; SDK applies defaults.
        advertised = lookup["parameters"]["properties"]["hours"]["enum"]
        assert set(advertised) - {None} == set(HISTORY_WINDOWS)

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_spoken_lookup_dispatches_ten_day_window_exclusions_and_time_bound(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        await transcribe(session, "Look earlier than that moment for the other green item.")
        call = asyncio.create_task(
            session.agent.look_for_object(
                query="green item",
                history=True,
                hours=240,
                excluded_frame_ids=[7, 8],
                before_frame_id=42,
            )
        )
        tool = await socket.tools.get()
        assert tool["action"] == {
            "action": "search_history",
            "query": "green item",
            "hours": 240,
            "excluded_frame_ids": [7, 8],
            "before_frame_id": 42,
        }
        await socket.reply(
            tool,
            ["source-before-anchor"],
            {
                "frame_id": 6,
                "object_query": "green item",
                "observed_at": "2026-11-01T12:00:00Z",
            },
        )
        summary = await call
        assert '"frame_id": 6' in summary
        assert "review_context" in summary
        complete_reply(session)

    conversations = replay_voice_tools(tmp_path, monkeypatch, scenario)
    assert conversations.recent()[-1]["sources"] == ["source-before-anchor"]


async def consume_node(stream):
    return [chunk async for chunk in stream]


def test_server_audio_gate_tracks_activity_without_reopening_cancelled_input(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        source = session.input.audio.frames
        for activated, user_state, agent_state, expected in [
            (False, "speaking", "thinking", False),
            (True, "listening", "listening", False),
            (True, "speaking", "listening", True),
            (True, "listening", "thinking", True),
            (True, "listening", "speaking", True),
        ]:
            voice.awake_until = time.monotonic() - 1 if activated else 0
            session.user_state, session.agent_state = user_state, agent_state
            before = source.qsize()
            await socket.incoming.put({"type": "websocket.receive", "bytes": bytes(640)})
            await asyncio.sleep(0)
            assert source.qsize() - before == int(expected)

        await transcribe(session, "Are you there?")
        assert voice.awake_until > time.monotonic()
        voice.cancel(voice.token)
        session.handlers["user_state_changed"](SimpleNamespace(new_state="listening"))
        session.handlers["agent_state_changed"](SimpleNamespace(new_state="listening"))
        assert voice.awake_until == 0
        session.user_state, session.agent_state = "speaking", "thinking"
        before = source.qsize()
        await socket.incoming.put({"type": "websocket.receive", "bytes": bytes(640)})
        await asyncio.sleep(0)
        assert source.qsize() == before

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_stt_segments_do_not_replace_an_owned_turn_before_livekit_accepts_it(tmp_path, monkeypatch):
    from livekit.agents import llm
    from test_personal_memory import operation, response

    def memory_reply(payload, schema):
        turn = payload["current_turn"]
        assert voice.turn["id"] == turn["turn_id"]
        return response(
            [
                operation(
                    turn["turn_id"],
                    turn["text"],
                    "Plans to keep the bottle in the kitchen",
                    kind="plan",
                )
            ]
        )

    session = voice = None

    async def scenario(current_session, socket, current_voice):
        nonlocal session, voice
        session, voice = current_session, current_voice
        session.handlers["user_input_transcribed"](
            SimpleNamespace(is_final=True, language="en", transcript="I'll put this")
        )
        assert voice.conversations.recent() == []
        message = llm.ChatMessage(role="user", content=["I'll keep the blue bottle in the kitchen"])
        await session.agent.on_user_turn_completed(llm.ChatContext(), message)
        assert voice.turn["transcript"] == "I'll keep the blue bottle in the kitchen"
        session.handlers["user_input_transcribed"](
            SimpleNamespace(is_final=True, language="en", transcript="Are you there?")
        )
        await asyncio.to_thread(session.memory_lane.wait, voice.turn["id"])
        with voice.conversations.connect() as db:
            row = db.execute("SELECT kind,content FROM memories").fetchone()
        assert row["kind"] == "plan"
        assert row["content"] == "Plans to keep the bottle in the kitchen"

    replay_voice_tools(tmp_path, monkeypatch, scenario, memory_reply=memory_reply)


def test_transcript_preview_appends_segments_without_changing_durable_turns(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        for final, text in [
            (True, "Look at this."),
            (False, "I plan"),
            (True, "I plan to keep it in the kitchen."),
        ]:
            session.handlers["user_input_transcribed"](
                SimpleNamespace(is_final=final, language="en", transcript=text)
            )
            await asyncio.sleep(0)
        async with asyncio.timeout(1):
            while len([event for event in socket.sent if event.get("type") == "transcript"]) < 3:
                await asyncio.sleep(0)
        previews = [event for event in socket.sent if event.get("type") == "transcript"]
        assert [event["text"] for event in previews] == [
            "Look at this.",
            "Look at this. I plan",
            "Look at this. I plan to keep it in the kitchen.",
        ]
        assert previews[0]["new_turn"] is True and previews[-1]["new_turn"] is False
        assert [event["is_final"] for event in previews] == [True, False, True]
        assert previews[1]["committed_text"] == "Look at this."
        assert previews[1]["interim_text"] == "I plan"
        assert voice.turn is None and voice.conversations.recent() == []

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_rejected_transcription_notifies_user_without_creating_a_turn(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        session.options["stt"].log("realtime_stt_rejected", language="ml-IN", final=True)
        async with asyncio.timeout(1):
            while not any(event["type"] == "transcription_rejected" for event in socket.sent):
                await asyncio.sleep(0)
        assert voice.turn is None
        assert voice.conversations.recent() == []

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def scripted_livekit_session(monkeypatch):
    from livekit.agents import AgentSession, llm

    packets = asyncio.Queue()

    class Provider:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def send(self, data):
            pass

        def __aiter__(self):
            return self

        async def __anext__(self):
            return json.dumps(await packets.get())

    class Model(llm.LLM):
        def chat(self, **kwargs):
            raise AssertionError("No provider calls in this SDK lifecycle regression")

    def make_session(**options):
        options.update(llm=Model(), tts=None, vad=None)
        session = AgentSession(**options)
        session.output.set_audio_enabled(False)
        return session

    monkeypatch.setenv("SARVAM_API_KEY", "fixture")
    monkeypatch.setattr(realtime, "connect", lambda *args, **kwargs: Provider())
    return packets, make_session


def test_short_pause_continuation_is_one_completed_livekit_turn(tmp_path, monkeypatch):
    packets, make_session = scripted_livekit_session(monkeypatch)

    async def generate(agent, ctx, tools, settings):
        yield "Understood."

    async def utterance(text):
        for event in [
            {"event": "vad.speech_start"},
            {"event": "transcript.partial", "text": text, "language": "en-IN"},
            {"event": "vad.speech_end"},
            {"event": "transcript.final", "text": text, "language": "en-IN"},
        ]:
            await packets.put(event)

    async def scenario(session, socket, voice):
        await utterance("Please remember.")
        await asyncio.sleep(0.2)
        await utterance("I will keep the blue bag by the door.")
        async with asyncio.timeout(3):
            while not any(
                "blue bag" in row["transcript"] and row["answer"]
                for row in voice.conversations.recent()
            ):
                await asyncio.sleep(0.01)

    monkeypatch.setattr(realtime.Agent.default, "llm_node", generate)
    conversations = replay_voice_tools(
        tmp_path, monkeypatch, scenario, session_factory=make_session
    )
    rows = conversations.recent()
    assert len(rows) == 1
    assert rows[0]["transcript"] == "Please remember. I will keep the blue bag by the door."


def test_real_livekit_replies_and_accepts_next_speech_while_memory_is_pending(
    tmp_path, monkeypatch
):
    from test_personal_memory import operation, response

    packets, make_session = scripted_livekit_session(monkeypatch)
    memory_started, release_memory = asyncio.Event(), asyncio.Event()

    async def before_memory(event):
        if not memory_started.is_set():
            memory_started.set()
            await release_memory.wait()

    async def generate(agent, ctx, tools, settings):
        yield "I am here."

    def memory_reply(payload, schema):
        turn = payload["current_turn"]
        if "bottle" in turn["text"]:
            return response(
                [
                    operation(
                        turn["turn_id"],
                        turn["text"],
                        "Plans to keep the bottle in the kitchen",
                        kind="plan",
                    )
                ]
            )
        return response()

    async def utterance(text):
        for event in [
            {"event": "vad.speech_start"},
            {"event": "transcript.partial", "text": text, "language": "en-IN"},
            {"event": "vad.speech_end"},
            {"event": "transcript.final", "text": text, "language": "en-IN"},
        ]:
            await packets.put(event)

    async def scenario(session, socket, voice):
        await utterance("I will keep the bottle in the kitchen.")
        await memory_started.wait()
        original = voice.turn["id"]
        # A complete short reply must be generated before the slow memory path is released.
        async with asyncio.timeout(2):
            while not any(
                row["id"] == original and row["answer"] == "I am here."
                for row in voice.conversations.recent()
            ):
                await asyncio.sleep(0.01)
        await utterance("Are you there?")
        async with asyncio.timeout(2):
            while not any(
                row["transcript"] == "Are you there?" and row["answer"] == "I am here."
                for row in voice.conversations.recent()
            ):
                await asyncio.sleep(0.01)
        assert voice.turn["id"] != original
        release_memory.set()
        assert any(
            event.get("type") == "user_state" and event.get("state") == "speaking"
            for event in socket.sent
        )

    monkeypatch.setattr(realtime.Agent.default, "llm_node", generate)
    conversations = replay_voice_tools(
        tmp_path,
        monkeypatch,
        scenario,
        memory_reply=memory_reply,
        session_factory=make_session,
        before_memory=before_memory,
    )
    with conversations.connect() as db:
        assert (
            db.execute("SELECT content FROM memories").fetchone()[0]
            == "Plans to keep the bottle in the kitchen"
        )
    assert any(
        row["transcript"] == "Are you there?" and row["answer"] == "I am here."
        for row in conversations.recent()
    )


def test_final_spoken_input_prepares_memory_once_without_blocking_generation(tmp_path, monkeypatch):
    from livekit.agents import llm
    from test_personal_memory import operation, response

    calls, interpreted = [], []

    def memory_reply(payload, schema):
        interpreted.append(payload)
        turn = payload["current_turn"]
        return response([operation(turn["turn_id"], turn["text"], "Prefers tea without sugar")])

    async def generate(agent, ctx, tools, settings):
        calls.append(ctx)
        yield "fixture reply"

    monkeypatch.setattr(realtime.Agent.default, "llm_node", generate)

    async def scenario(session, socket, voice):
        await transcribe(session, "I prefer tea without sugar")
        context = llm.ChatContext()
        context.add_message(role="user", content="I prefer tea without sugar")
        assert await consume_node(session.agent.llm_node(context, [], {})) == ["fixture reply"]
        await asyncio.to_thread(session.memory_lane.wait, voice.turn["id"])
        await consume_node(session.agent.llm_node(context, [], {}))
        assert "Prefers tea without sugar" in " ".join(
            item.text_content for item in calls[-1].items if item.type == "message"
        )
        complete_reply(session)

    conversations = replay_voice_tools(tmp_path, monkeypatch, scenario, memory_reply=memory_reply)
    assert len(interpreted) == 1 and len(calls) == 2
    turn = conversations.recent()[-1]
    assert turn["sources"] == ["transcript:" + turn["id"]]


def test_spoken_generation_receives_same_owned_available_context_as_text(tmp_path, monkeypatch):
    from livekit.agents import llm

    calls = []

    async def generate(agent, ctx, tools, settings):
        calls.append(ctx)
        yield "fixture"

    monkeypatch.setattr(realtime.Agent.default, "llm_node", generate)

    async def scenario(session, socket, voice):
        await transcribe(session, "That isn't the item")
        with voice.conversations.connect() as db:
            plan = json.loads(
                db.execute("SELECT plan FROM turns WHERE id=?", (voice.turn["id"],)).fetchone()[0]
            )
        plan["available"] = {"presented_candidate": {"frame_id": 42}, "scheduled_reminders": False}
        voice.conversations.update_plan(voice.turn["id"], plan)
        ctx = llm.ChatContext()
        ctx.add_message(role="user", content="That isn't the item")
        await consume_node(session.agent.llm_node(ctx, [], {}))
        sent = " ".join(item.text_content for item in calls[-1].items if item.type == "message")
        assert '"frame_id": 42' in sent and '"scheduled_reminders": false' in sent

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_conversation_uses_raw_final_images_without_retaining_them_in_chat(tmp_path, monkeypatch):
    import base64
    from datetime import datetime, timedelta
    from io import BytesIO

    from livekit.agents import llm
    from PIL import Image

    picture = BytesIO()
    Image.new("RGB", (16, 16), "green").save(picture, format="PNG")
    snapshot = base64.b64encode(picture.getvalue()).decode()
    calls = []
    monkeypatch.setattr(
        realtime.Agent.default, "llm_node", lambda agent, ctx, tools, settings: calls.append(ctx)
    )

    def frames(event):
        at = datetime.fromisoformat(event["at"])
        return [
            {"snapshot": snapshot, "captured_at": (at - timedelta(seconds=2)).isoformat()},
            {"snapshot": snapshot, "captured_at": at.isoformat()},
        ]

    async def scenario(session, socket, voice):
        await transcribe(session, "Look at this; I will keep it in the kitchen.")
        context = llm.ChatContext()
        original = context.add_message(
            role="user", content="Look at this; I will keep it in the kitchen."
        )
        await consume_node(session.agent.llm_node(context, [], {}))
        current = next(
            item for item in calls[-1].items if item.type == "message" and item.role == "user"
        )
        assert len([part for part in current.content if isinstance(part, llm.ImageContent)]) == 2
        assert original.content == ["Look at this; I will keep it in the kitchen."]
        await asyncio.sleep(0)
        question = next(event for event in socket.sent if event["type"] == "question")
        freeze = next(event for event in socket.sent if event["type"] == "freeze_context")
        assert question["visual_context_ids"] == [freeze["id"]]
        assert question["context_at"] == freeze["at"]
        await transcribe(session, "What time is it?")
        context.add_message(role="user", content="What time is it?")
        await consume_node(session.agent.llm_node(context, [], {}))
        users = [item for item in calls[-1].items if item.type == "message" and item.role == "user"]
        assert all(isinstance(part, str) for part in users[0].content)
        assert len([part for part in users[-1].content if isinstance(part, llm.ImageContent)]) == 2
        assert not any(
            event.get("action", {}).get("action") == "process_memory" for event in socket.sent
        )

    replay_voice_tools(tmp_path, monkeypatch, scenario, visual_frames=frames)


def test_spoken_recall_does_not_wait_for_background_memory(tmp_path, monkeypatch):
    from test_personal_memory import operation, response

    started, release = asyncio.Event(), asyncio.Event()

    async def before_memory(event):
        if not started.is_set():
            started.set()
            await release.wait()

    def interpret(payload, schema):
        current = payload["current_turn"]
        return response([operation(current["turn_id"], current["text"], current["text"])])

    async def scenario(session, socket, voice):
        await transcribe(session, "My bottle is in the kitchen.")
        first = voice.turn["id"]
        await started.wait()
        await transcribe(session, "Where did I say the bottle is?")
        recall = asyncio.create_task(session.agent.recall_memory(query="bottle"))
        try:
            tool = await asyncio.wait_for(socket.tools.get(), 0.3)
            assert not release.is_set(), (
                "Recall should use committed memory without a write barrier"
            )
            with voice.conversations.connect() as db:
                assert not db.execute("SELECT 1 FROM memories WHERE turn_id=?", (first,)).fetchone()
            await socket.reply(tool, [])
            assert json.loads(await recall)["answer"] == "Checked."
        finally:
            release.set()
            recall.cancel()
            await asyncio.gather(recall, return_exceptions=True)

    replay_voice_tools(
        tmp_path, monkeypatch, scenario, before_memory=before_memory, memory_reply=interpret
    )


def test_memory_context_validation_runs_off_voice_event_loop(tmp_path, monkeypatch):
    import threading

    from livekit.agents import llm

    from nyx.personal_memory import PersonalMemory

    monkeypatch.setattr(realtime.Agent.default, "llm_node", lambda *args: None)

    async def scenario(session, socket, voice):
        await transcribe(session, "Hello again")
        await asyncio.to_thread(session.memory_lane.wait, voice.turn["id"])
        original = PersonalMemory._read_rows
        event_thread = threading.get_ident()
        checks = []

        def checked(*args, **kwargs):
            assert threading.get_ident() != event_thread
            assert kwargs.get("identifiers") is not None
            checks.append(True)
            return original(*args, **kwargs)

        monkeypatch.setattr(PersonalMemory, "_read_rows", staticmethod(checked))
        context = llm.ChatContext()
        context.add_message(role="user", content="Hello again")
        await consume_node(session.agent.llm_node(context, [], {}))
        assert checks

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_first_reply_receives_optional_saved_memory_while_writer_is_blocked(tmp_path, monkeypatch):
    from livekit.agents import llm
    from test_personal_memory import Encoder, operation, response

    from nyx.personal_memory import PersonalMemory
    from nyx.voice import Conversations

    conversations = Conversations(tmp_path)
    old = conversations.begin("I plan to leave my umbrella by the door.", {})
    component = PersonalMemory(
        conversations,
        Encoder(),
        lambda *args: response(
            [
                operation(
                    old,
                    "I plan to leave my umbrella by the door.",
                    "Plans to leave umbrella by the door",
                    kind="plan",
                )
            ]
        ),
    )
    component.process(old)
    conversations.finish(old, "A reply that must stay outside recent context.")
    for i in range(24):
        marker = conversations.begin(f"Neutral marker {i}.", {})
        conversations.finish(marker, "Received.")
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def before_memory(event):
        started.set()
        await release.wait()

    async def generate(agent, context, tools, settings):
        calls.append(context)
        yield "Concise fixture reply."

    monkeypatch.setattr(realtime.Agent.default, "llm_node", generate)

    async def scenario(session, socket, voice):
        try:
            assert session.options["llm"].reasoning_effort == realtime.AGENT_REASONING_EFFORT
            restored = " ".join(
                item.text_content for item in session.agent.chat_ctx.items if item.type == "message"
            )
            assert "umbrella" not in restored
            await transcribe(session, "Where did I say I would leave my umbrella?")
            await started.wait()
            context = llm.ChatContext()
            context.add_message(role="user", content="Where did I say I would leave my umbrella?")
            assert await consume_node(session.agent.llm_node(context, [], {})) == [
                "Concise fixture reply."
            ]
            early = next(
                item.text_content
                for item in calls[-1].items
                if item.type == "message"
                and item.text_content.startswith("Optional saved user memories")
            )
            assert "Plans to leave umbrella by the door" in early
            assert session.memory_lane.status(voice.turn["id"])["status"] == "pending"
            complete_reply(session)
            current = voice.turn["id"]
            voice.conversations.invalidate("transcript:" + old)
            assert not voice.conversations.source_availability([current])[current]
            await consume_node(session.agent.llm_node(context, [], {}))
            assert all(
                "Plans to leave umbrella" not in item.text_content
                for item in calls[-1].items
                if item.type == "message"
            )
        finally:
            release.set()

    replay_voice_tools(tmp_path, monkeypatch, scenario, before_memory=before_memory)


def test_slow_early_lookup_has_a_deadline_and_does_not_disable_further_recall(
    tmp_path, monkeypatch
):
    import threading

    from livekit.agents import llm

    from nyx.background_memory import BackgroundMemory

    started, release = threading.Event(), threading.Event()

    def slow(self, query):
        started.set()
        assert release.wait(3)
        return {"matches": []}

    monkeypatch.setattr(BackgroundMemory, "_candidates", slow)
    calls = []
    monkeypatch.setattr(
        realtime.Agent.default, "llm_node", lambda agent, ctx, tools, settings: calls.append(ctx)
    )

    async def scenario(session, socket, voice):
        try:
            await asyncio.wait_for(transcribe(session, "Can you help me remember?"), timeout=0.65)
            assert started.is_set() and not release.is_set()
            context = llm.ChatContext()
            context.add_message(role="user", content="Can you help me remember?")
            await consume_node(session.agent.llm_node(context, [], {}))
            assert any(
                '"status": "pending"' in item.text_content
                for item in calls[-1].items
                if item.type == "message"
                and item.text_content.startswith("Optional saved user memories")
            )
            lookup = asyncio.create_task(session.agent.recall_memory(query="umbrella"))
            tool = await asyncio.wait_for(socket.tools.get(), 1)
            assert tool["action"]["action"] == "recall_memory"
            await socket.reply(tool, [])
            assert json.loads(await lookup)["answer"] == "Checked."
        finally:
            release.set()

    replay_voice_tools(tmp_path, monkeypatch, scenario)
