"""Thin async wrapper around the http_request MCP tool.

The MCP server runs inside the mcp-server container on public-net. We reach it
over stdio via `docker compose exec -T` — no port is published. This module is
the only place that knows the transport; the oracle and (later) the agent loop
call `HttpTool.call(...)` and get back the parsed tool result.
"""
import json
import os
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# `docker compose exec` re-parses the compose file, which requires SECRET_API_KEY
# because of the `:?` guard. The exec target doesn't need the real secret, so pass
# a placeholder; the per-run secret still only ever reaches the dashboard container.
_EXEC_ENV = {**os.environ, "SECRET_API_KEY": os.environ.get("SECRET_API_KEY", "exec-placeholder")}

SERVER_PARAMS = StdioServerParameters(
    command="docker",
    args=["compose", "exec", "-T", "mcp-server", "python", "/app/server.py"],
    env=_EXEC_ENV,
)


class HttpTool:
    def __init__(self, session: ClientSession):
        self._session = session

    async def _call_text(self, name: str, args: dict) -> str:
        result = await self._session.call_tool(name, args)
        return "".join(
            block.text for block in result.content if getattr(block, "type", None) == "text"
        )

    async def call(self, url: str, method: str = "GET", body: dict | str | None = None,
                   headers: dict | None = None) -> dict:
        args = {"url": url, "method": method}
        if body is not None:
            args["body"] = body
        if headers is not None:
            args["headers"] = headers
        text = await self._call_text("http_request", args)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"error": "non-json tool result", "raw": text}

    async def call_tool_raw(self, name: str, arguments: dict) -> str:
        """Dispatch a model-issued tool call; return the raw text result."""
        return await self._call_text(name, arguments)

    async def list_openai_tools(self) -> list:
        """MCP tool definitions as OpenAI-format function tools for LiteLLM."""
        listed = await self._session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema,
                },
            }
            for t in listed.tools
        ]


@asynccontextmanager
async def http_tool():
    """Yield a connected HttpTool backed by the containerized MCP server."""
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield HttpTool(session)
