"""AP2 payment-mandate verifier (ADR-0018 addendum).

A token containing ``~`` is an SD-JWT chain minted by Google's AP2 SDK
(optional ``ap2`` extra). The verifier checks the issuer signature, the
holder key binding, and the closed mandate's ``transaction_id`` against
the presentation nonce, then restores the substrate ``Mandate``.

Any other token is the offline HS256 stand-in: claims follow the AP2
payment-mandate shape, and ``transaction_id`` must be the SHA-256
(base64url, no padding) of ``checkout_jwt`` when that field is present.
"""

from __future__ import annotations

import base64
import hashlib
import json
import warnings
from datetime import UTC, datetime
from typing import Any

from kavach.capabilities.mandate._internal.tokens import decode_hs256, issue_hs256, mandate_digest
from kavach.capabilities.mandate.contracts import VerifiedMandate
from kavach.capabilities.mandate.scope import scope_covers_action
from kavach.events.schemas.mandate import Mandate, MandateConstraint

_PAYMENT_TYPES = frozenset({"mandate.payment.1", "mandate.payment.open.1"})
_KAVACH_AUD = "kavach"
_P256_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_CURRENCY = "INR"
_MIN_JWT_SEGMENTS = 2


def _b64_sha256(material: str) -> str:
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _constraints_from_ap2(claims: dict[str, Any]) -> list[MandateConstraint]:
    out: list[MandateConstraint] = []
    amount = claims.get("payment_amount")
    if isinstance(amount, dict) and "amount" in amount:
        out.append(
            MandateConstraint(path="payment_amount.amount", operator="lte", value=amount["amount"])
        )
    for raw in claims.get("constraints") or []:
        if not isinstance(raw, dict):
            continue
        kind = raw.get("type")
        if kind == "amount_range" and "max" in raw:
            out.append(
                MandateConstraint(path="payment_amount.amount", operator="lte", value=raw["max"])
            )
        elif kind == "allowed_payee":
            out.append(
                MandateConstraint(path="payee.id", operator="in", value=list(raw.get("payees", [])))
            )
        elif kind == "allowed_payment_instrument":
            out.append(
                MandateConstraint(
                    path="payment_instrument.id",
                    operator="in",
                    value=list(raw.get("instruments", [])),
                )
            )
    return out


def issue_ap2_mandate(claims: dict[str, Any], key: bytes) -> str:
    """Sign an AP2-shaped claim set for tests and the demo harness."""
    body = dict(claims)
    checkout = body.get("checkout_jwt")
    if isinstance(checkout, str) and "transaction_id" not in body:
        body["transaction_id"] = _b64_sha256(checkout)
    body.setdefault("vct", "mandate.payment.open.1")
    return issue_hs256(body, key)


def mandate_from_ap2(claims: dict[str, Any]) -> Mandate:
    """Map AP2 payment-mandate claims onto the substrate ``Mandate``."""
    issued = datetime.fromtimestamp(int(claims.get("iat", 0)), tz=UTC)
    expires = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    return Mandate(
        mandate_id=str(claims["mandate_id"]),
        originator_id=str(claims.get("originator_id", "ap2-user")),
        originator_kind="human",
        agent_id=str(claims["agent_id"]),
        action_scope=list(claims.get("action_scope") or ["account.funds.transfer"]),
        constraints=_constraints_from_ap2(claims),
        issued_at=issued,
        expires_at=expires,
        parent_mandate_id=None,
        nonce=str(claims.get("nonce", claims["mandate_id"])),
    )


