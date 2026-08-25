"""Outbox and webhook-subscription read/write access for the dispatcher."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage._internal.models import (
    OutboxRow,
    WebhookSubscriptionRow,
)
from kavach.events import utcnow


class OutboxStore:
    """Reads pending outbox rows and marks delivery outcomes."""

    async def undispatched(self, session: AsyncSession, *, limit: int = 100) -> list[OutboxRow]:
        stmt = (
            select(OutboxRow)
            .where(OutboxRow.dispatched_at.is_(None))
            .order_by(OutboxRow.id)
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def mark_dispatched(self, session: AsyncSession, row: OutboxRow) -> None:
        row.dispatched_at = utcnow()
        await session.flush()

    async def mark_failed(self, session: AsyncSession, row: OutboxRow, error: str) -> None:
        row.attempts += 1
        row.last_error = error[:1000]
        await session.flush()


class WebhookStore:
    """Reads active webhook subscriptions for a tenant and event type."""

    async def active_for(
        self, session: AsyncSession, tenant_id: str, event_type: str
    ) -> list[WebhookSubscriptionRow]:
        stmt = select(WebhookSubscriptionRow).where(
            WebhookSubscriptionRow.tenant_id == tenant_id,
            WebhookSubscriptionRow.active.is_(True),
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [r for r in rows if event_type in r.event_types]
