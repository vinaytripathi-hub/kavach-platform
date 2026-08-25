"""Policy and decision events (ADR-0012).

``PolicyEvaluated`` is a lightweight record that a rule set was run.
``DecisionEmitted`` is the decision-grade event carrying the four
mandatory embedded fields (evidence, reasoning, confidence, decided_by).
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field

from kavach.events._base import DomainEvent
from kavach.events.schemas.data_sufficiency import DataSufficiency
from kavach.events.schemas.decision_primitives import (
    Confidence,
    Evidence,
    ReasoningTrace,
)

Outcome = Literal["allow", "deny", "step_up"]


class PolicyEvaluated(DomainEvent):
    """Emitted when a policy rule set is evaluated for a proposed action."""

    event_type: ClassVar[str] = "PolicyEvaluated"
    schema_version: ClassVar[int] = 1

    agent_id: str
    session_id: str
    decision_id: str
    action_type: str
    matched_rule_id: str | None
    outcome: Outcome


class DecisionEmitted(DomainEvent):
    """A decision-grade event with embedded evidence, reasoning, confidence.

    Carries everything an auditor needs to understand why a decision was
    made: the inputs (evidence), how it was derived (reasoning), how
    certain it is (confidence), what produced it (decided_by), and how
    much data underlay it (data_sufficiency).
    """

    event_type: ClassVar[str] = "DecisionEmitted"
    schema_version: ClassVar[int] = 1

    agent_id: str
    session_id: str
    decision_id: str
    action_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    outcome: Outcome
    evidence: Evidence
    reasoning: ReasoningTrace
    confidence: Confidence
    decided_by: str
    data_sufficiency: DataSufficiency | None = None
    step_up_reason: str | None = None
    step_up_role: str | None = None


__all__ = ["DecisionEmitted", "Outcome", "PolicyEvaluated"]
