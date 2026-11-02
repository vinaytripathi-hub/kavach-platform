"""SQLAlchemy ORM models for the substrate (ADR-0008, ADR-0009).

Tables fall into three groups:

- The event log (``events``) — the substrate's source of truth.
- The transactional outbox (``outbox``) — events queued for outbound
  delivery (webhooks), written in the same transaction as the event.
- Operational tables — idempotency keys, and the read-side projection
  tables maintained by ``kavach.query`` (declared there but sharing this
  ``Base`` so a single ``metadata.create_all`` / Alembic autogenerate
  sees them all).

JSON columns use the portable ``JSON`` type so the same models run on
PostgreSQL 16 (on-prem, ADR-0004) and on SQLite (fast unit tests).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base shared across all substrate tables."""


class EventRow(Base):
    """One row per emitted domain event. The event log is source of truth."""

    __tablename__ = "events"

    seq: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    aggregate_id: Mapped[str | None] = mapped_column(String(200), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class OutboxRow(Base):
    """Outbound delivery queue, written transactionally with each event."""

    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class IdempotencyRow(Base):
    """Stored result of an idempotent request, keyed by tenant + key."""

    __tablename__ = "idempotency_keys"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    idem_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    status_code: Mapped[int] = mapped_column(Integer)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebhookSubscriptionRow(Base):
    """A partner system's subscription to outbound substrate events."""

    __tablename__ = "webhook_subscriptions"

    subscription_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    event_types: Mapped[list[str]] = mapped_column(JSON)
    secret: Mapped[str | None] = mapped_column(String(200), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentRegistrationRow(Base):
    """A registered agent (admin onboarding)."""

    __tablename__ = "agent_registrations"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(300))
    use_case: Mapped[str | None] = mapped_column(String(100), nullable=True)
    agent_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MandateRow(Base):
    """Stored mandate token and payload (ADR-0018)."""

    __tablename__ = "mandates"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    mandate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(200), index=True)
    originator_id: Mapped[str] = mapped_column(String(200))
    token: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    parent_mandate_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MandateRevocationRow(Base):
    """Revocation record for a mandate (ADR-0018)."""

    __tablename__ = "mandate_revocations"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    mandate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    revoked_by: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text, default="")
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentCredentialRow(Base):
    """A minted session or refresh credential (ADR-0020)."""

    __tablename__ = "agent_credentials"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    credential_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(200), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[list[str]] = mapped_column(JSON)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    parent_credential_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    holder_token: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentRevocationRow(Base):
    """Revocation of an entire agent principal (ADR-0020)."""

    __tablename__ = "agent_revocations"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    revoked_by: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text, default="")
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CredentialRevocationRow(Base):
    """Revocation of one credential ``jti`` (ADR-0020).

    ``reason="rotated"`` retires a refresh token and does not revoke the
    rest of its credential family. Any other reason revokes the family.
    """

    __tablename__ = "credential_revocations"

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    credential_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(200))
    revoked_by: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text, default="")
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SignalOutboxRow(Base):
    """Pending CAEP/SSF delivery, written in the publishing transaction."""

    __tablename__ = "signal_outbox"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
