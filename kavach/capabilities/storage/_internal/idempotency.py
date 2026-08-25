"""Idempotency key store (ADR-0016).

State-changing POSTs accept an ``Idempotency-Key`` header; the substrate
deduplicates by ``(tenant_id, key)`` and returns the original result on
replay. This makes agent retries safe alongside the at-least-once outbox.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.storage._internal.models import IdempotencyRow
from kavach.events import utcnow


class IdempotencyStore:
    """Persist and look up stored responses for idempotent requests."""

    async def get(
        self, session: AsyncSession, tenant_id: str, key: str
    ) -> tuple[int, dict[str, Any]] | None:
        """Return ``(status_code, response_json)`` if the key was seen."""
        stmt = select(IdempotencyRow).where(
            IdempotencyRow.tenant_id == tenant_id,
            IdempotencyRow.idem_key == key,
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return row.status_code, row.response_json

    async def put(
        self,
        session: AsyncSession,
        tenant_id: str,
        key: str,
        status_code: int,
        response_json: dict[str, Any],
    ) -> None:
        """Store the result of an idempotent request (no commit)."""
        session.add(
            IdempotencyRow(
                tenant_id=tenant_id,
                idem_key=key,
                status_code=status_code,
                response_json=response_json,
                created_at=utcnow(),
            )
        )
        await session.flush()
