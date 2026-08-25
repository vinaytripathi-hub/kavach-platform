"""Tests for the Customer Service policy rule provider."""

from __future__ import annotations

from kavach.capabilities.policy import PolicyEngine
from kavach.usecases.customer_service import CustomerServiceRules, build_rule_set


def _engine() -> PolicyEngine:
    return PolicyEngine(build_rule_set())


def _decide(engine: PolicyEngine, action: str, params: dict[str, object]) -> str:
    return engine.evaluate(
        tenant_id="t1",
        agent_id="a1",
        session_id="s1",
        action_type=action,
        parameters=params,
    ).outcome


def test_provider_use_case_name() -> None:
    assert CustomerServiceRules().use_case == "customer_service"
    assert CustomerServiceRules().rule_set().use_case == "customer_service"


def test_kyc_allowed() -> None:
    assert _decide(_engine(), "kyc.document.verify", {}) == "allow"


def test_complaint_allowed() -> None:
    assert _decide(_engine(), "complaint.ticket.create", {}) == "allow"


def test_high_value_transfer_steps_up() -> None:
    assert _decide(_engine(), "account.funds.transfer", {"amount": 250000}) == "step_up"


def test_low_value_transfer_allowed() -> None:
    assert _decide(_engine(), "account.funds.transfer", {"amount": 500}) == "allow"


def test_unknown_action_denied_by_default() -> None:
    assert _decide(_engine(), "trading.order.place", {}) == "deny"
