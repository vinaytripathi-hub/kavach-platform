"""Current trust assessment projection (ADR-0009, ADR-0014)."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage import EventStore
from kavach.events._base import DomainEvent
from kavach.events.schemas import TrustAssessmentEmitted
from kavach.query.projections._tables import AgentTrustCurrentRow


class AgentTrustCurrentProjection:
    """Maintains the latest trust tensor per agent + context."""

    consumes = frozenset({"TrustAssessmentEmitted"})
    tables = ("proj_agent_trust_current",)

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        if not isinstance(event, TrustAssessmentEmitted):
            return
        assessment = event.assessment
        dimensions = {
            name: dim.model_dump(mode="json") for name, dim in assessment.dimensions.items()
        }
        composed = assessment.compose()
        pk = (event.tenant_id, event.agent_id, event.context)
        existing = await session.get(AgentTrustCurrentRow, pk)
        if existing is None:
            session.add(
                AgentTrustCurrentRow(
                    tenant_id=event.tenant_id,
                    agent_id=event.agent_id,
                    context=event.context,
                    dimensions=dimensions,
                    composed_scalar=composed,
                    assessed_at=assessment.assessed_at,
                )
            )
        else:
            existing.dimensions = dimensions
            existing.composed_scalar = composed
            existing.assessed_at = assessment.assessed_at
        await session.flush()

    async def rebuild(self, session: AsyncSession, event_store: EventStore) -> None:
        await session.execute(delete(AgentTrustCurrentRow))
        for event in await event_store.read_all(session):
            if event.event_type in self.consumes:
                await self.handle(session, event)
