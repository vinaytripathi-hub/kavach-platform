"""Base classes and helpers for domain events.

Per ADR-0008, domain events are the substrate's primary output. Per
ADR-0010, every event class declares a stable ``event_type`` identifier
and an integer ``schema_version``; the pair ``(event_type, schema_version)``
selects the class for replay.

``DomainEvent`` carries a small common envelope (event id, tenant,
aggregate id, occurrence time). Domain-specific fields are declared by
subclasses. The envelope plus the domain fields together form the
persisted payload.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    """Timezone-aware current time in UTC.

    Centralised so every event uses tz-aware timestamps (ruff DTZ).
    """
    return datetime.now(UTC)


def new_event_id() -> str:
    """Generate a fresh event identifier."""
    return str(uuid.uuid4())


class DomainEvent(BaseModel):
    """Base class for all substrate domain events.

    Subclasses MUST set the ``event_type`` and ``schema_version`` class
    variables. Subclasses are automatically registered for replay
    dispatch (see ``kavach.events.registry``).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Declared by every concrete subclass (ADR-0010).
    event_type: ClassVar[str] = ""
    schema_version: ClassVar[int] = 0

    # Common envelope.
    event_id: str = Field(default_factory=new_event_id)
    tenant_id: str
    occurred_at: datetime = Field(default_factory=utcnow)

    def __init_subclass__(cls, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init_subclass__(**kwargs)
        # Concrete event classes (those that set a non-empty event_type)
        # register themselves for replay dispatch. Intermediate abstract
        # bases that leave event_type empty are skipped.
        if cls.__dict__.get("event_type"):
            from kavach.events.registry import register_event

            register_event(cls)

    def aggregate_id(self) -> str | None:
        """Identifier this event is grouped by for timelines/indexing.

        Most events relate to an agent; subclasses with an ``agent_id``
        field expose it here. Override where the grouping differs.
        """
        return getattr(self, "agent_id", None)

    def payload(self) -> dict[str, Any]:
        """Domain payload for persistence (JSON-serialisable).

        Includes the full model dump (envelope + domain fields) so that
        replay can reconstruct the event via ``model_validate``.
        """
        return self.model_dump(mode="json")
