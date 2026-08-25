"""Decision log projection (ADR-0009, ADR-0012)."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage import EventStore
from kavach.events._base import DomainEvent
from kavach.events.schemas import DecisionEmitted, DecisionFeedbackRecorded
from kavach.query.projections._tables import DecisionLogRow


class DecisionLogProjection:
    """One row per decision, with embedded evidence/reasoning/confidence."""

    consumes = frozenset({"DecisionEmitted", "DecisionFeedbackRecorded"})
    tables = ("proj_decision_log",)

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        if isinstance(event, DecisionEmitted):
            await self._on_decision(session, event)
        elif isinstance(event, DecisionFeedbackRecorded):
            await self._on_feedback(session, event)

    async def _on_decision(self, session: AsyncSession, event: DecisionEmitted) -> None:
        existing = await session.get(DecisionLogRow, event.decision_id)
        if existing is not None:
            return
        session.add(
            DecisionLogRow(
                decision_id=event.decision_id,
                tenant_id=event.tenant_id,
                agent_id=event.agent_id,
                action_type=event.action_type,
                outcome=event.outcome,
                decided_by=event.decided_by,
                occurred_at=event.occurred_at,
                evidence=event.evidence.model_dump(mode="json"),
                reasoning=event.reasoning.model_dump(mode="json"),
                confidence=event.confidence.model_dump(mode="json"),
                data_sufficiency=(
                    event.data_sufficiency.model_dump(mode="json")
                    if event.data_sufficiency is not None
                    else None
                ),
            )
        )
        await session.flush()

    async def _on_feedback(self, session: AsyncSession, event: DecisionFeedbackRecorded) -> None:
        existing = await session.get(DecisionLogRow, event.decision_id)
        if existing is not None:
            existing.feedback = event.feedback
            await session.flush()

    async def rebuild(self, session: AsyncSession, event_store: EventStore) -> None:
        await session.execute(delete(DecisionLogRow))
        for event in await event_store.read_all(session):
            if event.event_type in self.consumes:
                await self.handle(session, event)
