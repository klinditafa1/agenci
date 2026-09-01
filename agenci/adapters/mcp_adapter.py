"""Adapter for MCP (Model Context Protocol) servers.

This adapter is an MCP *client*: it launches (or connects to) an MCP
server over stdio, calls one configured tool per test case with the
test's ``input``, and normalizes the tool result into an
``AgentResponse``. This lets Agenci apply the same functional,
evaluation, and security-policy machinery it uses for chat-style agents
to individual MCP tools — useful for testing an MCP server directly,
independent of whichever LLM/agent framework ends up calling it in
production.

Built against the stable, long-standing MCP Python SDK client surface
(``ClientSession``, ``stdio_client``, ``StdioServerParameters``,
``list_tools``/``call_tool``) rather than any server-authoring helper,
since Agenci only ever acts as a client here.
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from typing import Any

from agenci.adapters.base import AgentResponse, ToolCallRecord


class MCPAdapterError(Exception):
    pass


def _build_tool_arguments(input: str, context: dict[str, Any] | None) -> dict[str, Any]:
    """Turns a test case's `input` (+ optional context) into tool call
    arguments.

    If `input` parses as a JSON object, it's used directly as the
    arguments (so a test author has full control over the call). If
    `context` provides an `mcp_arguments` mapping, that takes
    precedence entirely. Otherwise, `input` is passed as a single
    `input` string argument — the common case for a tool with one
    free-text parameter.
    """
    context = context or {}
    if isinstance(context.get("mcp_arguments"), dict):
        return dict(context["mcp_arguments"])

    try:
        parsed = json.loads(input)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    return {"input": input}


def _extract_text(result: Any) -> str:
    """Best-effort extraction of human-readable text from a CallToolResult."""
    content = getattr(result, "content", None)
    if content is None:
        return str(result)
    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(item))
    return "\n".join(parts) if parts else str(result)


class MCPAdapter:
    """Connects to an MCP server over stdio and calls one tool per test case."""

    def __init__(
        self,
        command: str,
        tool: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        try:
            import mcp  # noqa: F401
        except ImportError as exc:
            raise MCPAdapterError(
                "The 'mcp' adapter requires the mcp package. Install it with: pip install 'agenci[mcp]'"
            ) from exc

        self.command = command
        self.tool = tool
        self.args = args or []
        self.env = env or None
        self.timeout_seconds = timeout_seconds
        self._session: Any = None
        self._exit_stack: AsyncExitStack | None = None

    async def _ensure_session(self) -> Any:
        if self._session is not None:
            return self._session

        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        params = StdioServerParameters(command=self.command, args=self.args, env=self.env)

        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(stdio_client(params))
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._session = session
        return session

    async def run(self, input: str, context: dict[str, Any] | None = None) -> AgentResponse:
        arguments = _build_tool_arguments(input, context)
        try:
            session = await self._ensure_session()
        except Exception as exc:  # noqa: BLE001 - surfaced as a test failure, not a crash
            return AgentResponse(
                output="",
                error=f"Could not start/connect to MCP server: {type(exc).__name__}: {exc}",
            )

        try:
            result = await session.call_tool(self.tool, arguments)
        except Exception as exc:  # noqa: BLE001
            return AgentResponse(
                output="",
                error=f"MCP tool call {self.tool!r} failed: {type(exc).__name__}: {exc}",
            )

        is_error = bool(getattr(result, "isError", False))
        output = _extract_text(result)

        tool_call = ToolCallRecord(
            tool=self.tool,
            arguments=arguments,
            result=output,
            error=output if is_error else None,
        )

        if is_error:
            return AgentResponse(output=output, tool_calls=[tool_call], provider="mcp", error=output)

        return AgentResponse(output=output, tool_calls=[tool_call], provider="mcp", raw=result)

    async def aclose(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None
