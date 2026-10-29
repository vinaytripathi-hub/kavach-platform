"""Tests for the policy engine: matching, conditions, effects, defaults."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from kavach.capabilities.mandate.contracts import VerifiedMandate
from kavach.capabilities.policy import (
    PolicyCondition,
    PolicyEngine,
    PolicyRule,
    PolicyRuleSet,
)
from kavach.events.schemas.mandate import Mandate, MandateConstraint


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


# ---------------------------------------------------------------------------
# Mandate-aware evaluation (the authorization core).
# ---------------------------------------------------------------------------


def _verified(
    constraints: list[MandateConstraint],
    *,
    originator_kind: str = "human",
    verified: bool = True,
) -> VerifiedMandate:
    now = datetime.now(UTC)
    mandate = Mandate(
        mandate_id="m-1",
        originator_id="cust-1",
        originator_kind=originator_kind,  # type: ignore[arg-type]
        agent_id="agent-1",
        action_scope=["account.funds.transfer"],
        constraints=constraints,
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        nonce="n1",
    )
    return VerifiedMandate(mandate=mandate, verified=verified, digest="d" * 8)


def _eval_with_mandate(
    engine: PolicyEngine,
    action: str,
    params: dict[str, object],
    mandate: VerifiedMandate | None,
) -> object:
    return engine.evaluate(
        tenant_id="t1",
        agent_id="agent-1",
        session_id="s1",
        action_type=action,
        parameters=params,
        verified_mandate=mandate,
    )


def _mandate_required_engine(*, originator_kinds: list[str] | None = None) -> PolicyEngine:
    rule = PolicyRule(
        rule_id="allow-with-mandate",
        action_type="account.funds.transfer",
        effect="allow",
        priority=10,
        mandate_required=True,
        mandate_originator_kinds=originator_kinds,
    )
    return PolicyEngine(PolicyRuleSet(use_case="u", rules=[rule], default_effect="deny"))


def test_mandate_required_but_none_presented_denies() -> None:
    d = _eval_with_mandate(_mandate_required_engine(), "account.funds.transfer", {}, None)
    assert d.outcome == "deny"  # type: ignore[attr-defined]
    assert d.decision_event.decided_by == "policy:mandate"  # type: ignore[attr-defined]
    assert "verified mandate" in d.decision_event.reasoning.decision_path  # type: ignore[attr-defined]


def test_mandate_required_unverified_denies() -> None:
    mandate = _verified([], verified=False)
    d = _eval_with_mandate(_mandate_required_engine(), "account.funds.transfer", {}, mandate)
    assert d.outcome == "deny"  # type: ignore[attr-defined]


def test_mandate_originator_kind_mismatch_denies() -> None:
    engine = _mandate_required_engine(originator_kinds=["human"])
    mandate = _verified([], originator_kind="service")
    d = _eval_with_mandate(engine, "account.funds.transfer", {}, mandate)
    assert d.outcome == "deny"  # type: ignore[attr-defined]
    assert "originator kind" in d.decision_event.reasoning.decision_path  # type: ignore[attr-defined]


def test_mandate_constraint_satisfied_allows() -> None:
    engine = _mandate_required_engine(originator_kinds=["human"])
    mandate = _verified(
        [MandateConstraint(path="payment_amount.amount", operator="lte", value=50000)]
    )
    d = _eval_with_mandate(engine, "account.funds.transfer", {"amount": 40000}, mandate)
    assert d.outcome == "allow"  # type: ignore[attr-defined]
    # Mandate evidence is embedded.
    assert d.decision_event.evidence.attributes["mandate_originator_kind"] == "human"  # type: ignore[attr-defined]


def test_mandate_constraint_violation_denies() -> None:
    engine = _mandate_required_engine()
    mandate = _verified(
        [MandateConstraint(path="payment_amount.amount", operator="lte", value=50000)]
    )
    d = _eval_with_mandate(engine, "account.funds.transfer", {"amount": 60000}, mandate)
    assert d.outcome == "deny"  # type: ignore[attr-defined]
    assert "constraints" in d.decision_event.reasoning.decision_path  # type: ignore[attr-defined]


def test_mandate_payee_fallback_path() -> None:
    engine = _mandate_required_engine()
    mandate = _verified([MandateConstraint(path="payee.id", operator="eq", value="m-ok")])
    ok = _eval_with_mandate(engine, "account.funds.transfer", {"to": "m-ok"}, mandate)
    assert ok.outcome == "allow"  # type: ignore[attr-defined]
    bad = _eval_with_mandate(engine, "account.funds.transfer", {"to": "m-evil"}, mandate)
    assert bad.outcome == "deny"  # type: ignore[attr-defined]


def test_mandate_matches_operator_is_unsupported_and_denies() -> None:
    # "matches" has no comparator in _constraint_ok -> constraint never holds.
    engine = _mandate_required_engine()
    mandate = _verified([MandateConstraint(path="amount", operator="matches", value="5.*")])
    d = _eval_with_mandate(engine, "account.funds.transfer", {"amount": 500}, mandate)
    assert d.outcome == "deny"  # type: ignore[attr-defined]


def test_mandate_constraint_type_mismatch_denies() -> None:
    # Comparing a string actual against an int bound raises TypeError -> False.
    engine = _mandate_required_engine()
    mandate = _verified(
        [MandateConstraint(path="payment_amount.amount", operator="lte", value=50000)]
    )
    d = _eval_with_mandate(engine, "account.funds.transfer", {"amount": "not-a-number"}, mandate)
    assert d.outcome == "deny"  # type: ignore[attr-defined]


def test_mandate_covers_action_condition() -> None:
    rule = PolicyRule(
        rule_id="covered",
        action_type="account.funds.transfer",
        effect="allow",
        priority=10,
        conditions=[
            PolicyCondition(attribute="mandate", operator="mandate_covers_action", value=None)
        ],
    )
    engine = PolicyEngine(PolicyRuleSet(use_case="u", rules=[rule], default_effect="deny"))
    mandate = _verified([])
    covered = _eval_with_mandate(engine, "account.funds.transfer", {}, mandate)
    assert covered.outcome == "allow"  # type: ignore[attr-defined]
    # Without a verified mandate the condition fails and the default applies.
    uncovered = _eval_with_mandate(engine, "account.funds.transfer", {}, None)
    assert uncovered.outcome == "deny"  # type: ignore[attr-defined]


def test_in_and_contains_operators() -> None:
    in_rule = PolicyRule(
        rule_id="in-rule",
        action_type="x",
        effect="allow",
        conditions=[
            PolicyCondition(attribute="parameters.region", operator="in", value=["IN", "SG"])
        ],
    )
    engine = PolicyEngine(PolicyRuleSet(use_case="u", rules=[in_rule], default_effect="deny"))
    assert _evaluate(engine, "x", {"region": "IN"}).outcome == "allow"  # type: ignore[attr-defined]
    assert _evaluate(engine, "x", {"region": "US"}).outcome == "deny"  # type: ignore[attr-defined]


def test_contains_operator() -> None:
    rule = PolicyRule(
        rule_id="contains-rule",
        action_type="x",
        effect="allow",
        conditions=[
            PolicyCondition(attribute="parameters.scopes", operator="contains", value="funds")
        ],
    )
    engine = PolicyEngine(PolicyRuleSet(use_case="u", rules=[rule], default_effect="deny"))
    assert _evaluate(engine, "x", {"scopes": ["kyc", "funds"]}).outcome == "allow"  # type: ignore[attr-defined]
    assert _evaluate(engine, "x", {"scopes": ["kyc"]}).outcome == "deny"  # type: ignore[attr-defined]
    # Non-iterable actual is handled (TypeError -> False), not a crash.
    assert _evaluate(engine, "x", {"scopes": 5}).outcome == "deny"  # type: ignore[attr-defined]
