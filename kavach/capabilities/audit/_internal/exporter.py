"""Evidence-pack exporter and verifier (ADR-0012; EU AI Act Art. 12/13).

Produces a time-bounded, agent-scoped slice of the audit chain with a
detached signature manifest. The exported pack is independently
verifiable: a holder of the signing key can recompute every ``this_hash``
from the stored link material and check the signature over the chain head.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.audit._internal.chain import (
    compute_hash,
    key_id,
    sign,
)
from kavach.capabilities.audit._internal.models import AuditRecordRow
from kavach.events import utcnow


class AuditRecord(BaseModel):
    """One record in an exported evidence pack."""

    model_config = ConfigDict(extra="forbid")

    position: int
    event_id: str
    event_type: str
    occurred_at: datetime
    prev_hash: str | None
    this_hash: str
    payload_digest: str


class SignatureManifest(BaseModel):
    """Detached signature over an exported chain head."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str = "HMAC-SHA256"
    key_id: str
    chain_head: str
    signature: str
    generated_at: datetime = Field(default_factory=utcnow)


class AuditExport(BaseModel):
    """A signed evidence pack."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    agent_id: str
    record_count: int
    records: list[AuditRecord]
    signature_manifest: SignatureManifest | None = None


class AuditExporter:
    """Builds and verifies signed evidence packs from the audit chain."""

    def __init__(self, key: bytes) -> None:
        self._key = key

    async def export(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        agent_id: str,
        frm: datetime,
        to: datetime,
    ) -> AuditExport:
        stmt = (
            select(AuditRecordRow)
            .where(
                AuditRecordRow.tenant_id == tenant_id,
                AuditRecordRow.agent_id == agent_id,
                AuditRecordRow.occurred_at >= frm,
                AuditRecordRow.occurred_at <= to,
            )
            .order_by(AuditRecordRow.position)
        )
        rows = (await session.execute(stmt)).scalars().all()
        records = [
            AuditRecord(
                position=r.position,
                event_id=r.event_id,
                event_type=r.event_type,
                occurred_at=r.occurred_at,
                prev_hash=r.prev_hash,
                this_hash=r.this_hash,
                payload_digest=r.payload_digest,
            )
            for r in rows
        ]
        manifest: SignatureManifest | None = None
        if records:
            chain_head = records[-1].this_hash
            manifest = SignatureManifest(
                key_id=key_id(self._key),
                chain_head=chain_head,
                signature=sign(self._key, chain_head),
            )
        return AuditExport(
            tenant_id=tenant_id,
            agent_id=agent_id,
            record_count=len(records),
            records=records,
            signature_manifest=manifest,
        )

    def verify(self, export: AuditExport) -> bool:
        """Recompute the chain and check the signature. True iff intact."""
        if not export.records:
            return export.signature_manifest is None
        for rec in export.records:
            expected = compute_hash(
                self._key,
                rec.prev_hash,
                rec.position,
                rec.event_id,
                rec.payload_digest,
            )
            if expected != rec.this_hash:
                return False
        manifest = export.signature_manifest
        if manifest is None:
            return False
        if manifest.chain_head != export.records[-1].this_hash:
            return False
        return sign(self._key, manifest.chain_head) == manifest.signature
