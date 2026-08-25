"""Event bus: append-and-fan-out coordinator (ADR-0008, ADR-0009).

The bus is part of the composition layer because it wires the storage
event store to the read-side projection handlers. When a capability
publishes an event, the bus appends it to the event log (which also
enqueues the outbox row) and synchronously runs every projection handler
that consumes the event — all within the caller's transaction, so the
event, its outbox entry, and the projection updates commit atomically
(the synchronous-by-default rule of ADR-0009).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage.contracts import SupportsAppend
from kavach.events._base import DomainEvent


@runtime_checkable
class ProjectionHandler(Protocol):
    """A read-side projection that consumes events and updates its tables.

    ``consumes`` is declared read-only so both class-attribute and
    property implementations satisfy the protocol (the audit chain writer
    computes its consumed set dynamically).
    """

    @property
    def consumes(self) -> frozenset[str]: ...

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None: ...


class EventBus:
    """Publishes events to the log and fans them out to projections."""

    def __init__(
        self,
        store: SupportsAppend,
        handlers: list[ProjectionHandler] | None = None,
    ) -> None:
        self._store = store
        self._handlers = list(handlers or [])

    def register(self, handler: ProjectionHandler) -> None:
        """Add a projection handler to the fan-out set."""
        self._handlers.append(handler)

    @property
    def handlers(self) -> list[ProjectionHandler]:
        return list(self._handlers)

    async def publish(self, session: AsyncSession, event: DomainEvent) -> None:
        """Append ``event`` and run consuming projection handlers (no commit)."""
        await self._store.append(session, event)
        for handler in self._handlers:
            if event.event_type in handler.consumes:
                await handler.handle(session, event)
