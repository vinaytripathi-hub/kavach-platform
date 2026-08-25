"""Shared builders for data sufficiency (ADR-0013).

Capabilities use these helpers so they are not reimplementing
band-computation logic. The canonical types and the worst-band
composition live in ``kavach.events.schemas.data_sufficiency``; this
module adds convenience constructors.
"""

from __future__ import annotations

from datetime import datetime

from kavach.events.schemas.data_sufficiency import (
    Band,
    DataSufficiency,
    ModalitySufficiency,
    compose_sufficiency,
    worst_band,
)

__all__ = [
    "cold_start",
    "compose_sufficiency",
    "single_modality",
    "worst_band",
]


def single_modality(
    modality: str,
    *,
    band: Band,
    observations: int,
    earliest: datetime | None = None,
    latest: datetime | None = None,
    reason: str = "",
) -> DataSufficiency:
    """Build a one-modality sufficiency indicator."""
    ms = ModalitySufficiency(
        modality=modality,
        band=band,
        observations=observations,
        earliest=earliest,
        latest=latest,
        reason=reason,
    )
    return compose_sufficiency({modality: ms})


def cold_start(modality: str = "behavioral_baseline") -> DataSufficiency:
    """Sufficiency for an agent with no history in this modality."""
    return single_modality(
        modality,
        band="cold",
        observations=0,
        reason="No prior observations; output is priors-driven.",
    )
