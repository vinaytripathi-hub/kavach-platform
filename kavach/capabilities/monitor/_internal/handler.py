"""Bus-driven monitor worker (ADR-0019)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from kavach.capabilities.monitor.contracts import AnomalyDetector
from kavach.capabilities.storage import EventStore
from kavach.composition.bus import EventBus
from kavach.events._base import DomainEvent


class MonitorHandler:
    """Runs detectors inside the publishing transaction and emits anomalies."""

    def __init__(
        self,
        store: EventStore,
        bus: EventBus,
        detectors: list[AnomalyDetector],
    ) -> None:
        self._store = store
        self._bus = bus
        self._detectors = detectors

    @property
    def consumes(self) -> frozenset[str]:
        return frozenset({"DecisionEmitted"})

    async def handle(self, session: AsyncSession, event: DomainEvent) -> None:
        history = [
            item
            for item in await self._store.read_all(session)
            if item.aggregate_id() == event.aggregate_id()
        ]
        for detector in self._detectors:
            for anomaly in detector.observe(event, history):
                await self._bus.publish(session, anomaly)
