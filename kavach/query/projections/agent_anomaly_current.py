"""Current anomaly projection (ADR-0019)."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage import EventStore
from kavach.events._base import DomainEvent
from kavach.events.schemas.monitor import AnomalyAcknowledged, AnomalyDetected
from kavach.query.projections._tables import AgentAnomalyCurrentRow

_RANK = {"info": 0, "warn": 1, "critical": 2}


class AgentAnomalyCurrentProjection:
    """Keeps the highest-severity open anomaly per agent."""

    consumes = frozenset({"AnomalyDetected", "AnomalyAcknowledged"})
    tables = ("proj_agent_anomaly_current",)

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        if isinstance(event, AnomalyDetected):
            existing = await session.get(AgentAnomalyCurrentRow, (event.tenant_id, event.agent_id))
            incoming = _RANK[event.severity]
            if existing is None:
                session.add(
                    AgentAnomalyCurrentRow(
                        tenant_id=event.tenant_id,
                        agent_id=event.agent_id,
                        anomaly_id=event.anomaly_id,
                        detector_id=event.detector_id,
                        severity=event.severity,
                        status="open",
                        description=event.description,
                        first_seen=event.occurred_at,
                    )
                )
            elif existing.status != "open" or incoming >= _RANK[existing.severity]:
                existing.anomaly_id = event.anomaly_id
                existing.detector_id = event.detector_id
                existing.severity = event.severity
                existing.status = "open"
                existing.description = event.description
            await session.flush()
        elif isinstance(event, AnomalyAcknowledged):
            existing = await session.get(AgentAnomalyCurrentRow, (event.tenant_id, event.agent_id))
            if existing is None or existing.anomaly_id != event.anomaly_id:
                return
            existing.status = event.resolution
            await session.flush()

    async def rebuild(self, session: AsyncSession, event_store: EventStore) -> None:
        await session.execute(delete(AgentAnomalyCurrentRow))
        for event in await event_store.read_all(session):
            if event.event_type in self.consumes:
                await self.handle(session, event)
