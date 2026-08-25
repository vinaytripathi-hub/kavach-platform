"""Tests for the offline fake credential verifier."""

from __future__ import annotations

from kavach.capabilities.sdk_bridge import FakeCredentialVerifier, make_verifier


def test_valid_token_verifies_with_wildcard_scope() -> None:
    v = FakeCredentialVerifier()
    result = v.verify("agent:agent-1", expected_audience="kavach")
    assert result.verified
    assert result.agent_id == "agent-1"
    assert result.authorizes("anything.at.all")


def test_scoped_token_limits_authorization() -> None:
    v = FakeCredentialVerifier()
    result = v.verify("agent:agent-1:account.funds", expected_audience="kavach")
    assert result.authorizes("account.funds.transfer")
    assert not result.authorizes("trading.order.place")


def test_invalid_token_rejected() -> None:
    v = FakeCredentialVerifier()
    result = v.verify("invalid-token", expected_audience="kavach")
    assert not result.verified
    assert not result.authorizes("kyc.document.verify")


def test_make_verifier_default_is_fake() -> None:
    v = make_verifier()
    result = v.verify("agent:x", expected_audience="kavach")
    assert result.verified
