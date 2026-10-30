#!/usr/bin/env bash
# Cross-language SDK smoke test (Phase 1.5 gate).
#
# Boots a local Kavach API (fake verifier, file-backed SQLite), builds and links
# the @aurvia/kavach TypeScript SDK, then runs the Node reference agent through
# the full issue -> decide -> step-up -> export flow against the live API.
#
# Usage:  ./scripts/smoke-sdk-node.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PORT="${KAVACH_SMOKE_PORT:-8077}"
DBFILE="$(mktemp -t kavach-sdk-smoke.XXXXXX).sqlite"
PYTHON="${PYTHON:-.venv/bin/python}"

# Mint an operator access token and publish the matching JWKS so the API
# process (a separate interpreter) can verify it. ADR-0021.
eval "$("$PYTHON" - <<'PY'
import shlex
from kavach.testing.oidc import AUDIENCE, ISSUER, jwks_json, mint_operator_token

token = mint_operator_token(role="admin", tenant="bank-1")
print(f"export KAVACH_OIDC_ISSUER={shlex.quote(ISSUER)}")
print(f"export KAVACH_OIDC_AUDIENCE={shlex.quote(AUDIENCE)}")
print(f"export KAVACH_OIDC_JWKS={shlex.quote(jwks_json())}")
print(f"export OPERATOR_TOKEN={shlex.quote(token)}")
PY
)"

export KAVACH_DATABASE_URL="sqlite+aiosqlite:///${DBFILE}"
export KAVACH_OPERATOR_TOKEN="$OPERATOR_TOKEN"
export KAVACH_MANDATE_VERIFIER_MODE="fake"
export KAVACH_AUDIT_HMAC_KEY="smoke-test-hmac-key"

cleanup() {
  [[ -n "${SERVER_PID:-}" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -f "$DBFILE"
}
trap cleanup EXIT

echo "==> Creating schema on ${DBFILE}"
"$PYTHON" - <<'PY'
import asyncio
from kavach.composition import SubstrateConfig, build_substrate
from kavach.usecases.customer_service import CustomerServiceRules

substrate = build_substrate(SubstrateConfig(), rule_providers=[CustomerServiceRules()])
asyncio.run(substrate.create_schema())
print("    schema ready")
PY

echo "==> Starting API on :${PORT}"
"$PYTHON" -m uvicorn kavach.server:app --host 127.0.0.1 --port "$PORT" --log-level warning &
SERVER_PID=$!

echo "==> Waiting for health"
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${PORT}/v1/health" >/dev/null 2>&1; then
    echo "    healthy"
    break
  fi
  sleep 0.5
done

echo "==> Building + linking @aurvia/kavach"
(cd sdks/typescript && npm install --silent && npm run build --silent)

echo "==> Installing example deps"
(cd examples/node/minimal-agent && npm install --silent)

echo "==> Running the Node reference agent"
KAVACH_BASE_URL="http://127.0.0.1:${PORT}" \
  KAVACH_OPERATOR_TOKEN="$OPERATOR_TOKEN" \
  node examples/node/minimal-agent/index.mjs

echo
echo "SDK NODE SMOKE TEST PASSED"
