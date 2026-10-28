"""Mandate projection (ADR-0009, ADR-0018)."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage import EventStore
from kavach.events._base import DomainEvent
from kavach.events.schemas import MandateIssued, MandateRevoked
from kavach.query.projections._tables import MandateCurrentRow


class MandateCurrentProjection:
    """Tracks issued and revoked mandates."""

    consumes = frozenset({"MandateIssued", "MandateRevoked"})
    tables = ("proj_mandate_current",)

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        if isinstance(event, MandateIssued):
            session.add(
                MandateCurrentRow(
                    tenant_id=event.tenant_id,
                    mandate_id=event.mandate_id,
                    agent_id=event.agent_id,
                    originator_id=event.originator_id,
                    status="active",
                    expires_at=event.expires_at,
                    mandate_digest=event.mandate_digest,
                    updated_at=event.occurred_at,
                )
            )
            await session.flush()
        elif isinstance(event, MandateRevoked):
            row = await session.get(MandateCurrentRow, (event.tenant_id, event.mandate_id))
            if row is None:
                return
            row.status = "revoked"
            row.updated_at = event.occurred_at
            await session.flush()

    async def rebuild(self, session: AsyncSession, event_store: EventStore) -> None:
        await session.execute(delete(MandateCurrentRow))
        for event in await event_store.read_all(session):
            if event.event_type in self.consumes:
                await self.handle(session, event)
