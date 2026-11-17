import inspect

from livekit.agents import llm
from livekit.agents.llm.tool_context import find_function_tools

from nyx.agent_tools import AgentTools, tool_schemas


def test_voice_and_text_use_identical_native_tool_contracts(tmp_path, monkeypatch):
    from test_realtime import replay_voice_tools

    async def scenario(session, socket, voice):
        assert isinstance(session.agent, AgentTools)
        assert llm.ToolContext(session.agent.tools).parse_function_tools("openai") == tool_schemas()

    replay_voice_tools(tmp_path, monkeypatch, scenario)


def test_tools_can_be_bound_by_the_same_sdk_for_text_execution():
    tools = llm.ToolContext(find_function_tools(AgentTools())).function_tools
    args, kwargs = llm.utils.prepare_function_arguments(
        fnc=tools["look_for_object"],
        json_arguments={"query": "blue bag", "history": True, "hours": 240},
    )
    bound = inspect.signature(tools["look_for_object"]).bind(*args, **kwargs)
    assert bound.arguments["query"] == "blue bag" and bound.arguments["hours"] == 240


def test_shared_lookup_can_search_recordings_with_unknown_capture_dates():
    from nyx.agent_tools import bind_tool_action

    assert bind_tool_action("look_for_object", {"query": "blue bag", "undated": True}) == {
        "action": "search_matches",
        "query": "blue bag",
    }


def test_unknown_tool_arguments_are_rejected_instead_of_silently_dropped():
    import pytest

    from nyx.agent_tools import bind_tool_action

    with pytest.raises(ValueError, match="Unexpected tool arguments"):
        bind_tool_action("look_for_object", {"query": "bag", "unsupported_history": True})
