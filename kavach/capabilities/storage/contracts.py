"""Protocols the storage capability provides to the rest of the substrate.

Per ADR-0007, capabilities depend on Protocols, not concrete classes.
The event bus depends on ``SupportsAppend``; the API layer depends on
``SupportsIdempotency``. The composition layer wires the concrete
``EventStore`` / ``IdempotencyStore`` implementations to these.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from kavach.events._base import DomainEvent


class SupportsAppend(Protocol):
    """An object that can append a domain event within a session.

    The return value (a persisted row) is intentionally opaque here; the
    event bus discards it. Callers needing the row use the concrete
    ``EventStore`` directly.
    """

    async def append(self, session: AsyncSession, event: DomainEvent) -> object: ...


class SupportsReplay(Protocol):
    """An object that can read events back for replay/timeline."""

    async def read_aggregate(
        self, session: AsyncSession, tenant_id: str, aggregate_id: str
    ) -> list[DomainEvent]: ...

    async def read_all(
        self, session: AsyncSession, *, after_seq: int = 0, limit: int | None = None
    ) -> list[DomainEvent]: ...


class SupportsIdempotency(Protocol):
    """An object that stores and retrieves idempotent request results."""

    async def get(
        self, session: AsyncSession, tenant_id: str, key: str
    ) -> tuple[int, dict[str, Any]] | None: ...

    async def put(
        self,
        session: AsyncSession,
        tenant_id: str,
        key: str,
        status_code: int,
        response_json: dict[str, Any],
    ) -> None: ...
