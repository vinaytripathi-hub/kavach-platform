"""Tests that projections rebuild from the event log (ADR-0009 DR guarantee)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kavach.capabilities.storage import EventStore
from kavach.composition.bus import EventBus
from kavach.events.schemas import (
    ActionExecuted,
    DecisionEmitted,
    Evidence,
    ModalitySufficiency,
    ReasoningTrace,
    StepUpRequested,
    TrustAssessment,
    TrustAssessmentEmitted,
    TrustDimension,
    compose_sufficiency,
    rule_deterministic,
)
from kavach.query.projections._tables import (
    AgentTimelineRow,
    AgentTrustCurrentRow,
    DecisionLogRow,
    StepUpQueueRow,
)
from kavach.query.projections.agent_timeline import AgentTimelineProjection
from kavach.query.projections.agent_trust_current import AgentTrustCurrentProjection
from kavach.query.projections.decision_log import DecisionLogProjection
from kavach.query.projections.step_up_queue import StepUpQueueProjection


def _events() -> list[object]:
    suff = compose_sufficiency(
        {"m": ModalitySufficiency(modality="m", band="warm", observations=10)}
    )
    return [
        ActionExecuted(tenant_id="t1", agent_id="a", session_id="s", action_type="kyc.x"),
        DecisionEmitted(
            tenant_id="t1",
            agent_id="a",
            session_id="s",
            decision_id="d1",
            action_type="account.funds.transfer",
            outcome="step_up",
            evidence=Evidence(attributes={"amount": 100000}),
            reasoning=ReasoningTrace(kind="rule", rule_id="r1", decision_path="p"),
            confidence=rule_deterministic(),
            decided_by="rule:r1",
        ),
        StepUpRequested(
            tenant_id="t1",
            agent_id="a",
            session_id="s",
            decision_id="d1",
            action_type="account.funds.transfer",
            reason="high value",
            required_role="senior_ops",
        ),
        TrustAssessmentEmitted(
            tenant_id="t1",
            agent_id="a",
            context="customer_service",
            assessment=TrustAssessment(
                agent_id="a",
                context="customer_service",
                dimensions={
                    "credential_integrity": TrustDimension(
                        name="credential_integrity", value=0.8, sufficiency=suff
                    )
                },
            ),
        ),
    ]


async def _count(session_factory: async_sessionmaker[AsyncSession], model: type) -> int:
    async with session_factory() as session:
        stmt = select(func.count()).select_from(model)
        result: int = (await session.execute(stmt)).scalar_one()
        return result


async def test_projections_rebuild_from_event_log(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    projections: list[Any] = [
        AgentTimelineProjection(),
        AgentTrustCurrentProjection(),
        DecisionLogProjection(),
        StepUpQueueProjection(),
    ]
    bus = EventBus(store=event_store, handlers=projections)

    async with session_factory() as session:
        for event in _events():
            await bus.publish(session, event)  # type: ignore[arg-type]
        await session.commit()

    before = {
        m.__name__: await _count(session_factory, m)
        for m in (AgentTimelineRow, AgentTrustCurrentRow, DecisionLogRow, StepUpQueueRow)
    }
    assert before["AgentTimelineRow"] == 4
    assert before["DecisionLogRow"] == 1
    assert before["StepUpQueueRow"] == 1
    assert before["AgentTrustCurrentRow"] == 1

    # Rebuild every projection from the event log and confirm parity.
    async with session_factory() as session:
        for proj in projections:
            await proj.rebuild(session, event_store)
        await session.commit()

    after = {
        m.__name__: await _count(session_factory, m)
        for m in (AgentTimelineRow, AgentTrustCurrentRow, DecisionLogRow, StepUpQueueRow)
    }
    assert after == before
