"""Substrate event taxonomy and replay registry (ADR-0008, ADR-0010).

Public surface of the events package. Importing this module makes every
concrete event class available and registers it for replay dispatch.
"""

from __future__ import annotations

# Importing the schemas package registers all concrete event classes.
from kavach.events import schemas
from kavach.events._base import DomainEvent, new_event_id, utcnow
from kavach.events.registry import (
    deserialize_event,
    known_events,
    resolve_event,
)

__all__ = [
    "DomainEvent",
    "deserialize_event",
    "known_events",
    "new_event_id",
    "resolve_event",
    "schemas",
    "utcnow",
]
