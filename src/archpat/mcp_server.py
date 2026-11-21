"""Optional MCP stdio facade using the same pure application operations."""
from __future__ import annotations
from .operations import synthesize_operation, validate_operation, diff_operation, impact_operation


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ImportError as exc:
        raise RuntimeError('Install archpat[mcp] to use the MCP facade') from exc
    server = FastMCP("ArchPat", instructions="Propose and inspect architecture graphs. No project code is executed or changed.")
    readonly = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    server.tool(name="architecture_synthesize", annotations=readonly)(synthesize_operation)
    server.tool(name="architecture_validate", annotations=readonly)(validate_operation)
    server.tool(name="architecture_diff", annotations=readonly)(diff_operation)
    server.tool(name="architecture_impact", annotations=readonly)(impact_operation)
    return server

