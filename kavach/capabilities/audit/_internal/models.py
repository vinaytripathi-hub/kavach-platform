"""ORM table for the audit hash chain.

The audit capability is high-extractability (ADR-0011): its data model is
self-contained. The table shares the storage ``Base`` only so a single
migration baseline covers it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from kavach.capabilities.storage import Base


class AuditRecordRow(Base):
    """One tamper-evident, HMAC-chained record per emitted event."""

    __tablename__ = "audit_records"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    position: Mapped[int] = mapped_column(Integer, index=True)
    event_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    agent_id: Mapped[str | None] = mapped_column(String(200), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    this_hash: Mapped[str] = mapped_column(String(64))
    payload_digest: Mapped[str] = mapped_column(String(64))
