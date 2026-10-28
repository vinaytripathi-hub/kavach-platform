"""Audit capability — tamper-evident evidence chain (ADR-0012, ADR-0011).

Public API: the chain writer (a projection handler the bus runs per
event), the evidence-pack exporter/verifier, the export DTOs, and the
``AuditRecordRow`` table.
"""

from __future__ import annotations

from kavach.capabilities.audit._internal.exporter import (
    AuditExport,
    AuditExporter,
    AuditRecord,
    SignatureManifest,
)
from kavach.capabilities.audit._internal.models import AuditRecordRow
from kavach.capabilities.audit._internal.writer import AuditChainWriter
from kavach.capabilities.audit.signer import HMACSigner, KmsSignerStub, Signer, make_signer

__all__ = [
    "AuditChainWriter",
    "AuditExport",
    "AuditExporter",
    "AuditRecord",
    "AuditRecordRow",
    "HMACSigner",
    "KmsSignerStub",
    "SignatureManifest",
    "Signer",
    "make_signer",
]
