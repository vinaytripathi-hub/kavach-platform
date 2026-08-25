"""Event store: append-and-outbox writer and replay reader (ADR-0008)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage._internal.models import EventRow, OutboxRow
from kavach.events import deserialize_event, utcnow
from kavach.events._base import DomainEvent


class EventStore:
    """Persists domain events and reconstructs them for replay.

    ``append`` writes the event row and a matching outbox row in the
    caller's session, without committing. The caller (or the event bus)
    owns the transaction boundary, so the event, its outbox entry, and
    any synchronous projection updates commit atomically.
    """

    async def append(self, session: AsyncSession, event: DomainEvent) -> EventRow:
        """Append an event and enqueue it on the outbox (no commit)."""
        recorded_at = utcnow()
        payload = event.payload()
        row = EventRow(
            event_id=event.event_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            tenant_id=event.tenant_id,
            aggregate_id=event.aggregate_id(),
            occurred_at=event.occurred_at,
            recorded_at=recorded_at,
            payload=payload,
        )
        session.add(row)
        session.add(
            OutboxRow(
                event_id=event.event_id,
                event_type=event.event_type,
                tenant_id=event.tenant_id,
                payload=payload,
                created_at=recorded_at,
                attempts=0,
            )
        )
        await session.flush()
        return row

    async def read_aggregate(
        self, session: AsyncSession, tenant_id: str, aggregate_id: str
    ) -> list[DomainEvent]:
        """All events for one aggregate (e.g. an agent), in emission order."""
        stmt = (
            select(EventRow)
            .where(
                EventRow.tenant_id == tenant_id,
                EventRow.aggregate_id == aggregate_id,
            )
            .order_by(EventRow.seq)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [self._reconstruct(r) for r in rows]

    async def read_all(
        self, session: AsyncSession, *, after_seq: int = 0, limit: int | None = None
    ) -> list[DomainEvent]:
        """Events with ``seq`` greater than ``after_seq``, in order."""
        stmt = select(EventRow).where(EventRow.seq > after_seq).order_by(EventRow.seq)
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return [self._reconstruct(r) for r in rows]

    @staticmethod
    def _reconstruct(row: EventRow) -> DomainEvent:
        return deserialize_event(row.event_type, row.schema_version, row.payload)
