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

    asyncio.run(realtime.serve(Socket(), voice))
    assert sessions[0].input.audio.frames.qsize() == 1
    assert sessions[0].options["turn_handling"]["endpointing"]["min_delay"] == 0
    assert sessions[0].closed


def replay_voice_tools(tmp_path, monkeypatch, scenario):
    """Exercise our real socket/turn persistence with only speech/model IO replaced."""
    sessions = []

    class Session:
        def __init__(self, **options):
            self.input = SimpleNamespace()
            self.output = SimpleNamespace()
            self.handlers = {}
            sessions.append(self)

        def on(self, name):
            def register(callback):
                self.handlers[name] = callback
                return callback

            return register

        async def start(self, *, agent, **options):
            self.agent = agent

        async def aclose(self):
            pass

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
    monkeypatch.setattr(realtime.openai, "LLM", lambda **options: None)
    monkeypatch.setattr(realtime.aiohttp, "ClientSession", HTTP)
    voice = Voice(tmp_path, None)
    token = voice.start()["token"]

    class Socket:
        headers: ClassVar = {"origin": "http://localhost", "host": "localhost"}

        def __init__(self):
            self.incoming = asyncio.Queue()
            self.tools = asyncio.Queue()
            self.scenario = None

        async def accept(self):
            pass

        async def receive_json(self):
            return {"token": token, "timezone": "Asia/Kolkata"}

        async def send_json(self, event):
            if event.get("type") == "tool":
                await self.tools.put(event)

        async def receive(self):
            if self.scenario is None:
                self.scenario = asyncio.create_task(scenario(sessions[0], self, voice))
            return await self.incoming.get()

        async def reply(self, tool, sources, review=None):
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
        socket = Socket()
        async with asyncio.timeout(5):
            serving = asyncio.create_task(realtime.serve(socket, voice))
            while socket.scenario is None:
                await asyncio.sleep(0)
            try:
                await socket.scenario
            finally:
                await socket.incoming.put({"type": "websocket.disconnect"})
                await serving

    asyncio.run(run())
    return voice.conversations


def transcribe(session, text):
    session.handlers["user_input_transcribed"](
        SimpleNamespace(is_final=True, language="en", transcript=text)
    )


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
        transcribe(session, "Where are my glasses?")
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
        session.agent.llm_node(context, [], {})
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
        transcribe(session, "Where is that notebook?")
        context.add_message(role="user", content="Where is that notebook?")
        session.agent.llm_node(context, [], {})
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
        transcribe(session, "Check again")
        context.add_message(role="user", content="Check again")
        session.agent.llm_node(context.copy(), [], {})
        assert all(
            "orange vase" not in (getattr(item, "text_content", "") or getattr(item, "output", ""))
            for item in calls[-1].items
        )
        assert all(
            "red cabinet" not in (getattr(item, "text_content", "") or getattr(item, "output", ""))
            for item in calls[-1].items
        )

    replay_voice_tools(tmp_path, monkeypatch, scenario)


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


def test_spoken_tools_dispatch_report_correction_and_historical_time(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        transcribe(session, "Correct my earlier phone report.")
        call = asyncio.create_task(session.agent.remember_statement(supersedes_turn_id="claim-1"))
        tool = await asyncio.wait_for(socket.tools.get(), 2)
        assert tool["action"] == {"action": "remember_statement", "supersedes_turn_id": "claim-1"}
        await socket.reply(tool, ["transcript:claim-1"])
        await call
        call = asyncio.create_task(
            session.agent.search_statements(query="phone", as_of="2026-11-06T18:00:00Z")
        )
        tool = await asyncio.wait_for(socket.tools.get(), 2)
        assert tool["action"]["as_of"] == "2026-11-06T18:00:00Z"
        await socket.reply(
            tool,
            ["transcript:claim-1"],
            {"statement_refs": [{"turn_id": "claim-1", "object_description": "phone"}]},
        )
        summary = await call
        assert '"statement_refs"' in summary
        call = asyncio.create_task(
            session.agent.search_statements(query="phone", selection="latest_report")
        )
        tool = await asyncio.wait_for(socket.tools.get(), 2)
        assert tool["action"] == {
            "action": "search_statements",
            "query": "phone",
            "selection": "latest_report",
        }
        await socket.reply(tool, ["transcript:claim-1"])
        await call
        complete_reply(session)

    conversations = replay_voice_tools(tmp_path, monkeypatch, scenario)
    assert conversations.recent()[-1]["sources"] == ["transcript:claim-1"]


def test_late_tool_result_does_not_attach_to_a_new_spoken_turn(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        transcribe(session, "Where are my glasses?")
        call = asyncio.create_task(
            session.agent.run_tool({"action": "search_statements", "query": "glasses"})
        )
        old_tool = await socket.tools.get()
        transcribe(session, "Actually, tell me the time.")
        await socket.reply(old_tool, ["obsolete-video"])
        await asyncio.gather(call, return_exceptions=True)
        complete_reply(session)

    conversations = replay_voice_tools(tmp_path, monkeypatch, scenario)
    turns = conversations.recent()
    assert turns[0]["status"] == "interrupted"
    assert turns[1]["status"] == "complete"
    assert turns[1]["sources"] == []


def test_spoken_lookup_dispatches_ten_day_window_exclusions_and_time_bound(tmp_path, monkeypatch):
    async def scenario(session, socket, voice):
        transcribe(session, "Look earlier than that moment for the other green item.")
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
        assert "not proof of identity" in summary
        complete_reply(session)

    conversations = replay_voice_tools(tmp_path, monkeypatch, scenario)
    assert conversations.recent()[-1]["sources"] == ["source-before-anchor"]
