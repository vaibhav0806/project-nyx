"""Offline R12 reproductions. No devices, private data or provider requests."""

import ast
import asyncio
import json
import os
import platform
import subprocess
import tempfile
import time
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw

from nyx import realtime
from nyx.attention import select_activity_frames
from nyx.voice import Voice

REPO = Path(__file__).resolve().parents[2]


async def voice_sources(root):
    voice = Voice(root, None)
    token = voice.start()["token"]
    sessions = []
    result = {}

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

    class Socket:
        def __init__(self):
            self.headers = {"origin": "http://localhost", "host": "localhost"}
            self.tools = asyncio.Queue()
            self.step = 0

        async def accept(self):
            pass

        async def receive_json(self):
            return {"token": token, "timezone": "Asia/Kolkata"}

        async def send_json(self, event):
            if event.get("type") == "tool":
                await self.tools.put(event)

        async def receive(self):
            session = sessions[0]
            if self.step == 0:
                session.handlers["user_input_transcribed"](
                    SimpleNamespace(
                        is_final=True, language="en", transcript="Where are my glasses?"
                    )
                )
                self.saved_id = voice.turn["id"]

                async def calls():
                    await session.agent.run_tool(
                        {"action": "search_history", "query": "glasses", "hours": 2}
                    )
                    await session.agent.run_tool(
                        {"action": "search_statements", "query": "glasses"}
                    )

                self.call = asyncio.create_task(calls())
            if self.step < 2:
                event = await asyncio.wait_for(self.tools.get(), 2)
                sources = ["synthetic-video"] if self.step == 0 else []
                self.step += 1
                return {
                    "type": "websocket.receive",
                    "text": json.dumps(
                        {
                            "type": "tool_result",
                            "id": event["id"],
                            "answer": "Synthetic evidence.",
                            "sources": sources,
                        }
                    ),
                }
            await self.call
            session.handlers["conversation_item_added"](
                SimpleNamespace(
                    item=SimpleNamespace(
                        role="assistant",
                        text_content="Synthetic combined answer.",
                        interrupted=False,
                        created_at=time.time(),
                    )
                )
            )

            def saved():
                return next(r for r in voice.conversations.recent() if r["id"] == self.saved_id)

            result.update(sources_after_two_tools=saved()["sources"], status=saved()["status"])
            voice.conversations.invalidate("synthetic-video")
            result["sources_available_after_delete"] = saved()["sources_available"]
            return {"type": "websocket.disconnect"}

    with (
        patch.dict(os.environ, {"OPENROUTER_API_KEY": "fixture", "SARVAM_API_KEY": "fixture"}),
        patch.object(realtime, "AgentSession", Session),
        patch.object(realtime.sarvam, "TTS", TTS),
        patch.object(realtime.openai, "LLM", lambda **kwargs: None),
        patch.object(realtime.aiohttp, "ClientSession", HTTP),
    ):
        async with asyncio.timeout(8):
            await realtime.serve(Socket(), voice)
    return result


def source_panel():
    javascript = r"""
const fs = require('fs');
const source = fs.readFileSync('src/nyx/web/companion.js', 'utf8');
const method = source.slice(source.indexOf('  async request('), source.indexOf('\n  async cancel()'));
const elements = new Map();
const $ = id => {
  if (!elements.has(id)) elements.set(id, {hidden:false,replaceChildren(){}});
  return elements.get(id);
};
let nextResult;
const conversation = {render(){},begin(){},answer(){}};
const showAnswer = () => { $('answer-panel').hidden = false; };
const task = async () => nextResult;
const api = async () => ({});
const voice = {token:'fixture',turnVisual:{id:'fixture'}};
const companion = new Function('$','conversation','showAnswer','task','api','voice',`return {${method}}`)($,conversation,showAnswer,task,api,voice);
Object.assign(companion, {working:false,epoch:0,interruptDelivery(){},snapshot(){return{}},freezeContext(){return{}},async refresh(){}});
(async () => {
  nextResult = {answer:'synthetic sighting',steps:[],visual:{scope:{}},sources:['synthetic-video']};
  await companion.request('Where are my glasses?', {id:'fixture',request_id:'tool-1'}, {action:'search_history'});
  const afterVisual = $('answer-panel').hidden;
  nextResult = {answer:'synthetic statement',steps:[],sources:[]};
  await companion.request('Where are my glasses?', {id:'fixture',request_id:'tool-2'}, {action:'search_statements'});
  console.log(JSON.stringify({hidden_after_visual:afterVisual,hidden_after_statement:$('answer-panel').hidden,review_candidate:companion.reviewCandidate}));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    completed = subprocess.run(
        ["node"], input=javascript, text=True, capture_output=True, check=True, timeout=10, cwd=REPO
    )
    return json.loads(completed.stdout)


def small_object():
    background = Image.new("RGB", (1280, 720), (100, 100, 100))
    object_frame = background.copy()
    ImageDraw.Draw(object_frame).rectangle((600, 350, 624, 362), fill=(210, 210, 210))
    frames = [(i / 10, object_frame if 30 <= i < 60 else background) for i in range(100)]
    selected = select_activity_frames(frames)
    return {
        "visible_interval_seconds": [3.0, 5.9],
        "selected_offsets": [at for at, _ in selected],
        "selected_contains_object": any(3 <= at < 6 for at, _ in selected),
    }


def spoken_schema():
    tree = ast.parse((REPO / "src/nyx/realtime.py").read_text())
    lookup = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "look_for_object"
    )
    return [a.arg for a in lookup.args.args if a.arg != "self"]


def main():
    with tempfile.TemporaryDirectory(prefix="nyx-reliability-") as root:
        result = {
            "environment": {
                "python": platform.python_version(),
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "livekit_agents": version("livekit-agents"),
            },
            "voice_sources": asyncio.run(voice_sources(root)),
            "source_panel": source_panel(),
            "small_object": small_object(),
            "spoken_lookup_arguments": spoken_schema(),
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
