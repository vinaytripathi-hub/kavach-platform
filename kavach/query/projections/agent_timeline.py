"""Agent activity timeline projection (ADR-0009)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage import EventStore
from kavach.capabilities.storage._internal.models import EventRow
from kavach.events._base import DomainEvent
from kavach.query.projections._tables import AgentTimelineRow

_CONSUMED = frozenset(
    {
        "ActionExecuted",
        "DecisionEmitted",
        "StepUpRequested",
        "StepUpResolved",
        "TrustAssessmentEmitted",
        "DecisionFeedbackRecorded",
        "EvidenceRecorded",
    }
)


def _summary(event: DomainEvent) -> tuple[str, str | None]:  # noqa: PLR0911
    """Human-readable summary and optional outcome for a timeline entry."""
    et = event.event_type
    if et == "ActionExecuted":
        return f"Executed {getattr(event, 'action_type', '')}", None
    if et == "DecisionEmitted":
        return (
            f"Decision on {getattr(event, 'action_type', '')}",
            getattr(event, "outcome", None),
        )
    if et == "StepUpRequested":
        return f"Step-up requested: {getattr(event, 'reason', '')}", "step_up"
    if et == "StepUpResolved":
        return (
            f"Step-up {getattr(event, 'resolution', '')}",
            getattr(event, "final_outcome", None),
        )
    if et == "TrustAssessmentEmitted":
        return f"Trust assessed ({getattr(event, 'context', '')})", None
    if et == "DecisionFeedbackRecorded":
        return "Decision feedback recorded", getattr(event, "feedback", None)
    if et == "EvidenceRecorded":
        return "Evidence recorded", None
    return et, None


class AgentTimelineProjection:
    """Flattens events of interest into a per-agent timeline."""

    consumes = _CONSUMED
    tables = ("proj_agent_timeline",)

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        agent_id = event.aggregate_id()
        if agent_id is None:
            return
        seq = (
            await session.execute(select(EventRow.seq).where(EventRow.event_id == event.event_id))
        ).scalar_one_or_none() or 0
        summary, outcome = _summary(event)
        existing = await session.get(AgentTimelineRow, event.event_id)
        if existing is not None:
            return
        session.add(
            AgentTimelineRow(
                event_id=event.event_id,
                tenant_id=event.tenant_id,
                agent_id=agent_id,
                seq=seq,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                summary=summary,
                outcome=outcome,
            )
        )
        await session.flush()

    async def rebuild(self, session: AsyncSession, event_store: EventStore) -> None:
        await session.execute(delete(AgentTimelineRow))
        for event in await event_store.read_all(session):
            if event.event_type in self.consumes:
                await self.handle(session, event)
