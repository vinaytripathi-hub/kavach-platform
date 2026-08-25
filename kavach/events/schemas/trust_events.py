"""Trust assessment events (ADR-0014)."""

from __future__ import annotations

from typing import ClassVar

from kavach.events._base import DomainEvent
from kavach.events.schemas.trust import TrustAssessment


class TrustAssessmentEmitted(DomainEvent):
    """Emitted when the substrate produces a multidimensional trust assessment."""

    event_type: ClassVar[str] = "TrustAssessmentEmitted"
    schema_version: ClassVar[int] = 1

    agent_id: str
    context: str
    assessment: TrustAssessment


__all__ = ["TrustAssessmentEmitted"]
