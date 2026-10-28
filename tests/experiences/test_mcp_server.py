"""MCP tool catalogue, without a live API."""

from __future__ import annotations

from kavach.experiences.mcp_server.server import handle


def test_initialize_and_tools() -> None:
    init = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init is not None
    assert init["result"]["serverInfo"]["name"] == "kavach"
    listed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert listed is not None
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert {"decide", "issue_mandate", "get_trust"} <= names
