"""Reference-vector tests for the AP2 payment-mandate verifier."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from kavach.capabilities.mandate._internal.ap2_adapter import (
    AP2MandateVerifier,
    issue_ap2_mandate,
)

_KEY = b"ap2-test-key-at-least-thirty-two-bytes"
_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "ap2" / "payment_mandate.json"


def test_fixture_verifies_and_translates_constraints() -> None:
    raw = json.loads(_FIXTURE.read_text())
    token = issue_ap2_mandate(raw, _KEY)
    result = AP2MandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-cs-01",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
    )
    assert result.verified
    assert result.mandate is not None
    paths = {item.path for item in result.mandate.constraints}
    assert "payment_amount.amount" in paths
    assert "payee.id" in paths


def test_checkout_binding_mismatch_rejected() -> None:
    from kavach.capabilities.mandate._internal.tokens import issue_hs256

    claims = json.loads(_FIXTURE.read_text())
    claims["transaction_id"] = "not-the-checkout-hash"
    token = issue_hs256(claims, _KEY)
    result = AP2MandateVerifier(_KEY).verify(
        token,
        expected_agent_id="agent-cs-01",
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
    )
    assert not result.verified
    assert "checkout" in result.reason
