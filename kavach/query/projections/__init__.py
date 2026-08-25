"""Read-side projections over the event stream (ADR-0009).

Projections are top-level substrate concerns (not inside any capability).
Each projection declares the event types it consumes, maintains its
projection table(s), and can rebuild itself from the event log.
"""

from __future__ import annotations
