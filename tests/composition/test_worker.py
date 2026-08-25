"""Tests for the outbox webhook dispatcher."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kavach.capabilities.audit import AuditExporter
from kavach.capabilities.storage import EventStore
from kavach.composition.bus import EventBus
from kavach.composition.service import SubstrateService
from kavach.composition.worker import WebhookDispatcher, sign_body
from kavach.events.schemas import ActionExecuted


def _action() -> ActionExecuted:
    return ActionExecuted(
        tenant_id="bank-1", agent_id="agent-1", session_id="s1", action_type="kyc.x"
    )


def _service(
    session_factory: async_sessionmaker[AsyncSession],
    bus: EventBus,
    event_store: EventStore,
) -> SubstrateService:
    return SubstrateService(
        session_factory,
        bus,
        event_store,
        audit_exporter=AuditExporter(b"test-key"),
        policy_engines={},
    )


async def test_dispatch_delivers_to_matching_subscription(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    bus = EventBus(store=event_store)
    # Publish an event (writes the outbox row).
    async with session_factory() as session:
        await bus.publish(session, _action())
        await session.commit()

    # Register a subscription for ActionExecuted.
    svc = _service(session_factory, bus, event_store)
    await svc.create_webhook_subscription(
        tenant_id="bank-1",
        url="https://partner.example/webhook",
        event_types=["ActionExecuted"],
        secret="shh",
    )

    sent: list[tuple[str, bytes, dict[str, str]]] = []

    async def fake_sender(url: str, body: bytes, headers: dict[str, str]) -> int:
        sent.append((url, body, headers))
        return 200

    dispatcher = WebhookDispatcher(session_factory, sender=fake_sender)
    handled = await dispatcher.process_once()

    assert handled == 1
    assert len(sent) == 1
    url, body, headers = sent[0]
    assert url == "https://partner.example/webhook"
    assert headers["X-Kavach-Event-Type"] == "ActionExecuted"
    assert headers["X-Kavach-Signature"] == sign_body("shh", body)

    # Re-processing finds nothing (row marked dispatched).
    assert await dispatcher.process_once() == 0


async def test_failed_delivery_is_retained_for_retry(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    bus = EventBus(store=event_store)
    async with session_factory() as session:
        await bus.publish(session, _action())
        await session.commit()

    svc = _service(session_factory, bus, event_store)
    await svc.create_webhook_subscription(
        tenant_id="bank-1",
        url="https://partner.example/webhook",
        event_types=["ActionExecuted"],
    )

    async def failing_sender(url: str, body: bytes, headers: dict[str, str]) -> int:
        del url, body, headers
        return 500

    dispatcher = WebhookDispatcher(session_factory, sender=failing_sender)
    await dispatcher.process_once()
    # Still pending because delivery failed.
    assert await dispatcher.process_once() == 1


async def test_no_subscription_marks_dispatched(
    session_factory: async_sessionmaker[AsyncSession], event_store: EventStore
) -> None:
    bus = EventBus(store=event_store)
    async with session_factory() as session:
        await bus.publish(session, _action())
        await session.commit()

    async def sender(url: str, body: bytes, headers: dict[str, str]) -> int:
        del url, body, headers
        return 200

    dispatcher = WebhookDispatcher(session_factory, sender=sender)
    assert await dispatcher.process_once() == 1
    assert await dispatcher.process_once() == 0
