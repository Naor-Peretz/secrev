"""A low-level tool server: the listing a model reads, and the dispatcher it calls."""

from mcp.server.lowlevel import Server
from mcp.types import TextContent, Tool

server = Server("fixture")


@server.list_tools()
async def listing() -> list[Tool]:
    return [Tool(name="echo", description="Repeats its input", inputSchema={"type": "object"})]


@server.call_tool()
async def dispatch(name: str, arguments: dict) -> list[TextContent]:
    return [TextContent(type="text", text=str(arguments))]


async def discover(session):
    return await session.list_tools()
