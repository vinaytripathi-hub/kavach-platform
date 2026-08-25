"""Agent action events."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field

from kavach.events._base import DomainEvent


class ActionExecuted(DomainEvent):
    """Emitted when an agent executes an action (ingress record)."""

    event_type: ClassVar[str] = "ActionExecuted"
    schema_version: ClassVar[int] = 1

    agent_id: str
    session_id: str
    action_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    context: str | None = None


__all__ = ["ActionExecuted"]
