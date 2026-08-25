"""Decision feedback events (ADR-0012 FP/FN loop).

Feedback events are themselves decision events: they carry evidence,
reasoning, and confidence about why the original decision was right or
wrong. The pair (original decision + feedback) becomes labeled training
data.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from kavach.events._base import DomainEvent
from kavach.events.schemas.decision_primitives import (
    Confidence,
    Evidence,
    ReasoningTrace,
)

Feedback = Literal["false_positive", "true_positive", "partial", "unknown"]


class DecisionFeedbackRecorded(DomainEvent):
    """Emitted when a human or system labels a prior decision."""

    event_type: ClassVar[str] = "DecisionFeedbackRecorded"
    schema_version: ClassVar[int] = 1

    decision_id: str
    agent_id: str
    feedback: Feedback
    provided_by: str
    evidence: Evidence
    reasoning: ReasoningTrace
    confidence: Confidence
    narrative: str = ""


__all__ = ["DecisionFeedbackRecorded", "Feedback"]
