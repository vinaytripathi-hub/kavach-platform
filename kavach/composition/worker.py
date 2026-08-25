"""Background worker: outbox dispatcher for outbound webhooks (ADR-0008).

The substrate writes events and outbox rows transactionally. This worker
drains the outbox and delivers each event to the subscriptions that match
its tenant and type, signing the body with the subscription secret. It is
deliberately at-least-once: a row is marked dispatched only after all
matching deliveries succeed, so failures are retried.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kavach.capabilities.storage import (
    OutboxRow,
    OutboxStore,
    WebhookStore,
    WebhookSubscriptionRow,
    session_scope,
)

# A sender takes (url, body_bytes, headers) and returns an HTTP status code.
Sender = Callable[[str, bytes, dict[str, str]], Awaitable[int]]

# HTTP status at/above which a webhook delivery is considered failed.
_HTTP_ERROR_THRESHOLD = 300


def sign_body(secret: str | None, body: bytes) -> str | None:
    """HMAC-SHA256 signature header value for a webhook body."""
    if not secret:
        return None
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def _httpx_sender(url: str, body: bytes, headers: dict[str, str]) -> int:
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, content=body, headers=headers)
        return resp.status_code


class WebhookDispatcher:
    """Drains the outbox and delivers events to webhook subscriptions."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        sender: Sender | None = None,
        *,
        batch_size: int = 100,
    ) -> None:
        self._session_factory = session_factory
        self._sender = sender or _httpx_sender
        self._batch_size = batch_size
        self._outbox = OutboxStore()
        self._webhooks = WebhookStore()

    async def process_once(self) -> int:
        """Process one batch of pending outbox rows. Returns rows handled."""
        handled = 0
        async with session_scope(self._session_factory) as session:
            rows = await self._outbox.undispatched(session, limit=self._batch_size)
            for row in rows:
                await self._dispatch_row(session, row)
                handled += 1
        return handled

    async def _dispatch_row(self, session: AsyncSession, row: OutboxRow) -> None:
        subs = await self._webhooks.active_for(session, row.tenant_id, row.event_type)
        body = json.dumps(row.payload, sort_keys=True).encode("utf-8")
        error = await self._deliver_all(subs, row, body)
        if error is not None:
            await self._outbox.mark_failed(session, row, error)
            return
        await self._outbox.mark_dispatched(session, row)

    async def _deliver_all(
        self, subs: list[WebhookSubscriptionRow], row: OutboxRow, body: bytes
    ) -> str | None:
        """Deliver to every subscription; return an error string on failure."""
        for sub in subs:
            headers = {
                "Content-Type": "application/json",
                "X-Kavach-Event-Type": row.event_type,
                "X-Kavach-Event-Id": row.event_id,
            }
            signature = sign_body(sub.secret, body)
            if signature:
                headers["X-Kavach-Signature"] = signature
            try:
                status = await self._sender(sub.url, body, headers)
            except Exception as exc:  # network/SDK errors vary; retry later
                return f"Delivery error: {exc}"
            if status >= _HTTP_ERROR_THRESHOLD:
                return f"Delivery returned {status}"
        return None

    async def run(self, *, poll_interval: float = 1.0) -> None:  # pragma: no cover
        """Continuously drain the outbox (used by the worker process)."""
        while True:
            handled = await self.process_once()
            if handled == 0:
                await asyncio.sleep(poll_interval)
