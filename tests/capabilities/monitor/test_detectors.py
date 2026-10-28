"""Detector unit tests (ADR-0019)."""

from __future__ import annotations

from kavach.capabilities.monitor import RateDetector, ScopeExpansionDetector
from kavach.events.schemas import DecisionEmitted, Evidence, ReasoningTrace, rule_deterministic


def _decision(action: str, outcome: str = "allow") -> DecisionEmitted:
    return DecisionEmitted(
        tenant_id="t1",
        agent_id="a",
        session_id="s",
        decision_id=action,
        action_type=action,
        outcome=outcome,  # type: ignore[arg-type]
        evidence=Evidence(),
        reasoning=ReasoningTrace(kind="rule", decision_path="p"),
        confidence=rule_deterministic(),
        decided_by="rule:r",
    )


def test_rate_suppresses_thin_history() -> None:
    event = _decision("kyc.x")
    assert RateDetector().observe(event, [event]) == []


def test_rate_warns_after_threshold() -> None:
    events = [_decision(f"kyc.{i}") for i in range(3)]
    found = RateDetector(min_history=3, warn_at=3, critical_at=5).observe(events[-1], events)
    assert found and found[0].severity == "warn"


def test_scope_expansion() -> None:
    first = _decision("kyc.document.verify")
    second = _decision("account.funds.transfer")
    found = ScopeExpansionDetector().observe(second, [first, second])
    assert found and found[0].detector_id == "scope_expansion"
