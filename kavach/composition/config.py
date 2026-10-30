"""Substrate configuration (ADR-0017).

Environment-variable driven, all prefixed ``KAVACH_`` (the prefix the
test harness isolates). Secrets default to obvious insecure development
values; on-prem deployments supply real values at deploy time.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from kavach.capabilities.sdk_bridge import VerifierMode

MandateVerifierMode = Literal["fake", "ap2"]
AuditSignerMode = Literal["hmac", "kms_stub"]


class SubstrateConfig(BaseSettings):
    """Runtime configuration for the substrate."""

    model_config = SettingsConfigDict(env_prefix="KAVACH_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite://"
    audit_hmac_key: str = "dev-insecure-audit-key-change-me"
    sdk_bridge_mode: VerifierMode = "fake"
    mandate_verifier_mode: MandateVerifierMode = "fake"
    audit_signer_mode: AuditSignerMode = "hmac"
    jwt_secret: str = "dev-insecure-jwt-secret-change-me"  # noqa: S105
    expected_audience: str = "kavach"
    # Operator identity is OIDC (ADR-0021). Empty issuer fails closed.
    oidc_issuer: str = ""
    oidc_audience: str = "kavach"
    oidc_jwks_url: str = ""
    oidc_jwks: str = ""
    oidc_tenant_claim: str = "tenant"
    oidc_leeway_seconds: int = 30
    # Session credentials (ADR-0020). Hard cap is 15 minutes in the minter.
    agent_credential_ttl_seconds: int = 900
    # CAEP/SSF receiver. Empty disables outbound signals.
    signal_receiver_url: str = ""
    signal_issuer: str = "https://kavach.example"
    signal_audience: str = "kavach-ssf"
    echo_sql: bool = False
    # When true, the API creates tables on startup (convenient for the
    # SQLite demo). On-prem Postgres deployments set this false and run
    # Alembic migrations explicitly (ADR-0017).
    auto_create_schema: bool = True

    @property
    def audit_key_bytes(self) -> bytes:
        return self.audit_hmac_key.encode("utf-8")
