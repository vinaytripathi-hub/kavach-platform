#!/usr/bin/env bash
# Post-install end-to-end smoke test for an on-prem Kavach deployment
# (ADR-0017). Drives the synthetic Customer Service agent flow against a
# running API: register -> KYC -> high-value transfer step-up -> operator
# resolve -> signed evidence export, then asserts the export verifies.
#
# Usage:
#   KAVACH_API_URL=http://localhost:8000 \
#   KAVACH_OPERATOR_TOKEN=... \
#   ./scripts/smoke-onprem.sh
set -euo pipefail

API_URL="${KAVACH_API_URL:-http://localhost:8000}"
OPERATOR_TOKEN="${KAVACH_OPERATOR_TOKEN:-operator-dev-token}"
TENANT="${KAVACH_TENANT:-bank-1}"

echo "Kavach on-prem smoke test"
echo "  API:    ${API_URL}"
echo "  tenant: ${TENANT}"
echo

python - "$API_URL" "$OPERATOR_TOKEN" "$TENANT" <<'PY'
import os
import sys
from kavach.usecases.customer_service.harness import run_demo_flow

base_url, operator_token, tenant = sys.argv[1], sys.argv[2], sys.argv[3]
summary = run_demo_flow(base_url, operator_token=operator_token, tenant=tenant)

assert summary["kyc_outcome"] == "allow", summary
assert summary["transfer_outcome"] == "step_up", summary
assert summary["resolved_outcome"] == "allow", summary
assert summary["audit_record_count"] >= 4, summary
assert summary["audit_signed"] is True, summary
assert summary.get("mandate_digest"), summary
if os.environ.get("KAVACH_MANDATE_VERIFIER_MODE") == "ap2":
    assert "~~" in str(summary.get("mandate_token", "")), "expected an AP2 SD-JWT chain"

print("  KYC decision .............. {}".format(summary["kyc_outcome"]))
print("  High-value transfer ....... {}".format(summary["transfer_outcome"]))
print("  Operator resolution ....... {}".format(summary["resolved_outcome"]))
print("  Timeline entries .......... {}".format(summary["timeline_len"]))
print("  Audit records (signed) .... {}".format(summary["audit_record_count"]))
print()
print("SMOKE TEST PASSED")
PY
