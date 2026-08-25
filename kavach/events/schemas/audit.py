"""Audit-related events."""

from __future__ import annotations

from typing import ClassVar

from kavach.events._base import DomainEvent
from kavach.events.schemas.decision_primitives import Evidence


class EvidenceRecorded(DomainEvent):
    """Emitted when evidence is captured against an agent or decision."""

    event_type: ClassVar[str] = "EvidenceRecorded"
    schema_version: ClassVar[int] = 1

    agent_id: str
    decision_id: str | None = None
    evidence: Evidence
    note: str = ""


__all__ = ["EvidenceRecorded"]
