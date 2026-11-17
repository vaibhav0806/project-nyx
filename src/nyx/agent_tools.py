"""One native tool contract for the conversational voice and text adapters."""

from typing import Literal

from livekit.agents import function_tool, llm
from livekit.agents.llm.tool_context import find_function_tools


class AgentTools:
    async def acknowledge_lookup(self):
        """Voice supplies cached audio; text execution needs no audio acknowledgement."""

    async def run_tool(self, action):
        raise NotImplementedError("An execution adapter must provide run_tool")

    @function_tool
    async def look_for_object(
        self,
        query: str,
        history: bool = False,
        hours: Literal[0, 2, 24, 168, 240] = 2,
        excluded_frame_ids: list[int] | None = None,
        before_frame_id: int | None = None,
        undated: bool = False,
    ) -> str:
        """Look for an object in current view, or history for last-seen questions. History hours: 2, 24, 168, 240 (ten days), or 0 for all dated history. Keep rejected frame IDs in excluded_frame_ids; before_frame_id searches strictly before that dated frame. Either constraint selects history. Use undated=true to search recordings by similarity when capture dates are unknown. Resolve object details from context."""
        from nyx.agent import validate_action

        historical = history or bool(excluded_frame_ids) or before_frame_id is not None
        action = (
            {"action": "search_matches", "query": query}
            if undated
            else {"action": "search_history", "query": query, "hours": hours}
            if historical
            else {"action": "inspect_current", "query": query}
        )
        if excluded_frame_ids:
            action["excluded_frame_ids"] = excluded_frame_ids
        if before_frame_id is not None:
            action["before_frame_id"] = before_frame_id
        validate_action(action)
        await self.acknowledge_lookup()
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


def tool_schemas():
    return llm.ToolContext(find_function_tools(AgentTools())).parse_function_tools("openai")


class _ActionTools(AgentTools):
    async def run_tool(self, action):
        if action is None:
            raise ValueError("This tool does not support direct execution")
        return action


def bind_tool_action(name, arguments):
    """Use the voice SDK's argument binding and the shared tool body for text calls."""
    import asyncio
    import inspect
    import json

    tools = llm.ToolContext(find_function_tools(_ActionTools())).function_tools
    if name not in tools:
        raise ValueError("Unknown tool")
    arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
    if not isinstance(arguments, dict):
        raise TypeError("Tool arguments must be an object")
    if set(arguments) - set(inspect.signature(tools[name]).parameters):
        raise ValueError("Unexpected tool arguments")
    args, kwargs = llm.utils.prepare_function_arguments(fnc=tools[name], json_arguments=arguments)
    return asyncio.run(tools[name](*args, **kwargs))
