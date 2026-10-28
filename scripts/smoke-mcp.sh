#!/usr/bin/env bash
# Assert the MCP server answers initialize and tools/list over stdio.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python - <<'PY'
import json
import subprocess
import sys

proc = subprocess.Popen(
    [sys.executable, "-m", "kavach.experiences.mcp_server"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
)
assert proc.stdin and proc.stdout
proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n")
proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
proc.stdin.close()
lines = [json.loads(line) for line in proc.stdout if line.strip()]
proc.wait(timeout=10)
names = {tool["name"] for tool in lines[1]["result"]["tools"]}
assert "decide" in names and "issue_mandate" in names, names
print("MCP SMOKE PASSED")
print("  tools:", ", ".join(sorted(names)))
PY
