"""Unit tests for the fake mandate verifier and scope attenuation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kavach.capabilities.mandate._internal.fake import FakeMandateVerifier, issue_fake_mandate
from kavach.capabilities.mandate.scope import scope_is_strict_subset, scope_is_subset
from kavach.events.schemas import Mandate, MandateConstraint

_KEY = b"test-mandate-key"


def _mandate(**overrides: object) -> Mandate:
    base: dict[str, object] = {
        "mandate_id": "m1",
        "originator_id": "user-1",
        "originator_kind": "human",
        "agent_id": "agent-1",
        "action_scope": ["account.funds.*"],
        "constraints": [MandateConstraint(path="payment_amount.amount", operator="lte", value=100)],
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "nonce": "n1",
    }
    base.update(overrides)
    return Mandate.model_validate(base)


def test_round_trip_verifies() -> None:
    mandate = _mandate()
    token = issue_fake_mandate(mandate, _KEY)
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-1",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
    )
    assert result.verified
    assert result.digest


def test_bad_signature_rejected() -> None:
    token = issue_fake_mandate(_mandate(), b"other-key")
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-1",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
    )
    assert not result.verified


def test_expired_rejected() -> None:
    mandate = _mandate(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    token = issue_fake_mandate(mandate, _KEY)
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-1",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
    )
    assert not result.verified
    assert "expired" in result.reason


def test_wrong_agent_rejected() -> None:
    token = issue_fake_mandate(_mandate(), _KEY)
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="someone-else",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
    )
    assert not result.verified


def test_scope_mismatch_rejected() -> None:
    token = issue_fake_mandate(_mandate(action_scope=["kyc.*"]), _KEY)
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-1",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
    )
    assert not result.verified


def test_revoked_rejected() -> None:
    token = issue_fake_mandate(_mandate(), _KEY)
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-1",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
        revoked_ids=frozenset({"m1"}),
    )
    assert not result.verified
    assert not result.not_revoked


def test_parent_attenuation() -> None:
    parent = _mandate(mandate_id="parent", action_scope=["account.*"])
    child = _mandate(
        mandate_id="child",
        parent_mandate_id="parent",
        action_scope=["account.funds.transfer"],
        constraints=[MandateConstraint(path="payment_amount.amount", operator="lte", value=50)],
    )
    token = issue_fake_mandate(child, _KEY)
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-1",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
        parent=parent,
    )
    assert result.verified
    assert result.chain_ok


def test_broader_child_rejected() -> None:
    parent = _mandate(mandate_id="parent", action_scope=["account.funds.transfer"])
    child = _mandate(
        mandate_id="child",
        parent_mandate_id="parent",
        action_scope=["account.*"],
    )
    token = issue_fake_mandate(child, _KEY)
    result = FakeMandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-1",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
        parent=parent,
    )
    assert not result.chain_ok


@given(
    parent=st.sampled_from(["*", "account.*", "account.funds.*"]),
    child=st.sampled_from(["account.funds.transfer", "account.funds.*", "account.read.balance"]),
)
def test_subset_is_monotonic(parent: str, child: str) -> None:
    covered = scope_is_subset([parent], [child])
    if parent == "*":
        assert covered
    if covered and child != parent:
        assert scope_is_strict_subset([parent], [child])


def test_identical_scope_is_not_strict() -> None:
    assert scope_is_subset(["account.*"], ["account.*"])
    assert not scope_is_strict_subset(["account.*"], ["account.*"])


@pytest.mark.parametrize(
    ("parent", "child", "expected"),
    [
        (["*"], ["account.funds.transfer"], True),
        (["account.*"], ["account.funds.*"], True),
        (["kyc.*"], ["account.funds.transfer"], False),
    ],
)
def test_scope_examples(parent: list[str], child: list[str], expected: bool) -> None:
    assert scope_is_subset(parent, child) is expected
