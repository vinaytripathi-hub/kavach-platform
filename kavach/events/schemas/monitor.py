"""Monitor events (ADR-0019)."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field

from kavach.events._base import DomainEvent

Severity = Literal["info", "warn", "critical"]
AnomalyResolution = Literal["true_positive", "false_positive", "needs_investigation"]


class AgentMetricSnapshot(DomainEvent):
    """A point-in-time metric window for one agent."""

    event_type: ClassVar[str] = "AgentMetricSnapshot"
    schema_version: ClassVar[int] = 1

    agent_id: str
    window: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class AnomalyDetected(DomainEvent):
    """A bounded anomaly signal. Severity is the only policy-grade field."""

    event_type: ClassVar[str] = "AnomalyDetected"
    schema_version: ClassVar[int] = 1

    agent_id: str
    anomaly_id: str
    detector_id: str
    severity: Severity
    signal_score: float | None = None
    description: str
    triggering_event_ids: list[str] = Field(default_factory=list)
    decided_by: str


class AnomalyAcknowledged(DomainEvent):
    """Operator resolution of an anomaly. Feeds decision feedback."""

    event_type: ClassVar[str] = "AnomalyAcknowledged"
    schema_version: ClassVar[int] = 1

    agent_id: str
    anomaly_id: str
    resolution: AnomalyResolution
    operator_id: str
    rationale: str = ""
