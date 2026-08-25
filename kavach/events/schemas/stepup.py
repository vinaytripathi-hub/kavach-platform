"""Human-in-the-loop step-up events (EU AI Act Article 14 oversight)."""

from __future__ import annotations

from typing import ClassVar, Literal

from kavach.events._base import DomainEvent


class StepUpRequested(DomainEvent):
    """Emitted when policy escalates a decision to a human."""

    event_type: ClassVar[str] = "StepUpRequested"
    schema_version: ClassVar[int] = 1

    agent_id: str
    session_id: str
    decision_id: str
    action_type: str
    reason: str
    required_role: str


class StepUpResolved(DomainEvent):
    """Emitted when an operator approves or rejects a step-up."""

    event_type: ClassVar[str] = "StepUpResolved"
    schema_version: ClassVar[int] = 1

    agent_id: str
    decision_id: str
    resolution: Literal["approve", "reject"]
    operator_id: str
    rationale: str = ""
    final_outcome: Literal["allow", "deny"]


__all__ = ["StepUpRequested", "StepUpResolved"]
