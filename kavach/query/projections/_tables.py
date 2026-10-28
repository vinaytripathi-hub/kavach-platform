"""ORM tables for read-side projections (ADR-0009).

Projection tables are migration-managed like any other Postgres schema.
They share the storage capability's ``Base`` so a single metadata sees
the event log, the outbox, and the projections together.

Projections are derivative: the event log is the source of truth. These
tables can always be rebuilt from the log via the projection rebuild
methods (ADR-0009).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from kavach.capabilities.storage import Base


class AgentTimelineRow(Base):
    """Flattened activity timeline, one row per event of interest."""

    __tablename__ = "proj_agent_timeline"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    agent_id: Mapped[str] = mapped_column(String(200), index=True)
    seq: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)


class AgentTrustCurrentRow(Base):
    """Current multidimensional trust assessment per agent + context."""

    __tablename__ = "proj_agent_trust_current"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    context: Mapped[str] = mapped_column(String(100), primary_key=True)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON)
    composed_scalar: Mapped[float | None] = mapped_column(nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DecisionLogRow(Base):
    """One row per decision, with embedded evidence/reasoning/confidence."""

    __tablename__ = "proj_decision_log"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    agent_id: Mapped[str] = mapped_column(String(200), index=True)
    action_type: Mapped[str] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(String(50))
    decided_by: Mapped[str] = mapped_column(String(200))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    reasoning: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    data_sufficiency: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(50), nullable=True)


class StepUpQueueRow(Base):
    """Pending and resolved human-in-the-loop step-ups (Article 14)."""

    __tablename__ = "proj_step_up_queue"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    agent_id: Mapped[str] = mapped_column(String(200), index=True)
    action_type: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    required_role: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), index=True, default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    operator_id: Mapped[str | None] = mapped_column(String(200), nullable=True)


class MandateCurrentRow(Base):
    """Current mandate state for operator lookup (ADR-0018)."""

    __tablename__ = "proj_mandate_current"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    mandate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(200), index=True)
    originator_id: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mandate_digest: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentAnomalyCurrentRow(Base):
    """Highest-severity open anomaly per agent (ADR-0019)."""

    __tablename__ = "proj_agent_anomaly_current"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    anomaly_id: Mapped[str] = mapped_column(String(64))
    detector_id: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="open")
    description: Mapped[str] = mapped_column(Text, default="")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
