"""Synthetic Customer Service agent harness.

Drives the live API through a representative end-to-end flow: register an
agent, perform a benign KYC action, attempt a high-value transfer that
triggers a human step-up, have an operator resolve it, then export a
signed evidence pack. Used by the demo and the on-prem smoke test
(``scripts/smoke-onprem.sh``).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from kavach.client import KavachClient
from kavach.events import utcnow


def run_demo_flow(
    base_url: str,
    *,
    agent_id: str = "agent-cs-01",
    agent_token: str | None = None,
    operator_token: str = "operator-dev-token",  # noqa: S107
    tenant: str = "bank-1",
) -> dict[str, Any]:
    """Run the full demo flow and return a summary of what happened."""
    agent_token = agent_token or f"agent:{agent_id}:kyc,account.funds,complaint"
    summary: dict[str, Any] = {"steps": []}

    agent = KavachClient(base_url, token=agent_token, tenant=tenant)
    operator = KavachClient(base_url, token=operator_token, tenant=tenant, operator="op-demo")

    try:
        # 0. Health.
        summary["health"] = agent.health()

        # 1. Register the agent (operator/admin).
        operator.register_agent(
            agent_id=agent_id,
            display_name="Synthetic CS Agent",
            use_case="customer_service",
        )
        summary["steps"].append("registered agent")

        # 2. Benign KYC action.
        agent.record_action(
            agent_id,
            session_id="sess-1",
            action_type="kyc.document.verify",
            parameters={"document": "passport"},
        )
        summary["steps"].append("recorded kyc action")

        # 3. KYC decision -> allow.
        allow = agent.request_decision(
            agent_id,
            session_id="sess-1",
            action_type="kyc.document.verify",
            parameters={"document": "passport"},
        )
        summary["kyc_outcome"] = allow["outcome"]

        # 4. Originator issues a mandate that covers the transfer amount.
        issued = operator.issue_mandate(
            {
                "mandate_id": "m-demo-1",
                "originator_id": "customer-1",
                "originator_kind": "human",
                "agent_id": agent_id,
                "action_scope": ["account.funds.transfer"],
                "constraints": [
                    {"path": "payment_amount.amount", "operator": "lte", "value": 500000}
                ],
                "expires_at": (utcnow() + timedelta(hours=1)).isoformat(),
                "nonce": "nonce-demo-1",
            }
        )
        summary["mandate_id"] = issued["mandate_id"]
        summary["mandate_token"] = issued["token"]
        summary["steps"].append("issued mandate")

        # 5. High-value transfer within the mandate -> step_up.
        stepup = agent.request_decision(
            agent_id,
            session_id="sess-1",
            action_type="account.funds.transfer",
            parameters={"amount": 250000, "to": "ACC-999"},
            mandate_token=issued["token"],
        )
        summary["transfer_outcome"] = stepup["outcome"]
        evidence = stepup.get("evidence") or {}
        attributes = evidence.get("attributes") or {}
        summary["mandate_digest"] = attributes.get("mandate_digest")
        decision_id = stepup["decision_id"]

        # 6. Operator approves the step-up.
        resolved = operator.resolve_step_up(
            decision_id,
            resolution="approve",
            operator_id="op-demo",
            rationale="Customer identity confirmed by callback.",
        )
        summary["resolved_outcome"] = resolved["outcome"]

        # 6. Trust + timeline.
        summary["trust"] = operator.get_trust(agent_id)
        summary["timeline_len"] = len(operator.get_timeline(agent_id)["items"])

        # 7. Signed evidence export.
        export = operator.request_audit_export(
            agent_id=agent_id,
            frm=utcnow() - timedelta(hours=1),
            to=utcnow() + timedelta(hours=1),
        )
        summary["audit_record_count"] = export["record_count"]
        summary["audit_signed"] = export.get("signature_manifest") is not None
    finally:
        agent.close()
        operator.close()

    return summary
