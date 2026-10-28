"""Kavach MCP server built on the official Model Context Protocol SDK.

Exposes every protected substrate operation as an MCP tool over both
transports the plan requires: ``stdio`` for local agents (Claude Desktop,
Cursor) and ``streamable-http`` for networked deployments. Each tool is a
thin wrapper over :class:`kavach.client.KavachClient`; no business logic is
duplicated here.

Run it with::

    python -m kavach.experiences.mcp_server --transport stdio
    python -m kavach.experiences.mcp_server --transport streamable-http --port 8900
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer

from kavach.client import KavachClient

ClientFactory = Callable[[], KavachClient]

DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8900


def _default_client_factory() -> KavachClient:
    return KavachClient(
        os.environ.get("KAVACH_API_URL", "http://localhost:8000"),
        token=os.environ.get("KAVACH_AGENT_TOKEN", "agent:agent-cs-01:kyc,account.funds"),
        tenant=os.environ.get("KAVACH_TENANT", "bank-1"),
        operator=os.environ.get("KAVACH_OPERATOR_TOKEN", "operator-dev-token"),
    )


def build_server(client_factory: ClientFactory | None = None) -> MCPServer:
    """Assemble the Kavach MCP server with its six tools.

    ``client_factory`` is injectable so conformance tests can drive the
    tools without a live API.
    """
    factory: ClientFactory = client_factory or _default_client_factory
    server = MCPServer(name="kavach", version="0.1.0")

    @server.tool(description="Request a policy decision for an agent action.")
    def decide(
        agent_id: str,
        action_type: str,
        parameters: dict[str, Any] | None = None,
        session_id: str = "mcp",
        use_case: str = "customer_service",
        mandate_token: str | None = None,
    ) -> dict[str, Any]:
        client = factory()
        try:
            return client.request_decision(
                agent_id,
                session_id=session_id,
                action_type=action_type,
                parameters=parameters or {},
                use_case=use_case,
                mandate_token=mandate_token,
            )
        finally:
            client.close()

    @server.tool(description="Present a mandate by requesting a decision bound to it.")
    def verify_mandate(
        agent_id: str,
        action_type: str,
        mandate_token: str,
        parameters: dict[str, Any] | None = None,
        session_id: str = "mcp",
        use_case: str = "customer_service",
    ) -> dict[str, Any]:
        client = factory()
        try:
            return client.request_decision(
                agent_id,
                session_id=session_id,
                action_type=action_type,
                parameters=parameters or {},
                use_case=use_case,
                mandate_token=mandate_token,
            )
        finally:
            client.close()

    @server.tool(description="Issue a signed mandate (operator).")
    def issue_mandate(mandate: dict[str, Any]) -> dict[str, Any]:
        client = factory()
        try:
            return client.issue_mandate(mandate)
        finally:
            client.close()

    @server.tool(description="Resolve a pending human step-up (operator).")
    def resolve_step_up(
        decision_id: str,
        resolution: str,
        operator_id: str = "mcp",
    ) -> dict[str, Any]:
        client = factory()
        try:
            return client.resolve_step_up(
                decision_id, resolution=resolution, operator_id=operator_id
            )
        finally:
            client.close()

    @server.tool(description="Read the current trust assessment for an agent.")
    def get_trust(agent_id: str) -> dict[str, Any]:
        client = factory()
        try:
            return client.get_trust(agent_id)
        finally:
            client.close()

    @server.tool(description="Read the audit timeline for an agent.")
    def get_timeline(agent_id: str) -> dict[str, Any]:
        client = factory()
        try:
            return client.get_timeline(agent_id)
        finally:
            client.close()

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kavach-mcp", description="Kavach MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
    )
    parser.add_argument("--host", default=DEFAULT_HTTP_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT)
    args = parser.parse_args(argv)

    server = build_server()
    if args.transport == "streamable-http":
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")
