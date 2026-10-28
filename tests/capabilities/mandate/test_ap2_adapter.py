"""Conformance: a mandate minted by Google's AP2 SDK verifies in Kavach.

Skipped when the optional ``ap2`` extra is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("ap2")
pytest.importorskip("jwcrypto")

import json
import time
from datetime import UTC, datetime, timedelta

from ap2.sdk.generated.open_payment_mandate import (
    AllowedPayees,
    AmountRange,
    Budget,
    OpenPaymentMandate,
)
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK

from kavach.capabilities.mandate._internal.ap2_adapter import AP2MandateVerifier
from kavach.capabilities.mandate._internal.tokens import mandate_digest
from kavach.composition import SubstrateConfig, build_substrate
from kavach.events.schemas import Mandate, MandateConstraint
from kavach.usecases.customer_service import CustomerServiceRules

_AGENT = "agent-cs-01"


def _jwk(kid: str) -> JWK:
    raw = json.loads(JWK.from_pyca(ec.generate_private_key(ec.SECP256R1())).export())
    raw["kid"] = kid
    return JWK(**raw)


def _chain(issuer: JWK, holder: JWK) -> str:
    now = int(time.time())
    holder_pub = json.loads(holder.export_public())
    client = MandateClient()
    open_token = client.create(
        payloads=[
            OpenPaymentMandate(
                constraints=[
                    AmountRange(currency="INR", min=0, max=500000),
                    AllowedPayees(allowed=[Merchant(id="merchant-1", name="Merchant")]),
                    Budget(currency="INR", max=500000),
                ],
                cnf={"jwk": holder_pub},
                risk_data={"kavach_agent_id": _AGENT, "kavach_originator_id": "customer-1"},
                iat=now,
                exp=now + 3600,
            )
        ],
        issuer_key=issuer,
    )
    presented: str = client.present(
        holder_key=holder,
        mandate_token=open_token,
        payloads=[
            PaymentMandate(
                transaction_id="checkout-hash-demo",
                payee=Merchant(id="merchant-1", name="Merchant"),
                payment_amount=Amount(amount=250000, currency="INR"),
                payment_instrument=PaymentInstrument(id="card-1", type="card", description="Demo"),
                iat=now,
                exp=now + 3600,
            )
        ],
        nonce="checkout-hash-demo",
        aud="kavach",
    )
    return presented


def test_sdk_chain_verifies_and_translates_constraints() -> None:
    issuer = _jwk("issuer-1")
    holder = _jwk("agent-1")
    token = _chain(issuer, holder)
    result = AP2MandateVerifier(b"unused", issuer_jwk=issuer).verify(
        token,
        expected_agent_id=_AGENT,
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
        expected_aud="kavach",
        expected_nonce="checkout-hash-demo",
    )
    assert result.verified, result.reason
    assert result.mandate is not None
    paths = {item.path: item.value for item in result.mandate.constraints}
    assert paths["payment_amount.amount"] == 500000
    assert "merchant-1" in paths["payee.id"]
    assert paths["budget"] == 500000
    assert result.mandate.agent_id == _AGENT


def test_issue_chain_round_trips_the_same_mandate() -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    mandate = Mandate(
        mandate_id="m-ap2-1",
        originator_id="customer-1",
        originator_kind="human",
        agent_id=_AGENT,
        action_scope=["account.funds.transfer"],
        constraints=[
            MandateConstraint(path="payment_amount.amount", operator="lte", value=500000),
            MandateConstraint(path="payee.id", operator="in", value=["merchant-1"]),
            MandateConstraint(path="budget", operator="lte", value=500000),
            MandateConstraint(path="agent_recurrence.max_occurrences", operator="lte", value=4),
            MandateConstraint(path="payment_instrument.id", operator="in", value=["card-1"]),
        ],
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        nonce="checkout-hash-demo",
    )
    verifier = AP2MandateVerifier(b"k" * 32)
    token = verifier.issue_chain(mandate)
    assert "~~" in token
    result = verifier.verify(
        token,
        expected_agent_id=_AGENT,
        expected_action="account.funds.transfer",
        now=now,
    )
    assert result.verified, result.reason
    assert result.mandate is not None
    assert mandate_digest(result.mandate) == mandate_digest(mandate)
    restarted = AP2MandateVerifier(b"k" * 32).verify(
        token,
        expected_agent_id=_AGENT,
        expected_action="account.funds.transfer",
        now=now,
    )
    assert restarted.verified, restarted.reason


def test_tampered_sdk_chain_is_rejected() -> None:
    issuer = _jwk("issuer-1")
    holder = _jwk("agent-1")
    token = _chain(issuer, holder)
    other = _jwk("issuer-2")
    result = AP2MandateVerifier(b"unused", issuer_jwk=other).verify(
        token,
        expected_agent_id=_AGENT,
        expected_action="account.funds.transfer",
        now=datetime.now(UTC),
        expected_aud="kavach",
        expected_nonce="checkout-hash-demo",
    )
    assert not result.verified


async def test_ap2_mode_issues_a_chain_the_decision_can_present() -> None:
    substrate = build_substrate(
        SubstrateConfig(
            database_url="sqlite+aiosqlite:///:memory:",
            audit_hmac_key="unit-test-key",
            mandate_verifier_mode="ap2",
        ),
        rule_providers=[CustomerServiceRules()],
    )
    await substrate.create_schema()
    now = datetime.now(UTC).replace(microsecond=0)
    mandate = Mandate(
        mandate_id="m-flow-ap2",
        originator_id="customer-1",
        originator_kind="human",
        agent_id="agent-1",
        action_scope=["account.funds.transfer"],
        constraints=[MandateConstraint(path="payment_amount.amount", operator="lte", value=500000)],
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        nonce="checkout-hash-demo",
    )
    issued = await substrate.service.issue_mandate(tenant_id="t1", mandate=mandate)
    stored = await substrate.service.get_mandate(tenant_id="t1", mandate_id="m-flow-ap2")
    assert stored is not None
    assert "~~" in stored.token
    stepped = await substrate.service.decide(
        tenant_id="t1",
        agent_id="agent-1",
        session_id="s",
        action_type="account.funds.transfer",
        parameters={"amount": 250000},
        use_case="customer_service",
        mandate_token=stored.token,
    )
    assert stepped.outcome == "step_up"
    assert stepped.decision_event.evidence.attributes["mandate_digest"] == issued.mandate_digest
    await substrate.dispose()
