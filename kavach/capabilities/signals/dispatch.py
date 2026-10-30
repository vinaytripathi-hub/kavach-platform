"""Outbox drain for CAEP/SSF delivery (ADR-0020)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kavach.capabilities.signals import SIGNAL_EVENT_TYPES, build_set
from kavach.capabilities.storage import SignalOutboxRow, session_scope
from kavach.events import utcnow
from kavach.events._base import DomainEvent

Sender = Callable[[str, bytes, dict[str, str]], Awaitable[int]]
_HTTP_ERROR_THRESHOLD = 300


class SignalOutboxProjection:
    """Copies revocation and critical-anomaly events onto the signal outbox."""

    @property
    def consumes(self) -> frozenset[str]:
        return SIGNAL_EVENT_TYPES

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        if event.event_type == "AnomalyDetected" and getattr(event, "severity", None) != "critical":
            return
        payload = event.payload()
        session.add(
            SignalOutboxRow(
                event_id=event.event_id,
                event_type=event.event_type,
                tenant_id=event.tenant_id,
                payload=payload,
                created_at=utcnow(),
            )
        )


class SignalDispatcher:
    """Delivers pending signal-outbox rows as Security Event Tokens."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sender: Sender,
        *,
        receiver_url: str,
        issuer: str,
        audience: str,
        key: bytes,
        batch_size: int = 100,
    ) -> None:
        self._session_factory = session_factory
        self._sender = sender
        self._receiver_url = receiver_url
        self._issuer = issuer
        self._audience = audience
        self._key = key
        self._batch_size = batch_size

    async def process_once(self) -> int:
        """Deliver one batch. Returns the number of rows attempted."""
        if not self._receiver_url:
            return 0
        handled = 0
        async with session_scope(self._session_factory) as session:
            rows = (
                (
                    await session.execute(
                        select(SignalOutboxRow)
                        .where(SignalOutboxRow.dispatched_at.is_(None))
                        .limit(self._batch_size)
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                await self._deliver(row)
                handled += 1
        return handled

    async def _deliver(self, row: SignalOutboxRow) -> None:
        token = build_set(
            row.payload,
            row.event_type,
            issuer=self._issuer,
            audience=self._audience,
            key=self._key,
        )
        try:
            status = await self._sender(
                self._receiver_url,
                token.encode("utf-8"),
                {"Content-Type": "application/secevent+jwt"},
            )
        except Exception as exc:  # receiver errors vary; leave the row for retry
            row.last_error = f"Delivery error: {exc}"
            return
        if status >= _HTTP_ERROR_THRESHOLD:
            row.last_error = f"Delivery returned {status}"
            return
        row.dispatched_at = utcnow()
        row.last_error = None

    async def run(self, *, poll_interval: float = 0.5) -> None:  # pragma: no cover
        """Continuously drain the signal outbox."""
        while True:
            handled = await self.process_once()
            if handled == 0:
                await asyncio.sleep(poll_interval)
