"""Tests for the Customer Service policy rule provider."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from kavach.capabilities.mandate.contracts import VerifiedMandate
from kavach.capabilities.policy import PolicyEngine
from kavach.events.schemas import Mandate, MandateConstraint
from kavach.usecases.customer_service import CustomerServiceRules, build_rule_set


def _engine() -> PolicyEngine:
    return PolicyEngine(build_rule_set())


def _mandate(max_amount: int = 500000) -> VerifiedMandate:
    mandate = Mandate(
        mandate_id="m1",
        originator_id="user-1",
        originator_kind="human",
        agent_id="a1",
        action_scope=["account.funds.transfer"],
        constraints=[
            MandateConstraint(path="payment_amount.amount", operator="lte", value=max_amount)
        ],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        nonce="n1",
    )
    return VerifiedMandate(mandate=mandate, verified=True, digest="abc", reason="ok")


def _decide(
    engine: PolicyEngine,
    action: str,
    params: dict[str, object],
    mandate: VerifiedMandate | None = None,
) -> str:
    return engine.evaluate(
        tenant_id="t1",
        agent_id="a1",
        session_id="s1",
        action_type=action,
        parameters=params,
        verified_mandate=mandate,
    ).outcome


def test_provider_use_case_name() -> None:
    assert CustomerServiceRules().use_case == "customer_service"
    assert CustomerServiceRules().rule_set().use_case == "customer_service"


def test_kyc_allowed() -> None:
    assert _decide(_engine(), "kyc.document.verify", {}) == "allow"


def test_complaint_allowed() -> None:
    assert _decide(_engine(), "complaint.ticket.create", {}) == "allow"


def test_high_value_transfer_steps_up() -> None:
    assert _decide(_engine(), "account.funds.transfer", {"amount": 250000}, _mandate()) == "step_up"


def test_low_value_transfer_allowed() -> None:
    assert _decide(_engine(), "account.funds.transfer", {"amount": 500}, _mandate()) == "allow"


def test_transfer_without_mandate_denied() -> None:
    assert _decide(_engine(), "account.funds.transfer", {"amount": 500}) == "deny"


def test_transfer_over_mandate_denied() -> None:
    outcome = _decide(_engine(), "account.funds.transfer", {"amount": 900000}, _mandate(1000))
    assert outcome == "deny"


def test_unknown_action_denied_by_default() -> None:
    assert _decide(_engine(), "trading.order.place", {}) == "deny"
