"""Audit chain writer: appends one chained record per event (ADR-0012).

Implements the ``ProjectionHandler`` shape (``consumes`` + ``handle``) so
the event bus runs it within the same transaction as the event append.
This makes "every interaction generates a cryptographically signed audit
trail" a transactional invariant, not a best-effort afterthought.

It consumes every registered event type. In the prototype the per-tenant
chain is advanced sequentially; concurrent writers would need a row lock
on the chain head, which is a production hardening item.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.audit._internal.chain import link_message, payload_digest
from kavach.capabilities.audit._internal.models import AuditRecordRow
from kavach.capabilities.audit.signer import HMACSigner, Signer
from kavach.events._base import DomainEvent
from kavach.events.registry import known_events


class AuditChainWriter:
    """Maintains the per-tenant HMAC hash chain over all events."""

    def __init__(self, signer: Signer | bytes) -> None:
        self._signer: Signer = signer if not isinstance(signer, bytes) else HMACSigner(signer)

    @property
    def consumes(self) -> frozenset[str]:
        return frozenset(event_type for event_type, _ in known_events())

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        head = await self._chain_head(session, event.tenant_id)
        if head is None:
            prev_hash: str | None = None
            position = 0
        else:
            prev_hash = head.this_hash
            position = head.position + 1

        digest = payload_digest(event.payload())
        message = link_message(prev_hash, position, event.event_id, digest)
        this_hash = self._signer.sign(message.encode("utf-8")).hex()
        session.add(
            AuditRecordRow(
                tenant_id=event.tenant_id,
                position=position,
                event_id=event.event_id,
                event_type=event.event_type,
                agent_id=event.aggregate_id(),
                occurred_at=event.occurred_at,
                prev_hash=prev_hash,
                this_hash=this_hash,
                payload_digest=digest,
            )
        )
        await session.flush()

    async def _chain_head(self, session: AsyncSession, tenant_id: str) -> AuditRecordRow | None:
        stmt = (
            select(AuditRecordRow)
            .where(AuditRecordRow.tenant_id == tenant_id)
            .order_by(AuditRecordRow.position.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()
