"""Events consumed by the audit capability.

The audit capability consumes every event (to chain it) and emits
``EvidenceRecorded`` when evidence is explicitly captured. The
``EvidenceRecorded`` schema is defined centrally in
``kavach.events.schemas.audit`` per the ADR-0010 versioning discipline;
it is re-exported here for discoverability per ADR-0007.
"""

from __future__ import annotations

from kavach.events.schemas.audit import EvidenceRecorded

__all__ = ["EvidenceRecorded"]
