"""OIDC access-token verification for operator routes (ADR-0021).

Validates RS256 against an inline JWKS (tests, offline demos) or a
remote JWKS URL (Keycloak). Role and tenant checks live in the API
dependencies; this module only authenticates the token.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, cast

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from jwt import PyJWK, PyJWKClient

from kavach.composition.config import SubstrateConfig


@dataclass(frozen=True)
class OperatorClaims:
    """Verified operator access-token claims."""

    subject: str
    roles: frozenset[str]
    tenant: str


@dataclass
class OperatorIdentityVerifier:
    """Verifies operator JWTs. Fail-closed when no issuer is configured."""

    issuer: str
    audience: str
    leeway_seconds: int = 30
    tenant_claim: str = "tenant"
    _keys: dict[str, Any] = field(default_factory=dict)
    _jwks_client: PyJWKClient | None = None

    @classmethod
    def from_config(cls, config: SubstrateConfig) -> OperatorIdentityVerifier:
        verifier = cls(
            issuer=config.oidc_issuer,
            audience=config.oidc_audience,
            leeway_seconds=config.oidc_leeway_seconds,
            tenant_claim=config.oidc_tenant_claim,
        )
        if config.oidc_jwks:
            document = json.loads(config.oidc_jwks)
            for jwk in document.get("keys", []):
                if isinstance(jwk, dict):
                    kid = str(jwk.get("kid") or "")
                    verifier._keys[kid] = PyJWK.from_dict(jwk).key
        if config.oidc_jwks_url:
            verifier._jwks_client = PyJWKClient(config.oidc_jwks_url, cache_keys=True)
        return verifier

    @property
    def configured(self) -> bool:
        return bool(self.issuer) and (bool(self._keys) or self._jwks_client is not None)

    def verify(self, token: str) -> OperatorClaims:
        """Return claims or raise ``jwt.PyJWTError`` / ``ValueError``."""
        if not self.configured:
            raise ValueError("Operator identity is not configured.")
        header = jwt.get_unverified_header(token)
        key = self._resolve(str(header.get("kid") or ""))
        claims = jwt.decode(
            token,
            cast(RSAPublicKey, key),
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
            leeway=self.leeway_seconds,
        )
        tenant = claims.get(self.tenant_claim)
        if isinstance(tenant, list):
            tenant = tenant[0] if tenant else ""
        if not isinstance(tenant, str) or not tenant:
            raise ValueError("Operator token is missing a tenant claim.")
        return OperatorClaims(
            subject=str(claims.get("sub") or ""),
            roles=frozenset(_roles(claims)),
            tenant=tenant,
        )

    def _resolve(self, kid: str) -> object:
        if kid in self._keys:
            return self._keys[kid]
        if self._jwks_client is not None:
            return self._jwks_client.get_signing_key(kid).key
        if "" in self._keys and not kid:
            return self._keys[""]
        raise ValueError("No signing key for operator token.")


def _roles(claims: dict[str, Any]) -> set[str]:
    flat = claims.get("roles")
    if isinstance(flat, list):
        return {str(role) for role in flat}
    realm = claims.get("realm_access")
    if isinstance(realm, dict) and isinstance(realm.get("roles"), list):
        return {str(role) for role in realm["roles"]}
    return set()
