"""A tool server: one tool declared, and a call to a tool that declares nothing."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fixture")


@mcp.tool()
def lookup(name: str) -> str:
    return name.upper()


async def relay(session, name):
    return await session.call_tool("lookup", {"name": name})
