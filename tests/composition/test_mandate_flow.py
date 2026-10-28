"""Mandate issuance, presentation, and revocation through the substrate."""

from __future__ import annotations

from datetime import timedelta

import pytest

from kavach.composition import SubstrateConfig, build_substrate
from kavach.events import utcnow
from kavach.events.schemas import Mandate, MandateConstraint
from kavach.usecases.customer_service import CustomerServiceRules


@pytest.mark.asyncio
async def test_transfer_requires_mandate_and_records_digest() -> None:
    substrate = build_substrate(
        SubstrateConfig(
            database_url="sqlite+aiosqlite:///:memory:",
            audit_hmac_key="unit-test-key",
        ),
        rule_providers=[CustomerServiceRules()],
    )
    await substrate.create_schema()
    mandate = Mandate(
        mandate_id="m-flow",
        originator_id="customer-1",
        originator_kind="human",
        agent_id="agent-1",
        action_scope=["account.funds.transfer"],
        constraints=[MandateConstraint(path="payment_amount.amount", operator="lte", value=500000)],
        expires_at=utcnow() + timedelta(hours=1),
        nonce="n",
    )
    issued = await substrate.service.issue_mandate(tenant_id="t1", mandate=mandate)
    stored = await substrate.service.get_mandate(tenant_id="t1", mandate_id="m-flow")
    assert stored is not None

    denied = await substrate.service.decide(
        tenant_id="t1",
        agent_id="agent-1",
        session_id="s",
        action_type="account.funds.transfer",
        parameters={"amount": 250000},
        use_case="customer_service",
    )
    assert denied.outcome == "deny"

    stepped = await substrate.service.decide(
        tenant_id="t1",
        agent_id="agent-1",
        session_id="s",
        action_type="account.funds.transfer",
        parameters={"amount": 250000},
        use_case="customer_service",
        mandate_token=stored.token,
    )
    assert stepped.outcome == "step_up"
    assert stepped.decision_event.evidence.attributes["mandate_digest"] == issued.mandate_digest

    await substrate.service.revoke_mandate(
        tenant_id="t1", mandate_id="m-flow", revoked_by="op", reason="test"
    )
    after = await substrate.service.decide(
        tenant_id="t1",
        agent_id="agent-1",
        session_id="s",
        action_type="account.funds.transfer",
        parameters={"amount": 250000},
        use_case="customer_service",
        mandate_token=stored.token,
    )
    assert after.outcome == "deny"
    await substrate.dispose()
