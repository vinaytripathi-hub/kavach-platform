"""Egress and notification channel contracts."""

from __future__ import annotations

import pytest

from kavach.capabilities.egress import WebhookEgress
from kavach.capabilities.notify import NoopNotifier
from kavach.events.schemas import ActionExecuted


@pytest.mark.asyncio
async def test_channels_accept_a_call() -> None:
    event = ActionExecuted(tenant_id="t", agent_id="a", session_id="s", action_type="kyc.x")
    await WebhookEgress().send(event)
    await NoopNotifier().notify(decision_id="d", reason="r", role="supervisor")
