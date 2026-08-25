"""Storage capability — persistence substrate (ADR-0004, ADR-0008).

Public API: the ORM ``Base`` and tables, engine/session helpers, the
event store, and the idempotency store. Internal implementation lives
under ``_internal/`` and must not be imported from outside this package.
"""

from __future__ import annotations

from kavach.capabilities.storage._internal.engine import (
    create_all,
    drop_all,
    make_engine,
    make_session_factory,
    session_scope,
)
from kavach.capabilities.storage._internal.event_store import EventStore
from kavach.capabilities.storage._internal.idempotency import IdempotencyStore
from kavach.capabilities.storage._internal.models import (
    AgentRegistrationRow,
    Base,
    EventRow,
    IdempotencyRow,
    OutboxRow,
    WebhookSubscriptionRow,
)
from kavach.capabilities.storage._internal.outbox import OutboxStore, WebhookStore
from kavach.capabilities.storage.contracts import (
    SupportsAppend,
    SupportsIdempotency,
    SupportsReplay,
)

__all__ = [
    "AgentRegistrationRow",
    "Base",
    "EventRow",
    "EventStore",
    "IdempotencyRow",
    "IdempotencyStore",
    "OutboxRow",
    "OutboxStore",
    "SupportsAppend",
    "SupportsIdempotency",
    "SupportsReplay",
    "WebhookStore",
    "WebhookSubscriptionRow",
    "create_all",
    "drop_all",
    "make_engine",
    "make_session_factory",
    "session_scope",
]