class AP2MandateVerifier:
    """Verifies an AP2 payment mandate.

    A token containing ``~`` is an SD-JWT chain from Google's AP2 SDK and is
    verified with ``MandateClient``. Any other token is the offline HS256
    stand-in used when the SDK is not installed.
    """

    def __init__(self, key: bytes, issuer_jwk: object | None = None) -> None:
        self._key = key
        self._issuer_jwk = issuer_jwk
        self._holder_jwk: object | None = None

    def verify(  # noqa: PLR0911
        self,
        token: str,
        *,
        expected_agent_id: str,
        expected_action: str,
        now: datetime,
        revoked_ids: frozenset[str] = frozenset(),
        parent: Mandate | None = None,
        expected_aud: str | None = None,
        expected_nonce: str | None = None,
    ) -> VerifiedMandate:
        del parent  # AP2 open mandates carry constraints directly.
        if "~" in token:
            return self._verify_sd_jwt(
                token,
                expected_agent_id=expected_agent_id,
                expected_action=expected_action,
                now=now,
                revoked_ids=revoked_ids,
                expected_aud=expected_aud,
                expected_nonce=expected_nonce,
            )
        claims = decode_hs256(token, self._key)
        if claims is None:
            return VerifiedMandate(verified=False, reason="AP2 mandate signature invalid.")
        if claims.get("vct") not in _PAYMENT_TYPES:
            return VerifiedMandate(verified=False, reason="Not an AP2 payment mandate.")
        checkout = claims.get("checkout_jwt")
        txn = claims.get("transaction_id")
        if isinstance(checkout, str) and txn != _b64_sha256(checkout):
            return VerifiedMandate(
                verified=False, reason="Payment mandate is not bound to the checkout."
            )
        try:
            mandate = mandate_from_ap2(claims)
        except (KeyError, TypeError, ValueError) as exc:
            return VerifiedMandate(verified=False, reason=f"AP2 mandate incomplete: {exc}")
        digest = mandate_digest(mandate)
        if mandate.agent_id != expected_agent_id:
            return VerifiedMandate(
                mandate=mandate, verified=False, reason="Mandate agent mismatch.", digest=digest
            )
        if mandate.expires_at <= now:
            return VerifiedMandate(
                mandate=mandate, verified=False, reason="Mandate expired.", digest=digest
            )
        if not scope_covers_action(mandate.action_scope, expected_action):
            return VerifiedMandate(
                mandate=mandate,
                verified=False,
                reason="Mandate scope does not cover the action.",
                digest=digest,
            )
        not_revoked = mandate.mandate_id not in revoked_ids
        return VerifiedMandate(
            mandate=mandate,
            verified=not_revoked,
            reason="AP2 mandate verified." if not_revoked else "Mandate revoked.",
            chain_ok=True,
            not_revoked=not_revoked,
            digest=digest,
        )

    def issue_chain(self, mandate: Mandate) -> str:
        """Mint an SD-JWT payment chain this verifier will accept.

        Raises:
            ImportError: The optional ``ap2`` extra is not installed.
        """
        try:
            from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
            from ap2.sdk.generated.payment_mandate import PaymentMandate
            from ap2.sdk.generated.types.amount import Amount
            from ap2.sdk.generated.types.merchant import Merchant
            from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
            from ap2.sdk.mandate import MandateClient
        except ImportError as exc:
            raise ImportError("AP2 SDK is not installed.") from exc
        issuer, holder = self._signing_keys()
        holder_pub = json.loads(holder.export_public())
        issued = int(mandate.issued_at.timestamp())
        expires = int(mandate.expires_at.timestamp())
        constraints, presented, payee_id, instrument_id = _open_constraints(mandate)
        client = MandateClient()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            open_token = client.create(
                payloads=[
                    OpenPaymentMandate(
                        constraints=constraints,
                        cnf={"jwk": holder_pub},
                        risk_data={
                            "kavach_agent_id": mandate.agent_id,
                            "kavach_originator_id": mandate.originator_id,
                            "kavach_action_scope": list(mandate.action_scope),
                            "kavach_mandate": mandate.model_dump(mode="json"),
                        },
                        iat=issued,
                        exp=expires,
                    )
                ],
                issuer_key=issuer,
            )
            return str(
                client.present(
                    holder_key=holder,
                    mandate_token=open_token,
                    payloads=[
                        PaymentMandate(
                            transaction_id=mandate.nonce,
                            payee=Merchant(id=payee_id, name=payee_id),
                            payment_amount=Amount(amount=presented, currency=_CURRENCY),
                            payment_instrument=PaymentInstrument(
                                id=instrument_id, type="card", description=instrument_id
                            ),
                            iat=issued,
                            exp=expires,
                        )
                    ],
                    nonce=mandate.nonce,
                    aud=_KAVACH_AUD,
                )
            )

    def _signing_keys(self) -> tuple[Any, Any]:
        if self._issuer_jwk is None:
            self._issuer_jwk = _p256_jwk(b"kavach-ap2-issuer:" + self._key, "kavach-ap2-issuer")
        if self._holder_jwk is None:
            self._holder_jwk = _p256_jwk(b"kavach-ap2-holder:" + self._key, "kavach-ap2-holder")
        return self._issuer_jwk, self._holder_jwk

    def _verify_sd_jwt(  # noqa: PLR0911
        self,
        token: str,
        *,
        expected_agent_id: str,
        expected_action: str,
        now: datetime,
        revoked_ids: frozenset[str],
        expected_aud: str | None,
        expected_nonce: str | None,
    ) -> VerifiedMandate:
        try:
            self._signing_keys()
            from ap2.sdk.constraints import MandateContext
            from ap2.sdk.mandate import MandateClient
            from ap2.sdk.payment_mandate_chain import PaymentMandateChain
        except ImportError:
            return VerifiedMandate(verified=False, reason="AP2 SDK is not installed.")
        audience = expected_aud or _KAVACH_AUD
        nonce = expected_nonce or _kb_claim(token, "nonce")
        client = MandateClient()
        try:
            payloads = client.verify(
                token=token,
                key_or_provider=lambda _parsed: self._issuer_jwk,
                expected_aud=audience,
                expected_nonce=nonce,
            )
            chain = PaymentMandateChain.parse(payloads)
            violations = chain.verify(
                expected_transaction_id=nonce,
                mandate_context=MandateContext(),
            )
        except Exception as exc:  # untrusted tokens fail closed
            return VerifiedMandate(verified=False, reason=f"AP2 mandate signature invalid: {exc}")
        if violations:
            return VerifiedMandate(verified=False, reason="; ".join(violations))
        mandate = _mandate_from_chain(chain)
        digest = mandate_digest(mandate)
        if mandate.agent_id != expected_agent_id:
            return VerifiedMandate(
                mandate=mandate, verified=False, reason="Mandate agent mismatch.", digest=digest
            )
        if mandate.expires_at <= now:
            return VerifiedMandate(
                mandate=mandate, verified=False, reason="Mandate expired.", digest=digest
            )
        if not scope_covers_action(mandate.action_scope, expected_action):
            return VerifiedMandate(
                mandate=mandate,
                verified=False,
                reason="Mandate scope does not cover the action.",
                digest=digest,
            )
        not_revoked = mandate.mandate_id not in revoked_ids
        return VerifiedMandate(
            mandate=mandate,
            verified=not_revoked,
            reason="AP2 mandate verified." if not_revoked else "Mandate revoked.",
            chain_ok=True,
            not_revoked=not_revoked,
            digest=digest,
        )


