"""Tests for the policy engine: matching, conditions, effects, defaults."""

from __future__ import annotations

import pytest

from kavach.capabilities.policy import (
    PolicyCondition,
    PolicyEngine,
    PolicyRule,
    PolicyRuleSet,
)


def _engine(default: str = "deny") -> PolicyEngine:
    rules = [
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
            conditions=[PolicyCondition(attribute="parameters.amount", operator="gt", value=50000)],
            step_up_role="senior_ops",
            priority=10,
        ),
        PolicyRule(
            rule_id="allow-low-value",
            action_type="account.funds.transfer",
            effect="allow",
            priority=20,
        ),
    ]
    return PolicyEngine(
        PolicyRuleSet(use_case="customer_service", rules=rules, default_effect=default)  # type: ignore[arg-type]
    )


def _evaluate(engine: PolicyEngine, action: str, params: dict[str, object]) -> object:
    return engine.evaluate(
        tenant_id="t1",
        agent_id="agent-1",
        session_id="s1",
        action_type=action,
        parameters=params,
    )


def test_glob_match_allow() -> None:
    d = _evaluate(_engine(), "kyc.document.verify", {})
    assert d.outcome == "allow"  # type: ignore[attr-defined]
    assert d.matched_rule_id == "allow-kyc"  # type: ignore[attr-defined]


def test_condition_triggers_step_up() -> None:
    d = _evaluate(_engine(), "account.funds.transfer", {"amount": 100000})
    assert d.outcome == "step_up"  # type: ignore[attr-defined]
    assert d.step_up_event is not None  # type: ignore[attr-defined]
    assert d.step_up_event.required_role == "senior_ops"  # type: ignore[attr-defined]


def test_priority_falls_through_to_low_value_allow() -> None:
    d = _evaluate(_engine(), "account.funds.transfer", {"amount": 100})
    assert d.outcome == "allow"  # type: ignore[attr-defined]
    assert d.matched_rule_id == "allow-low-value"  # type: ignore[attr-defined]


def test_default_effect_when_no_match() -> None:
    d = _evaluate(_engine(default="deny"), "unknown.action", {})
    assert d.outcome == "deny"  # type: ignore[attr-defined]
    assert d.matched_rule_id is None  # type: ignore[attr-defined]
    assert d.decision_event.decided_by == "policy:default"  # type: ignore[attr-defined]


def test_decision_carries_mandatory_embedded_fields() -> None:
    d = _evaluate(_engine(), "kyc.document.verify", {})
    ev = d.decision_event  # type: ignore[attr-defined]
    assert ev.evidence is not None
    assert ev.reasoning.decision_path
    assert ev.confidence.kind == "rule_deterministic"
    assert ev.decided_by


@pytest.mark.parametrize(
    "operator,value,amount,expected",
    [
        ("gt", 50000, 60000, True),
        ("gt", 50000, 40000, False),
        ("gte", 50000, 50000, True),
        ("lt", 50000, 40000, True),
        ("eq", 50000, 50000, True),
        ("ne", 50000, 40000, True),
    ],
)
def test_numeric_operators(operator: str, value: int, amount: int, expected: bool) -> None:
    rule = PolicyRule(
        rule_id="r",
        action_type="x",
        effect="step_up",
        conditions=[PolicyCondition(attribute="parameters.amount", operator=operator, value=value)],  # type: ignore[arg-type]
    )
    engine = PolicyEngine(PolicyRuleSet(use_case="u", rules=[rule], default_effect="allow"))
    d = _evaluate(engine, "x", {"amount": amount})
    assert (d.outcome == "step_up") is expected  # type: ignore[attr-defined]
