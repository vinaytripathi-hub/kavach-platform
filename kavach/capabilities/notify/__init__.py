"""Operator notification channels for step-up (ADR-0012)."""

from __future__ import annotations

from typing import Protocol


class NotificationChannel(Protocol):
    """Notifies an operator that a step-up is waiting."""

    name: str

    async def notify(self, *, decision_id: str, reason: str, role: str) -> None: ...


class NoopNotifier:
    """Default channel. Records nothing outside the audit chain."""

    name = "noop"

    async def notify(self, *, decision_id: str, reason: str, role: str) -> None:
        del decision_id, reason, role


__all__ = ["NoopNotifier", "NotificationChannel"]
