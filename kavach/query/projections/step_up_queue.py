"""Step-up queue projection (ADR-0009; EU AI Act Art. 14)."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage import EventStore
from kavach.events._base import DomainEvent
from kavach.events.schemas import StepUpRequested, StepUpResolved
from kavach.query.projections._tables import StepUpQueueRow


class StepUpQueueProjection:
    """Pending and resolved human-in-the-loop step-ups."""

    consumes = frozenset({"StepUpRequested", "StepUpResolved"})
    tables = ("proj_step_up_queue",)

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        if isinstance(event, StepUpRequested):
            await self._on_requested(session, event)
        elif isinstance(event, StepUpResolved):
            await self._on_resolved(session, event)

    async def _on_requested(self, session: AsyncSession, event: StepUpRequested) -> None:
        existing = await session.get(StepUpQueueRow, event.decision_id)
        if existing is not None:
            return
        session.add(
            StepUpQueueRow(
                decision_id=event.decision_id,
                tenant_id=event.tenant_id,
                agent_id=event.agent_id,
                action_type=event.action_type,
                reason=event.reason,
                required_role=event.required_role,
                status="pending",
                requested_at=event.occurred_at,
            )
        )
        await session.flush()

    async def _on_resolved(self, session: AsyncSession, event: StepUpResolved) -> None:
        existing = await session.get(StepUpQueueRow, event.decision_id)
        if existing is None:
            return
        existing.status = "resolved"
        existing.resolved_at = event.occurred_at
        existing.resolution = event.resolution
        existing.operator_id = event.operator_id
        await session.flush()

    async def rebuild(self, session: AsyncSession, event_store: EventStore) -> None:
        await session.execute(delete(StepUpQueueRow))
        for event in await event_store.read_all(session):
            if event.event_type in self.consumes:
                await self.handle(session, event)
