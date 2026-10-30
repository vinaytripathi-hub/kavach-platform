#!/usr/bin/env bash
# Exercise Kavach as an MCP server using the official MCP client over stdio:
# initialize, tools/list, and tools/call decide against the API in
# KAVACH_API_URL. Requires the [mcp] extra.
#
# Claude Desktop (manual): Settings → Developer → Edit Config, add
#   "kavach": {
#     "command": "python",
#     "args": ["-m", "kavach.experiences.mcp_server", "--transport", "stdio"],
#     "env": {
#       "KAVACH_API_URL": "http://localhost:8000",
#       "KAVACH_TENANT": "bank-1",
#       "KAVACH_AGENT_TOKEN": "agent:agent-cs-01:kyc,account.funds,complaint",
#       "KAVACH_OPERATOR_ID": "op-demo"
#     }
#   }
# then start a chat and ask it to call the decide tool.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python - <<'PY'
import os
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    passthrough = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("KAVACH_") or key in {"PATH", "VIRTUAL_ENV", "HOME"}
    }
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "kavach.experiences.mcp_server", "--transport", "stdio"],
        env=passthrough,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert {"decide", "issue_mandate"} <= names, names
            result = await session.call_tool(
                "decide",
                {
                    "agent_id": "agent-cs-01",
                    "action_type": "kyc.document.verify",
                    "parameters": {"document": "passport"},
                    "use_case": "customer_service",
                },
            )
            decision = result.structured_content
            assert decision is not None and decision["outcome"] == "allow", decision
    print("MCP SMOKE PASSED")
    print("  tools:", ", ".join(sorted(names)))
    print("  decide:", decision["outcome"])


anyio.run(main)
PY
