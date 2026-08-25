"""Tests for the event bus append-and-fan-out behaviour."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kavach.capabilities.storage import EventStore
from kavach.composition.bus import EventBus
from kavach.events._base import DomainEvent
from kavach.events.schemas import ActionExecuted


class _RecordingHandler:
    """A projection handler that records what it consumed."""

    consumes = frozenset({"ActionExecuted"})

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        del session
        self.seen.append(event.event_type)


async def test_publish_appends_and_fans_out(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    handler = _RecordingHandler()
    bus = EventBus(store=event_store, handlers=[handler])

    async with session_factory() as session:
        await bus.publish(
            session,
            ActionExecuted(tenant_id="t1", agent_id="a", session_id="s", action_type="x"),
        )
        await session.commit()

    assert handler.seen == ["ActionExecuted"]
    async with session_factory() as session:
        stored = await event_store.read_all(session)
    assert len(stored) == 1


async def test_handler_not_invoked_for_unconsumed_event(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    class OnlyDecisions:
        consumes = frozenset({"DecisionEmitted"})

        def __init__(self) -> None:
            self.count = 0

        async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
            del session, event
            self.count += 1

    handler = OnlyDecisions()
    bus = EventBus(store=event_store, handlers=[handler])

    async with session_factory() as session:
        await bus.publish(
            session,
            ActionExecuted(tenant_id="t1", agent_id="a", session_id="s", action_type="x"),
        )
        await session.commit()

    assert handler.count == 0
