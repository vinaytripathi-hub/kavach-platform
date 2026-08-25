"""Replay dispatch registry for domain events (ADR-0010).

The event log stores ``(event_type, schema_version, payload)`` for every
event. Replay walks the log and reconstructs the concrete event class
via this registry. Versioned classes accumulate here; retired versions
remain importable for historical replay.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kavach.events._base import DomainEvent

_REGISTRY: dict[tuple[str, int], type[DomainEvent]] = {}


def register_event(cls: type[DomainEvent]) -> None:
    """Register a concrete event class by ``(event_type, schema_version)``.

    Called automatically from ``DomainEvent.__init_subclass__``. Raises
    if a different class is already registered for the same key, which
    catches accidental duplicate event-type/version declarations.
    """
    key = (cls.event_type, cls.schema_version)
    existing = _REGISTRY.get(key)
    if existing is not None and existing is not cls:
        raise ValueError(
            f"Duplicate event registration for {key}: {existing.__name__} and {cls.__name__}"
        )
    _REGISTRY[key] = cls


def resolve_event(event_type: str, schema_version: int) -> type[DomainEvent]:
    """Return the event class for a stored ``(event_type, schema_version)``."""
    try:
        return _REGISTRY[(event_type, schema_version)]
    except KeyError as exc:
        raise KeyError(
            f"No event registered for ({event_type!r}, {schema_version}). "
            f"Known: {sorted(_REGISTRY.keys())}"
        ) from exc


def deserialize_event(
    event_type: str, schema_version: int, payload: dict[str, object]
) -> DomainEvent:
    """Reconstruct a domain event from its stored payload."""
    cls = resolve_event(event_type, schema_version)
    return cls.model_validate(payload)


def known_events() -> list[tuple[str, int]]:
    """All registered ``(event_type, schema_version)`` pairs."""
    return sorted(_REGISTRY.keys())
