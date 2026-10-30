"""Mandate not-before enforcement (ADR-0020)."""

from __future__ import annotations

from datetime import timedelta

from kavach.capabilities.mandate._internal.fake import FakeMandateVerifier, issue_fake_mandate
from kavach.events import utcnow
from kavach.events.schemas import Mandate

_KEY = b"mandate-test-key-32-bytes-minimum!!"


def _mandate(*, not_before_delta: timedelta | None) -> Mandate:
    now = utcnow()
    return Mandate(
        mandate_id="m-nbf",
        originator_id="customer-1",
        originator_kind="human",
        agent_id="agent-1",
        action_scope=["account.funds.transfer"],
        expires_at=now + timedelta(hours=1),
        not_before=None if not_before_delta is None else now + not_before_delta,
        nonce="n",
    )


def test_mandate_not_before_fails_closed() -> None:
    mandate = _mandate(not_before_delta=timedelta(minutes=10))
    token = issue_fake_mandate(mandate, _KEY)
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-1",
        expected_action="account.funds.transfer",
        now=utcnow(),
    )
    assert not result.verified
    assert result.reason == "Mandate not yet valid."


def test_mandate_inside_window_verifies() -> None:
    mandate = _mandate(not_before_delta=timedelta(minutes=-1))
    token = issue_fake_mandate(mandate, _KEY)
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-1",
        expected_action="account.funds.transfer",
        now=utcnow(),
    )
    assert result.verified
