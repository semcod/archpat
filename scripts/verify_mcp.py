"""Exercise the installed ArchPat server through real MCP stdio messages."""
import asyncio
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

root = Path(__file__).resolve().parents[1]


async def main():
    story = json.loads((root / "examples/story-local.json").read_text())
    params = StdioServerParameters(command=sys.executable, args=["-m", "archpat", "mcp"])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            init = await session.initialize()
            listed = await session.list_tools()
            names = sorted(tool.name for tool in listed.tools)
            expected = sorted(["architecture_synthesize", "architecture_validate", "architecture_diff", "architecture_impact"])
            assert names == expected, names
            plan = await session.call_tool("architecture_synthesize", {"story": story})
            assert not plan.isError, plan
            value = plan.structuredContent
            if value is None:
                value = json.loads(plan.content[0].text)
            assert value["selected_id"] == "modular_monolith", value
            graph = next(candidate["graph"] for candidate in value["candidates"] if candidate["id"] == value["selected_id"])
            checked = await session.call_tool("architecture_validate", {"graph": graph})
            assert not checked.isError, checked
            report = checked.structuredContent or json.loads(checked.content[0].text)
            assert report["valid"] is True and report["execution_ready"] is False
            result = {"transport": "stdio", "protocol_version": init.protocolVersion,
                      "tools": names, "initialize": "passed", "synthesize": "passed", "validate": "passed",
                      "upstream_integrations_tested": False}
            (root / "evidence/mcp.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=30))
