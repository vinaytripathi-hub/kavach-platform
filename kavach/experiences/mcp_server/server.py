"""Minimal MCP (stdio) server over KavachClient.

Speaks the initialize / tools/list / tools/call subset used by agent
frameworks. Tools: decide, verify_mandate, issue_mandate, resolve_step_up,
get_trust, get_timeline.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from kavach.client import KavachClient

TOOLS: list[dict[str, Any]] = [
    {"name": "decide", "description": "Request a policy decision for an agent action."},
    {"name": "verify_mandate", "description": "Present a mandate by requesting a decision."},
    {"name": "issue_mandate", "description": "Issue a signed mandate (operator)."},
    {"name": "resolve_step_up", "description": "Resolve a pending step-up."},
    {"name": "get_trust", "description": "Read the current trust assessment."},
    {"name": "get_timeline", "description": "Read the agent timeline."},
]


def _client() -> KavachClient:
    return KavachClient(
        os.environ.get("KAVACH_API_URL", "http://localhost:8000"),
        token=os.environ.get("KAVACH_AGENT_TOKEN", "agent:agent-cs-01:kyc,account.funds"),
        tenant=os.environ.get("KAVACH_TENANT", "bank-1"),
        operator=os.environ.get("KAVACH_OPERATOR_TOKEN", "operator-dev-token"),
    )


def _call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    try:
        if name in {"decide", "verify_mandate"}:
            return client.request_decision(
                str(arguments["agent_id"]),
                session_id=str(arguments.get("session_id", "mcp")),
                action_type=str(arguments["action_type"]),
                parameters=arguments.get("parameters") or {},
                use_case=str(arguments.get("use_case", "customer_service")),
                mandate_token=arguments.get("mandate_token"),
            )
        if name == "issue_mandate":
            return client.issue_mandate(arguments)
        if name == "resolve_step_up":
            return client.resolve_step_up(
                str(arguments["decision_id"]),
                resolution=str(arguments["resolution"]),
                operator_id=str(arguments.get("operator_id", "mcp")),
            )
        if name == "get_trust":
            return client.get_trust(str(arguments["agent_id"]))
        if name == "get_timeline":
            return client.get_timeline(str(arguments["agent_id"]))
        return {"error": f"unknown tool {name}"}
    finally:
        client.close()


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        result: dict[str, Any] = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "kavach", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params") or {}
        payload = _call(str(params.get("name", "")), params.get("arguments") or {})
        result = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": "Method not found"},
        }
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def main() -> None:
    for raw in sys.stdin:
        stripped = raw.strip()
        if not stripped:
            continue
        message = json.loads(stripped)
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
