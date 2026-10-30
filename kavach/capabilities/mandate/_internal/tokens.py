"""Shared HMAC token helpers for mandate verifiers."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

import jwt

from kavach.events.schemas.mandate import Mandate


def mandate_digest(mandate: Mandate) -> str:
    """Stable SHA-256 over the canonical mandate JSON."""
    canonical = json.dumps(mandate.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_MIN_HS256_KEY_BYTES = 32


def _jwt_key(key: bytes) -> bytes:
    """HS256 wants at least 32 bytes (RFC 7518). Short keys are stretched."""
    if len(key) >= _MIN_HS256_KEY_BYTES:
        return key
    return hashlib.sha256(key).digest()


def issue_hs256(claims: dict[str, Any], key: bytes) -> str:
    """Sign ``claims`` as a compact JWT (HS256)."""
    token: str = jwt.encode(claims, _jwt_key(key), algorithm="HS256")
    return token


def temporal_rejection(mandate: Mandate, now: datetime) -> str | None:
    """Return a failure reason when ``now`` is outside the mandate lifetime."""
    not_before = getattr(mandate, "not_before", None)
    if not_before is not None and now < not_before:
        return "Mandate not yet valid."
    expires_at = getattr(mandate, "expires_at", None)
    if expires_at is not None and expires_at <= now:
        return "Mandate expired."
    return None


def decode_hs256(token: str, key: bytes) -> dict[str, Any] | None:
    """Return claims, or None when the signature or shape is wrong."""
    try:
        decoded: dict[str, Any] = jwt.decode(
            token,
            _jwt_key(key),
            algorithms=["HS256"],
            options={"verify_exp": False, "verify_iat": False},
        )
    except jwt.PyJWTError:
        return None
    return decoded


def hmac_eq(key: bytes, material: str, signature: str) -> bool:
    expected = hmac.new(key, material.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
