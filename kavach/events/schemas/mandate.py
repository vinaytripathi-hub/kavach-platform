"""Signed mandate primitives and lifecycle events (ADR-0018).

A mandate is a bounded authorization from a task originator to an agent.
The credential itself is verified by ``MandateVerifier``; these types are
the semantic object and the audit-chain events that record issuance,
presentation, and revocation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from kavach.events._base import DomainEvent, utcnow

MandateOperator = Literal["eq", "ne", "lte", "gte", "lt", "gt", "in", "matches"]
OriginatorKind = Literal["human", "service", "agent", "wallet"]


class MandateConstraint(BaseModel):
    """One bound on action parameters (for example amount <= 50000)."""

    model_config = ConfigDict(extra="forbid")

    path: str
    operator: MandateOperator
    value: Any = None


class Mandate(BaseModel):
    """A signed, bounded authorization from an originator to an agent."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    mandate_id: str
    originator_id: str
    originator_kind: OriginatorKind
    agent_id: str
    action_scope: list[str]
    constraints: list[MandateConstraint] = Field(default_factory=list)
    issued_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    parent_mandate_id: str | None = None
    nonce: str


class MandateIssued(DomainEvent):
    """Emitted when a mandate is created and stored."""

    event_type: ClassVar[str] = "MandateIssued"
    schema_version: ClassVar[int] = 1

    mandate_id: str
    originator_id: str
    agent_id: str
    action_scope: list[str]
    constraints: list[MandateConstraint] = Field(default_factory=list)
    expires_at: datetime
    mandate_digest: str
    parent_mandate_id: str | None = None


class MandatePresented(DomainEvent):
    """Emitted when a mandate is presented at decision time."""

    event_type: ClassVar[str] = "MandatePresented"
    schema_version: ClassVar[int] = 1

    agent_id: str
    decision_id: str
    mandate_id: str
    verified: bool
    reason: str


class MandateRevoked(DomainEvent):
    """Emitted when a mandate is revoked before expiry."""

    event_type: ClassVar[str] = "MandateRevoked"
    schema_version: ClassVar[int] = 1

    mandate_id: str
    agent_id: str
    revoked_by: str
    reason: str = ""


__all__ = [
    "Mandate",
    "MandateConstraint",
    "MandateIssued",
    "MandateOperator",
    "MandatePresented",
    "MandateRevoked",
    "OriginatorKind",
]
