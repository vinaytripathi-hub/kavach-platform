"""End-to-end substrate integration: decide, step-up, trust, audit export."""

from __future__ import annotations

from datetime import timedelta

import pytest

from kavach.capabilities.policy import PolicyCondition, PolicyRule, PolicyRuleSet
from kavach.composition import Substrate, SubstrateConfig, build_substrate


class _CustomerServiceRules:
    """Inline rule provider for the test (a use case implements this)."""

    use_case = "customer_service"

    def rule_set(self) -> PolicyRuleSet:
        return PolicyRuleSet(
            use_case="customer_service",
            version="test-1",
            default_effect="deny",
            default_step_up_role="supervisor",
            rules=[
                PolicyRule(
                    rule_id="allow-kyc",
                    action_type="kyc.*",
                    effect="allow",
                    priority=10,
                ),
                PolicyRule(
                    rule_id="stepup-high-value",
                    action_type="account.funds.transfer",
                    effect="step_up",
                    conditions=[
                        PolicyCondition(attribute="parameters.amount", operator="gt", value=50000)
                    ],
                    step_up_role="senior_ops",
                    priority=10,
                ),
            ],
        )


@pytest.fixture
async def substrate() -> Substrate:
    sub = build_substrate(
        SubstrateConfig(database_url="sqlite+aiosqlite://"),
        rule_providers=[_CustomerServiceRules()],
    )
    await sub.create_schema()
    return sub


async def test_full_customer_service_flow(substrate: Substrate) -> None:
    svc = substrate.service
    tenant, agent = "bank-1", "agent-1"

    # 1. Verify the agent and assess initial (cold-start) trust.
    verified = substrate.verifier.verify(
        "agent:agent-1:kyc,account.funds", expected_audience="kavach"
    )
    assert verified.verified
    await svc.assess_trust(
        tenant_id=tenant, agent_id=agent, context="customer_service", agent=verified
    )

    # 2. Record a benign KYC action.
    await svc.record_action(
        tenant_id=tenant,
        agent_id=agent,
        session_id="s1",
        action_type="kyc.document.verify",
        parameters={"doc": "passport"},
    )

    # 3. A high-value transfer triggers a step-up.
    decision = await svc.decide(
        use_case="customer_service",
        tenant_id=tenant,
        agent_id=agent,
        session_id="s1",
        action_type="account.funds.transfer",
        parameters={"amount": 100000},
    )
    assert decision.outcome == "step_up"

    # 4. Operator approves the step-up.
    resolved = await svc.resolve_step_up(
        tenant_id=tenant,
        decision_id=decision.decision_id,
        resolution="approve",
        operator_id="op-1",
        rationale="Customer verified by phone.",
    )
    assert resolved.final_outcome == "allow"

    # 5. Projections reflect the activity.
    timeline = await svc.get_timeline(tenant_id=tenant, agent_id=agent)
    assert len(timeline) >= 4
    trust = await svc.get_trust(tenant_id=tenant, agent_id=agent, context="customer_service")
    assert trust is not None
    assert "credential_integrity" in trust.dimensions

    pending = await svc.pending_step_ups(tenant_id=tenant)
    assert pending == []  # the step-up was resolved

    # 6. Export a signed evidence pack and verify it cryptographically.
    export = await svc.export_audit(
        tenant_id=tenant,
        agent_id=agent,
        frm=svc.now - timedelta(hours=1),
        to=svc.now + timedelta(hours=1),
    )
    assert export.record_count >= 4
    assert export.signature_manifest is not None
    assert svc.verify_export(export) is True

    await substrate.dispose()


async def test_tampered_export_fails_verification(substrate: Substrate) -> None:
    svc = substrate.service
    await svc.record_action(
        tenant_id="bank-1",
        agent_id="agent-1",
        session_id="s1",
        action_type="kyc.document.verify",
        parameters={"doc": "passport"},
    )
    export = await svc.export_audit(
        tenant_id="bank-1",
        agent_id="agent-1",
        frm=svc.now - timedelta(hours=1),
        to=svc.now + timedelta(hours=1),
    )
    assert svc.verify_export(export) is True

    # Tamper with a record's payload digest; verification must fail.
    export.records[0].payload_digest = "0" * 64
    assert svc.verify_export(export) is False

    await substrate.dispose()


async def test_default_deny_for_unknown_action(substrate: Substrate) -> None:
    decision = await substrate.service.decide(
        use_case="customer_service",
        tenant_id="bank-1",
        agent_id="agent-1",
        session_id="s1",
        action_type="trading.order.place",
        parameters={},
    )
    assert decision.outcome == "deny"
    assert decision.matched_rule_id is None
    await substrate.dispose()
