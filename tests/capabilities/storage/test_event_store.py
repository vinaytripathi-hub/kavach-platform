"""Tests for the event store: append, outbox, and replay."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kavach.capabilities.storage import EventStore
from kavach.capabilities.storage._internal.models import OutboxRow
from kavach.events.schemas import (
    ActionExecuted,
    DecisionEmitted,
    Evidence,
    ReasoningTrace,
    rule_deterministic,
)


def _action(agent: str = "agent-1", action: str = "kyc.document.verify") -> ActionExecuted:
    return ActionExecuted(tenant_id="t1", agent_id=agent, session_id="s1", action_type=action)


async def test_append_persists_event_and_outbox(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    async with session_factory() as session:
        await event_store.append(session, _action())
        await session.commit()

    async with session_factory() as session:
        events = await event_store.read_all(session)
        outbox_count = (
            await session.execute(select(func.count()).select_from(OutboxRow))
        ).scalar_one()

    assert len(events) == 1
    assert events[0].event_type == "ActionExecuted"
    assert outbox_count == 1


async def test_read_aggregate_filters_and_orders(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    async with session_factory() as session:
        await event_store.append(session, _action(agent="a", action="first"))
        await event_store.append(session, _action(agent="a", action="second"))
        await event_store.append(session, _action(agent="b", action="other"))
        await session.commit()

    async with session_factory() as session:
        a_events = await event_store.read_aggregate(session, "t1", "a")

    assert [e.action_type for e in a_events] == ["first", "second"]  # type: ignore[attr-defined]


async def test_replay_reconstructs_decision_with_primitives(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    decision = DecisionEmitted(
        tenant_id="t1",
        agent_id="agent-1",
        session_id="s1",
        decision_id="d1",
        action_type="account.funds.transfer",
        outcome="deny",
        evidence=Evidence(attributes={"amount": 999}),
        reasoning=ReasoningTrace(kind="rule", rule_id="r1", decision_path="blocked"),
        confidence=rule_deterministic(),
        decided_by="rule:r1",
    )
    async with session_factory() as session:
        await event_store.append(session, decision)
        await session.commit()

    async with session_factory() as session:
        restored = await event_store.read_all(session)

    assert len(restored) == 1
    got = restored[0]
    assert isinstance(got, DecisionEmitted)
    assert got.evidence.attributes["amount"] == 999
    assert got.confidence.kind == "rule_deterministic"
    assert got == decision


async def test_read_all_after_seq_paginates(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    async with session_factory() as session:
        for i in range(5):
            await event_store.append(session, _action(action=f"a{i}"))
        await session.commit()

    async with session_factory() as session:
        first_two = await event_store.read_all(session, limit=2)
        assert len(first_two) == 2
        rest = await event_store.read_all(session, after_seq=2)
        assert len(rest) == 3
