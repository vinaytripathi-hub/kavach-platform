"""Data sufficiency primitives (ADR-0013).

Every substrate output that depends on accumulated data carries a
``DataSufficiency`` indicator with a categorical band and per-modality
breakdown. The conservative default composition is worst-band-wins.
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

Band = Literal["cold", "thin", "warm", "warm_stale"]

# Total order from least to most confident, used by worst-band composition.
# warm_stale ranks above thin (more history) but below warm (stale recency).
_BAND_RANK: dict[Band, int] = {"cold": 0, "thin": 1, "warm_stale": 2, "warm": 3}


class ModalitySufficiency(BaseModel):
    """Sufficiency for one input modality."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    modality: str
    band: Band
    observations: int = Field(ge=0)
    earliest: datetime | None = None
    latest: datetime | None = None
    reason: str = ""


class DataSufficiency(BaseModel):
    """Indicator of how much data underlies an output."""

    model_config = ConfigDict(extra="forbid")
    schema_version: ClassVar[int] = 1

    band: Band
    modalities: dict[str, ModalitySufficiency] = Field(default_factory=dict)
    summary: str = ""


def worst_band(bands: list[Band]) -> Band:
    """Return the least-confident band (worst-band-wins, ADR-0013)."""
    if not bands:
        return "cold"
    return min(bands, key=lambda b: _BAND_RANK[b])


def compose_sufficiency(
    modalities: dict[str, ModalitySufficiency],
    *,
    summary: str | None = None,
) -> DataSufficiency:
    """Compose per-modality sufficiency into an overall indicator.

    Uses the conservative worst-band-wins default (ADR-0013). Capability
    code may build a ``DataSufficiency`` directly when it needs to
    override this composition.
    """
    overall = worst_band([m.band for m in modalities.values()])
    if summary is None:
        summary = f"Overall band {overall} from {len(modalities)} modalities."
    return DataSufficiency(band=overall, modalities=modalities, summary=summary)
