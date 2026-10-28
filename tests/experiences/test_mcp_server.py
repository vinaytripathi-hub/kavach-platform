"""MCP conformance: drive the Kavach server with the official MCP client.

These tests speak the real protocol handshake end to end (initialize,
tools/list, tools/call) against an in-memory transport, with a stubbed
Kavach client so no live API is required.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

pytest.importorskip("mcp")

import anyio
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from kavach.client import KavachClient
from kavach.experiences.mcp_server.server import build_server

_EXPECTED_TOOLS = {
    "decide",
    "verify_mandate",
    "issue_mandate",
    "resolve_step_up",
    "get_trust",
    "get_timeline",
}


class _StubClient:
    """Records calls and returns canned payloads instead of hitting the API."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def request_decision(self, agent_id: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("request_decision", {"agent_id": agent_id, **kwargs}))
        return {"outcome": "allow", "agent_id": agent_id}

    def issue_mandate(self, mandate: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("issue_mandate", mandate))
        return {"mandate_id": mandate["mandate_id"], "token": "tok"}

    def resolve_step_up(self, decision_id: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("resolve_step_up", {"decision_id": decision_id, **kwargs}))
        return {"outcome": "allow"}

    def get_trust(self, agent_id: str) -> dict[str, Any]:
        self.calls.append(("get_trust", {"agent_id": agent_id}))
        return {"agent_id": agent_id, "trust": 0.9}

    def get_timeline(self, agent_id: str) -> dict[str, Any]:
        self.calls.append(("get_timeline", {"agent_id": agent_id}))
        return {"items": []}

    def close(self) -> None:
        self.calls.append(("close", {}))


async def _run_session(stub: _StubClient, body: Any) -> Any:
    """Connect the official client to the Kavach server over memory streams."""
    server = build_server(client_factory=lambda: cast(KavachClient, stub))
    low = server._lowlevel_server  # official low-level server under MCPServer
    init_options = low.create_initialization_options()
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams
        async with anyio.create_task_group() as tg:

            async def _serve() -> None:
                await low.run(server_read, server_write, init_options, raise_exceptions=True)

            tg.start_soon(_serve)
            async with ClientSession(client_read, client_write) as session:
                await session.initialize()
                result = await body(session)
            tg.cancel_scope.cancel()
    return result


@pytest.mark.anyio
async def test_tools_list_exposes_every_protected_operation() -> None:
    stub = _StubClient()

    async def body(session: ClientSession) -> set[str]:
        listed = await session.list_tools()
        return {tool.name for tool in listed.tools}

    names = await _run_session(stub, body)
    assert names >= _EXPECTED_TOOLS


@pytest.mark.anyio
async def test_call_tool_decide_round_trips_through_the_client() -> None:
    stub = _StubClient()

    async def body(session: ClientSession) -> Any:
        return await session.call_tool(
            "decide",
            {
                "agent_id": "agent-cs-01",
                "action_type": "kyc.document.verify",
                "parameters": {"document": "passport"},
            },
        )

    result = await _run_session(stub, body)
    assert result.structured_content is not None
    assert result.structured_content["outcome"] == "allow"
    assert (
        "request_decision",
        {
            "agent_id": "agent-cs-01",
            "session_id": "mcp",
            "action_type": "kyc.document.verify",
            "parameters": {"document": "passport"},
            "use_case": "customer_service",
            "mandate_token": None,
        },
    ) in stub.calls


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
