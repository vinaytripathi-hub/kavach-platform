"""Policy evaluation engine (ADR-0012; EU AI Act Art. 14).

Evaluates a proposed action against a rule set and produces decision-grade
events: a ``PolicyEvaluated`` record, a ``DecisionEmitted`` carrying the
four mandatory embedded fields, and (when the outcome is ``step_up``) a
``StepUpRequested`` to escalate to a human.
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from pydantic import BaseModel, ConfigDict

from kavach.capabilities.policy._internal.rules import (
    PolicyCondition,
    PolicyRule,
    PolicyRuleSet,
)
from kavach.events import new_event_id
from kavach.events.decision_helpers import make_evidence, rule_reasoning
from kavach.events.schemas import (
    Confidence,
    DecisionEmitted,
    Outcome,
    PolicyEvaluated,
    ReasoningTrace,
    StepUpRequested,
    rule_deterministic,
)


class PolicyDecision(BaseModel):
    """The full outcome of evaluating one proposed action."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    outcome: Outcome
    decision_id: str
    matched_rule_id: str | None
    decision_event: DecisionEmitted
    policy_evaluated_event: PolicyEvaluated
    step_up_event: StepUpRequested | None = None


def _resolve(attribute: str, ctx: dict[str, Any]) -> Any:  # noqa: ANN401
    """Resolve a dotted attribute path against the evaluation context."""
    cur: Any = ctx
    for part in attribute.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _check(cond: PolicyCondition, ctx: dict[str, Any]) -> bool:  # noqa: PLR0911
    actual = _resolve(cond.attribute, ctx)
    expected = cond.value
    op = cond.operator
    if op == "eq":
        return bool(actual == expected)
    if op == "ne":
        return bool(actual != expected)
    if actual is None:
        return False
    try:
        if op == "gt":
            return bool(actual > expected)
        if op == "gte":
            return bool(actual >= expected)
        if op == "lt":
            return bool(actual < expected)
        if op == "lte":
            return bool(actual <= expected)
    except TypeError:
        return False
    if op == "in":
        return actual in expected if expected is not None else False
    # op == "contains" (all other operators handled above)
    try:
        return expected in actual
    except TypeError:
        return False


class PolicyEngine:
    """Evaluates proposed actions against a rule set."""

    def __init__(self, rule_set: PolicyRuleSet) -> None:
        self._rule_set = rule_set

    @property
    def rule_set(self) -> PolicyRuleSet:
        return self._rule_set

    def _match(self, action_type: str, ctx: dict[str, Any]) -> PolicyRule | None:
        candidates = [r for r in self._rule_set.rules if fnmatch(action_type, r.action_type)]
        candidates.sort(key=lambda r: r.priority)
        for rule in candidates:
            if all(_check(c, ctx) for c in rule.conditions):
                return rule
        return None

    def evaluate(
        self,
        *,
        tenant_id: str,
        agent_id: str,
        session_id: str,
        action_type: str,
        parameters: dict[str, Any],
        context: str | None = None,
    ) -> PolicyDecision:
        decision_id = new_event_id()
        ctx: dict[str, Any] = {
            "parameters": parameters,
            "action_type": action_type,
            "agent_id": agent_id,
            "context": context,
        }
        rule = self._match(action_type, ctx)

        if rule is None:
            outcome: Outcome = self._rule_set.default_effect
            matched_rule_id: str | None = None
            decided_by = "policy:default"
            reasoning: ReasoningTrace = ReasoningTrace(
                kind="rule",
                rule_id=None,
                decision_path=(
                    f"No rule matched action '{action_type}'; applied default effect '{outcome}'."
                ),
            )
            step_up_role = self._rule_set.default_step_up_role
        else:
            outcome = rule.effect
            matched_rule_id = rule.rule_id
            decided_by = f"rule:{rule.rule_id}"
            reasoning = rule_reasoning(
                rule.rule_id,
                f"Rule '{rule.rule_id}' matched '{action_type}' with effect '{rule.effect}'.",
            )
            step_up_role = rule.step_up_role or self._rule_set.default_step_up_role

        confidence: Confidence = rule_deterministic()
        evidence = make_evidence(
            attributes={
                "action_type": action_type,
                "parameters": parameters,
                "context": context,
                "matched_rule_id": matched_rule_id,
            }
        )

        step_up_reason: str | None = None
        step_up_event: StepUpRequested | None = None
        if outcome == "step_up":
            step_up_reason = (
                f"Action '{action_type}' requires human approval by role '{step_up_role}'."
            )
            step_up_event = StepUpRequested(
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                decision_id=decision_id,
                action_type=action_type,
                reason=step_up_reason,
                required_role=step_up_role,
            )

        decision_event = DecisionEmitted(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            decision_id=decision_id,
            action_type=action_type,
            parameters=parameters,
            outcome=outcome,
            evidence=evidence,
            reasoning=reasoning,
            confidence=confidence,
            decided_by=decided_by,
            step_up_reason=step_up_reason,
            step_up_role=step_up_role if outcome == "step_up" else None,
        )
        policy_evaluated = PolicyEvaluated(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            decision_id=decision_id,
            action_type=action_type,
            matched_rule_id=matched_rule_id,
            outcome=outcome,
        )
        return PolicyDecision(
            outcome=outcome,
            decision_id=decision_id,
            matched_rule_id=matched_rule_id,
            decision_event=decision_event,
            policy_evaluated_event=policy_evaluated,
            step_up_event=step_up_event,
        )
