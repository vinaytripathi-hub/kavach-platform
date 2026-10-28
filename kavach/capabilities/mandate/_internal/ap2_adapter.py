"""AP2 payment-mandate verifier (ADR-0018 addendum).

Accepts an HS256 JWT whose claims follow the AP2 payment-mandate shape
(``vct``, ``transaction_id``, ``payee``, ``payment_amount``, optional
``checkout_jwt`` and ``constraints``). ``transaction_id`` must be the
SHA-256 (base64url, no padding) of ``checkout_jwt`` when that field is
present. Constraints are translated into ``MandateConstraint`` so the
policy engine stays format-agnostic.

This adapter does not import Google's AP2 package. The optional
``ap2`` extra documents that dependency for deployments that want the
upstream types; verification here is self-contained so the substrate
runs offline.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from typing import Any

from kavach.capabilities.mandate._internal.tokens import decode_hs256, issue_hs256, mandate_digest
from kavach.capabilities.mandate.contracts import VerifiedMandate
from kavach.capabilities.mandate.scope import scope_covers_action
from kavach.events.schemas.mandate import Mandate, MandateConstraint

_PAYMENT_TYPES = frozenset({"mandate.payment.1", "mandate.payment.open.1"})


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
    """Verifies an AP2-shaped payment mandate JWT."""

    def __init__(self, key: bytes) -> None:
        self._key = key

    def verify(  # noqa: PLR0911
        self,
        token: str,
        *,
        expected_agent_id: str,
        expected_action: str,
        now: datetime,
        revoked_ids: frozenset[str] = frozenset(),
        parent: Mandate | None = None,
    ) -> VerifiedMandate:
        del parent  # AP2 open mandates carry constraints directly; no parent chain here.
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
