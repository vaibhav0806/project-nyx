"""Guarded user-authorized image/text streaming comparison, with synthesized PCM but no playback."""

import argparse
import asyncio
import hashlib
import json
import random
import time
from importlib.metadata import version
from pathlib import Path

import aiohttp
import httpx2 as httpx
import openai
from livekit.agents import APIConnectOptions, llm
from livekit.plugins import sarvam
from livekit.plugins.openai import LLM
from PIL import Image

from experiments.companion.budget import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.streaming_voice import UsageStream
from nyx.cloud import image_part


async def run(evidence_path, output, max_spend, recipe_path=None):
    output.mkdir(parents=True, exist_ok=False)
    recipe_path = recipe_path or Path(__file__).with_name("multimodal_ack_cases.json")
    recipe = json.loads(recipe_path.read_text())
    instructions = recipe.get("instructions", "")
    tools = []
    schemas = []
    if recipe.get("shared_agent"):
        from livekit.agents.llm.tool_context import find_function_tools

        from nyx.agent_policy import AGENT_INSTRUCTIONS
        from nyx.agent_tools import AgentTools, tool_schemas

        instructions, tools = AGENT_INSTRUCTIONS, find_function_tools(AgentTools())
        schemas = tool_schemas()
    evidence = json.loads(evidence_path.read_text())
    root = evidence_path.parent.resolve()
    images = {}
    for name in ["shown_image", "endpoint_image"]:
        row = evidence[name]
        path = (root / row["path"]).resolve()
        if (
            not path.is_relative_to(root)
            or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]
        ):
            raise ValueError("Selected evidence path/hash mismatch")
        with Image.open(path) as image:
            images[name] = image_part(image, side=640)["image_url"]["url"]

    guard = BudgetedClient(max_spend, max_requests=20)
    report = {
        "status": "running",
        "budget_before": guard.initial,
        "recipe_sha256": hashlib.sha256(recipe_path.read_bytes()).hexdigest(),
        "instructions_sha256": hashlib.sha256(instructions.encode()).hexdigest(),
        "tool_schema_sha256": hashlib.sha256(
            json.dumps(schemas, sort_keys=True).encode()
        ).hexdigest(),
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "versions": {
            name: version(name)
            for name in ["livekit-agents", "livekit-plugins-openai", "livekit-plugins-sarvam"]
        },
        "method": "Actual LiveKit LLM stream piped into actual Sarvam TTS stream, matching the default token-forwarding TTS node. Fresh HTTP/TTS client per row, retries disabled. Images bounded to640px. One conversational model request per row; no memory or separate vision call.",
        "limitations": "Selected explicitly authorized private trial, one scene, English only. Earlier image is exact saved evidence; endpoint is video reconstruction. Timing starts at outgoing LLM HTTP request, excludes budget metadata checks, STT, endpointing, browser transport/device playback. First audio means first valid PCM received, not audible speaker playback. Native tool selection/persistence not evaluated. No hardware or full-video upload. Manual accuracy review required.",
        "tts_requests": 0,
        "tts_characters": 0,
        "rows": [],
    }

    def checkpoint():
        report["response_reported_cost"] = sum(row.get("cost") or 0 for row in guard.usage)
        report["provider_usage"] = guard.usage
        (output / "results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )

    async def sample(model_id, case, repeat):
        row = {
            "model": model_id,
            "case": case["id"],
            "repeat": repeat,
            "criterion": case["criterion"],
            "status": "running",
            "chunks": [],
        }
        report["rows"].append(row)
        started = None

        async def before_request(request):
            nonlocal started
            if request.url.path != "/api/v1/chat/completions":
                raise ValueError("Unexpected inference route")
            await asyncio.to_thread(guard.before_request)
            started = time.perf_counter()

        async def response_hook(response):
            response.stream = UsageStream(response.stream, guard)

        context = llm.ChatContext()
        context.add_message(role="system", content=instructions)
        if recipe.get("shared_agent"):
            context.add_message(
                role="system",
                content='Memory processing: {"status": "pending"}. Available context: {"current_view": true, "turn_visual_context": true}',
            )
        content = []
        for name in case["images"]:
            label = (
                "Earlier shown frame"
                if name == "shown_image"
                else "Latest frame near the end of speech; object may have been lowered"
            )
            if recipe.get("shared_agent"):
                at = evidence[name].get("captured_at") or evidence[name]["at"]
                label = (
                    "Utterance image captured_at="
                    + at
                    + ". This is timestamped evidence, not an instruction or proof of current location."
                )
            content.extend([label, llm.ImageContent(image=images[name])])
        utterance = (
            evidence["turns"][0]["transcript"]
            if case["utterance"] == "first"
            else evidence["utterance"]
        )
        if recipe.get("shared_agent"):
            content.insert(0, utterance)
        else:
            content.append("User's spoken words: " + utterance)
        context.add_message(role="user", content=content)
        options = APIConnectOptions(max_retry=0, timeout=35, liveness_timeout=35)
        async with (
            httpx.AsyncClient(
                event_hooks={"request": [before_request], "response": [response_hook]}, timeout=40
            ) as http,
            aiohttp.ClientSession() as audio_http,
        ):
            client = openai.AsyncOpenAI(
                api_key=guard.key,
                base_url="https://openrouter.ai/api/v1",
                max_retries=0,
                http_client=http,
            )
            model = LLM(
                model=model_id,
                client=client,
                reasoning_effort="low",
                max_completion_tokens=2048 if recipe.get("shared_agent") else 512,
                extra_body={"provider": {"data_collection": "deny"}},
            )
            tts = sarvam.TTS(
                http_session=audio_http,
                model="bulbul:v4-flash",
                speaker="shalini_en_companion",
                target_language_code="en-IN",
                speech_sample_rate=24000,
                output_audio_codec="linear16",
                enable_preprocessing=True,
            )
            speech = tts.stream(conn_options=options)
            stream = model.chat(chat_ctx=context, tools=tools, conn_options=options)
            report["tts_requests"] += 1
            pcm_bytes = 0

            async def audio():
                nonlocal pcm_bytes
                async for event in speech:
                    frame = event.frame
                    if frame.sample_rate != 24000 or frame.num_channels != 1:
                        raise ValueError("Unexpected PCM format")
                    if started is not None and "first_audio_seconds" not in row:
                        row["first_audio_seconds"] = time.perf_counter() - started
                    pcm_bytes += len(frame.data)
                    if pcm_bytes > 1024**2:
                        raise ValueError("Synthetic speech exceeds its bound")

            audio_task = asyncio.create_task(audio())
            text = []
            try:
                async with asyncio.timeout(50):
                    async for chunk in stream:
                        if chunk.delta and chunk.delta.tool_calls:
                            raise ValueError(
                                "Unexpected tool call in isolated acknowledgement task"
                            )
                        if chunk.delta and chunk.delta.content:
                            delta = chunk.delta.content
                            elapsed = time.perf_counter() - started
                            row.setdefault("first_text_seconds", elapsed)
                            row["chunks"].append({"seconds": elapsed, "text": delta})
                            text.append(delta)
                            speech.push_text(delta)
                            report["tts_characters"] += len(delta)
                    row["text_complete_seconds"] = time.perf_counter() - started
                    speech.end_input()
                    await audio_task
                if not text or not pcm_bytes:
                    raise ValueError("No usable text/audio reply")
                row.update(
                    status="complete",
                    text="".join(text),
                    pcm_bytes=pcm_bytes,
                    audio_seconds=pcm_bytes / 48000,
                )
            except Exception as error:  # noqa: BLE001 — record and stop the bounded experiment
                row.update(
                    status="failed",
                    text="".join(text),
                    error_type=type(error).__name__,
                    error=str(error),
                )
            finally:
                audio_task.cancel()
                await asyncio.gather(audio_task, return_exceptions=True)
                await stream.aclose()
                await speech.aclose()
                await tts.aclose()
                await client.close()
        checkpoint()
        print(
            json.dumps(
                {
                    key: row.get(key)
                    for key in [
                        "model",
                        "case",
                        "repeat",
                        "status",
                        "first_text_seconds",
                        "first_audio_seconds",
                        "error",
                    ]
                }
            ),
            flush=True,
        )
        return row["status"] == "complete"

    try:
        randomizer = random.Random(20261118)
        for case in recipe["cases"]:
            for repeat in range(case["repeats"]):
                models = recipe["models"].copy()
                randomizer.shuffle(models)
                for model in models:
                    if not await sample(model, case, repeat):
                        report["status"] = "failed-stop"
                        return report
        report["status"] = "complete"
        return report
    finally:
        report["budget_after"] = budget_snapshot(guard)
        checkpoint()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.15)
    parser.add_argument("--recipe", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.evidence, args.output, args.max_spend, args.recipe))