def _mandate_from_chain(chain: object) -> Mandate:
    """Translate a verified AP2 payment chain into a substrate mandate."""
    open_mandate = chain.open_mandate  # type: ignore[attr-defined]
    closed = chain.closed_mandate  # type: ignore[attr-defined]
    risk = open_mandate.risk_data or {}
    embedded = risk.get("kavach_mandate") if isinstance(risk, dict) else None
    if isinstance(embedded, dict):
        return Mandate.model_validate(embedded)
    issued = datetime.fromtimestamp(int(open_mandate.iat or 0), tz=UTC)
    expires = datetime.fromtimestamp(int(open_mandate.exp or 0), tz=UTC)
    return Mandate(
        mandate_id=str(closed.transaction_id),
        originator_id=str(risk.get("kavach_originator_id", "ap2-user")),
        originator_kind="human",
        agent_id=str(risk.get("kavach_agent_id", "")),
        action_scope=list(risk.get("kavach_action_scope") or ["account.funds.transfer"]),
        constraints=_constraints_from_models(open_mandate.constraints),
        issued_at=issued,
        expires_at=expires,
        nonce=str(closed.transaction_id),
    )


def _p256_jwk(label: bytes, kid: str) -> object:
    """Deterministic P-256 key from ``label`` so restarts keep verifying."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from jwcrypto.jwk import JWK

    seed = hashlib.sha256(label).digest()
    scalar = int.from_bytes(seed, "big") % (_P256_ORDER - 1) + 1
    private = ec.derive_private_key(scalar, ec.SECP256R1())
    raw = json.loads(JWK.from_pyca(private).export())
    raw["kid"] = kid
    return JWK(**raw)


def _kb_claim(token: str, field: str) -> str | None:
    """Read one string claim from the trailing key-binding JWT."""
    kb = token.split("~~")[-1].rsplit("~", 1)[-1]
    parts = kb.split(".")
    if len(parts) < _MIN_JWT_SEGMENTS or not parts[1]:
        return None
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError):
        return None
    value = claims.get(field) if isinstance(claims, dict) else None
    return value if isinstance(value, str) else None


def _open_constraints(mandate: Mandate) -> tuple[list[Any], int, str, str]:
    """AP2 open-mandate constraints plus a presentation that satisfies them."""
    from ap2.sdk.constraints import AgentRecurrence, Frequency
    from ap2.sdk.generated.open_payment_mandate import (
        AllowedPayees,
        AllowedPaymentInstruments,
        AmountRange,
        Budget,
    )
    from ap2.sdk.generated.types.merchant import Merchant
    from ap2.sdk.generated.types.payment_instrument import PaymentInstrument

    amount_max = 0
    payees: list[str] = []
    instruments: list[str] = []
    budget_max: int | None = None
    recurrence: int | None = None
    for bound in mandate.constraints:
        if bound.path == "payment_amount.amount" and isinstance(bound.value, int):
            amount_max = bound.value
        elif bound.path == "payee.id" and isinstance(bound.value, list):
            payees = [str(item) for item in bound.value]
        elif bound.path == "payment_instrument.id" and isinstance(bound.value, list):
            instruments = [str(item) for item in bound.value]
        elif bound.path == "budget" and isinstance(bound.value, int):
            budget_max = bound.value
        elif bound.path == "agent_recurrence.max_occurrences" and isinstance(bound.value, int):
            recurrence = bound.value
    constraints: list[Any] = [AmountRange(currency=_CURRENCY, min=0, max=amount_max)]
    if payees:
        constraints.append(AllowedPayees(allowed=[Merchant(id=item, name=item) for item in payees]))
    if budget_max is not None:
        constraints.append(Budget(currency=_CURRENCY, max=budget_max))
    if instruments:
        constraints.append(
            AllowedPaymentInstruments(
                allowed=[
                    PaymentInstrument(id=item, type="card", description=item)
                    for item in instruments
                ]
            )
        )
    if recurrence is not None:
        # The SDK hashes the model with json.dumps and cannot encode the enum.
        item = AgentRecurrence(frequency=Frequency.ON_DEMAND, max_occurrences=recurrence)
        object.__setattr__(item, "frequency", Frequency.ON_DEMAND.value)
        constraints.append(item)
    presented = 1 if amount_max >= 1 else 0
    payee_id = payees[0] if payees else "kavach"
    instrument_id = instruments[0] if instruments else "card"
    return constraints, presented, payee_id, instrument_id


def _constraints_from_models(constraints: list[object]) -> list[MandateConstraint]:
    out: list[MandateConstraint] = []
    for item in constraints:
        kind = str(getattr(item, "type", ""))
        if kind == "payment.amount_range":
            out.append(
                MandateConstraint(
                    path="payment_amount.amount",
                    operator="lte",
                    value=getattr(item, "max", None),
                )
            )
        elif kind == "payment.allowed_payees":
            allowed = getattr(item, "allowed", [])
            out.append(
                MandateConstraint(
                    path="payee.id",
                    operator="in",
                    value=[getattr(merchant, "id", None) for merchant in allowed],
                )
            )
        elif kind == "payment.budget":
            out.append(
                MandateConstraint(path="budget", operator="lte", value=int(getattr(item, "max", 0)))
            )
        elif kind == "payment.agent_recurrence":
            out.append(
                MandateConstraint(
                    path="agent_recurrence.max_occurrences",
                    operator="lte",
                    value=getattr(item, "max_occurrences", None),
                )
            )
        elif kind == "payment.allowed_payment_instruments":
            allowed = getattr(item, "allowed", [])
            out.append(
                MandateConstraint(
                    path="payment_instrument.id",
                    operator="in",
                    value=[getattr(instrument, "id", None) for instrument in allowed],
                )
            )
    return out
