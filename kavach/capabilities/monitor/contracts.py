"""Monitor capability contracts (ADR-0019)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from kavach.events._base import DomainEvent
from kavach.events.schemas.monitor import AnomalyDetected


class AnomalyDetector(Protocol):
    """Observes one event and may emit bounded anomaly signals."""

    detector_id: str

    def observe(
        self, event: DomainEvent, history: Sequence[DomainEvent]
    ) -> list[AnomalyDetected]: ...
