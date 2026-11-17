"""Actual shared voice SDK schemas/binding/dispatch with synthetic transport boundaries."""

import asyncio
import importlib.util
import inspect
from pathlib import Path

import pytest
from livekit.agents import ToolError, llm


def helpers_module():
    path = Path(__file__).resolve().parents[2] / "tests/test_realtime.py"
    spec = importlib.util.spec_from_file_location("nyx_realtime_replay_helpers", path)
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    return helpers


def schemas(root):
    helpers = helpers_module()
    captured = {}

    async def scenario(session, socket, voice):
        context = llm.ToolContext(session.agent.tools)
        captured["schemas"] = context.parse_function_tools("openai")
        captured["tools"] = context.function_tools

    with pytest.MonkeyPatch.context() as monkeypatch:
        helpers.replay_voice_tools(root, monkeypatch, scenario)
    return captured


def dispatch(root, text, calls):
    """Exercise actual SDK binding and Companion dispatch; external tool results are synthetic."""
    helpers = helpers_module()
    results = []

    async def scenario(session, socket, voice):
        helpers.transcribe(session, text)
        tools = llm.ToolContext(session.agent.tools).function_tools
        for call in calls:
            try:
                args, kwargs = llm.utils.prepare_function_arguments(
                    fnc=tools[call["name"]], json_arguments=call["arguments"]
                )
            except (ToolError, ValueError, KeyError, TypeError):
                results.append({"valid": False, "stage": "binding"})
                continue
            task = asyncio.create_task(getattr(session.agent, call["name"])(*args, **kwargs))
            requested = asyncio.create_task(socket.tools.get())
            try:
                done, _ = await asyncio.wait([task, requested], return_when=asyncio.FIRST_COMPLETED)
                if requested in done:
                    tool = requested.result()
                    await socket.reply(tool, [])
                    await task
                    results.append({"valid": True, "action": tool["action"]})
                else:
                    await task
                    results.append({"valid": False, "stage": "missing_request"})
            except (ValueError, TypeError):
                results.append({"valid": False, "stage": "dispatch"})
            finally:
                requested.cancel()
                task.cancel()
                await asyncio.gather(requested, task, return_exceptions=True)

    with pytest.MonkeyPatch.context() as monkeypatch:
        helpers.replay_voice_tools(root, monkeypatch, scenario)
    return results


def bind_call(tool, arguments):
    positional, keywords = llm.utils.prepare_function_arguments(fnc=tool, json_arguments=arguments)
    bound = inspect.signature(tool).bind(*positional, **keywords)
    bound.apply_defaults()
    return dict(bound.arguments)
