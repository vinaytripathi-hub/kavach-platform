"""Outbound event delivery channels (ADR-0008 outbox, pluggable sinks)."""

from __future__ import annotations

from typing import Protocol

from kavach.events._base import DomainEvent


class EgressChannel(Protocol):
    """Delivers one domain event to a partner system."""

    name: str

    async def send(self, event: DomainEvent) -> None: ...


class WebhookEgress:
    """Marks the event for the existing transactional outbox worker."""

    name = "webhook"

    async def send(self, event: DomainEvent) -> None:
        del event  # The event bus already writes the outbox row.


__all__ = ["EgressChannel", "WebhookEgress"]
