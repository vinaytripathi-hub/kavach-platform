"""In-process RS256 issuer for tests and offline demos (ADR-0021).

Unit and e2e tests must not boot Keycloak. This module generates one
keypair per process, exposes its JWKS, and mints operator access tokens
the ``OperatorIdentityVerifier`` accepts when ``oidc_jwks`` is set.
"""

from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any, TypedDict

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

ISSUER = "https://kavach.test/realms/kavach"
AUDIENCE = "kavach"
_KID = "kavach-test"


@lru_cache(maxsize=1)
def _private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks_json() -> str:
    """Public JWKS document matching :func:`mint_operator_token`."""
    jwk: dict[str, Any] = json.loads(RSAAlgorithm.to_jwk(_private_key().public_key()))
    jwk["kid"] = _KID
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return json.dumps({"keys": [jwk]})


class OidcSettings(TypedDict):
    """The three config fields tests set so the verifier trusts this issuer."""

    oidc_issuer: str
    oidc_audience: str
    oidc_jwks: str


def oidc_settings() -> OidcSettings:
    """``SubstrateConfig`` fields that point the verifier at this issuer."""
    return {
        "oidc_issuer": ISSUER,
        "oidc_audience": AUDIENCE,
        "oidc_jwks": jwks_json(),
    }


def mint_operator_token(
    *,
    sub: str = "op-demo",
    role: str = "admin",
    tenant: str = "bank-1",
    expired: bool = False,
    not_yet_valid: bool = False,
) -> str:
    """Mint an RS256 operator access token."""
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": sub,
        "iat": now,
        "nbf": now + 3600 if not_yet_valid else now,
        "exp": now - 60 if expired else now + 600,
        "roles": [role],
        "tenant": tenant,
    }
    token = jwt.encode(claims, _private_key(), algorithm="RS256", headers={"kid": _KID})
    return token if isinstance(token, str) else token.decode("ascii")
