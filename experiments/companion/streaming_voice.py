"""Bounded real LiveKit/OpenAI tool streaming; synthetic text only, no audio/hardware."""

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx2 as httpx
import openai
from livekit.agents import APIConnectOptions, llm
from livekit.plugins.openai import LLM

from experiments.companion.budget import BudgetedClient
from experiments.companion.embedding_replay import budget_snapshot
from experiments.companion.native_voice import bind_call, schemas
from nyx.agent_policy import AGENT_MODEL
from nyx.realtime import INSTRUCTIONS, INSTRUCTIONS_VERSION


class UsageStream(httpx.AsyncByteStream):
    """Observe provider SSE usage without changing bytes delivered to the actual SDK."""

    def __init__(self, original, guard):
        self.original, self.guard = original, guard
        self.pending = b""
        self.usage = None

    async def __aiter__(self):
        try:
            async for part in self.original:
                self.pending += part
                if len(self.pending) > 1024**2:
                    raise ValueError("SDK evaluation stream exceeded its line bound")
                while b"\n" in self.pending:
                    line, self.pending = self.pending.split(b"\n", 1)
                    if line.startswith(b"data:"):
                        raw = line[5:].strip()
                        if raw and raw != b"[DONE]":
                            event = json.loads(raw)
                            if event.get("usage"):
                                self.usage = event["usage"]
                yield part
        finally:
            if self.usage:
                self.guard.usage.append(self.usage)

    async def aclose(self):
        await self.original.aclose()


async def run(output, max_spend):
    output.mkdir(parents=True, exist_ok=False)
    captured = await asyncio.to_thread(schemas, output / "schema-session")
    selected_model = os.environ.get("NYX_AGENT_MODEL", AGENT_MODEL)
    guard = BudgetedClient(max_spend, max_requests=4)
    report = {
        "status": "running",
        "model": selected_model,
        "instructions_version": INSTRUCTIONS_VERSION,
        "budget_before": guard.initial,
        "cases": [],
        "limitations": "Actual installed LiveKit/OpenAI streaming parser and native tool schemas, synthetic text/evidence only. No microphone, STT/TTS, real vision or tool side effects. Retries disabled for bounded evaluation; runtime retry policy is separate. Final answers require inline semantic audit.",
    }

    async def before_request(request):
        if request.url.path != "/api/v1/chat/completions":
            raise ValueError("Unexpected SDK evaluation route")
        await asyncio.to_thread(guard.before_request)

    async def response_hook(response):
        response.stream = UsageStream(response.stream, guard)

    http = httpx.AsyncClient(
        event_hooks={"request": [before_request], "response": [response_hook]},
        timeout=45,
    )
    client = openai.AsyncOpenAI(
        api_key=guard.key,
        base_url="https://openrouter.ai/api/v1",
        max_retries=0,
        http_client=http,
    )
    model = LLM(
        model=selected_model,
        client=client,
        reasoning_effort="low",
        max_completion_tokens=2048,
        parallel_tool_calls=True,
        extra_body={"provider": {"data_collection": "deny"}},
    )

    async def generate(context):
        text, calls = [], []
        stream = model.chat(
            chat_ctx=context,
            tools=list(captured["tools"].values()),
            conn_options=APIConnectOptions(max_retry=0, timeout=45, liveness_timeout=45),
        )
        try:
            async with asyncio.timeout(60):
                async for chunk in stream:
                    if chunk.delta:
                        if chunk.delta.content:
                            text.append(chunk.delta.content)
                        calls.extend(chunk.delta.tool_calls or [])
        finally:
            await stream.aclose()
        return {
            "text": "".join(text),
            "calls": [call.model_dump() for call in calls],
        }

    try:
        for case in (
            {"id": "bottle-en", "text": "Where did you last see my blue bottle?"},
            {"id": "remote-hi", "text": "मेरा रिमोट आखिरी बार कहाँ दिखा था?"},
        ):
            context = llm.ChatContext()
            context.add_message(role="system", content=INSTRUCTIONS)
            context.add_message(
                role="system",
                content="Synthetic clock 2026-11-17T12:00:00Z; no current view. Available recorded history and saved memory. No scheduled reminders or proactive notifications.",
            )
            context.add_message(role="user", content=case["text"])
            row = {**case, "initial": await generate(context), "bindings": []}
            report["cases"].append(row)
            if not row["initial"]["calls"]:
                raise ValueError("SDK model did not select a tool")
            for call in row["initial"]["calls"]:
                arguments = bind_call(captured["tools"][call["name"]], call["arguments"])
                row["bindings"].append({"name": call["name"], "arguments": arguments})
                context.items.append(
                    llm.FunctionCall(
                        call_id=call["call_id"], name=call["name"], arguments=call["arguments"]
                    )
                )
                if call["name"] == "look_for_object":
                    evidence = {
                        "status": "candidate",
                        "answer": "Possible visual match on the sideboard yesterday, identity and current location unverified.",
                        "evidence": {"observed_at": "2026-11-16T10:00:00Z"},
                    }
                else:
                    evidence = {"status": "uncertain", "matches": [], "answer": "No saved report."}
                context.items.append(
                    llm.FunctionCallOutput(
                        call_id=call["call_id"],
                        name=call["name"],
                        output=json.dumps(evidence),
                        is_error=False,
                    )
                )
            row["continuation"] = await generate(context)
            if row["continuation"]["calls"] or not row["continuation"]["text"]:
                raise ValueError("SDK continuation did not finish within bound")
        report["status"] = "complete"
    finally:
        if report["status"] != "complete":
            report["status"] = "failed"
        await model.aclose()
        await client.close()
        report["budget_after"] = await asyncio.to_thread(budget_snapshot, guard)
        report["provider_usage"] = guard.usage
        report["requests"] = guard.requests
        (output / "results.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
    return {"status": report["status"], "cases": len(report["cases"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-spend", type=float, default=0.05)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.output, args.max_spend))))
