"""Substrate configuration (ADR-0017).

Environment-variable driven, all prefixed ``KAVACH_`` (the prefix the
test harness isolates). Secrets default to obvious insecure development
values; on-prem deployments supply real values at deploy time.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from kavach.capabilities.sdk_bridge import VerifierMode


class SubstrateConfig(BaseSettings):
    """Runtime configuration for the substrate."""

    model_config = SettingsConfigDict(env_prefix="KAVACH_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite://"
    audit_hmac_key: str = "dev-insecure-audit-key-change-me"
    sdk_bridge_mode: VerifierMode = "fake"
    jwt_secret: str = "dev-insecure-jwt-secret-change-me"  # noqa: S105
    expected_audience: str = "kavach"
    operator_token: str = "operator-dev-token"  # noqa: S105
    echo_sql: bool = False
    # When true, the API creates tables on startup (convenient for the
    # SQLite demo). On-prem Postgres deployments set this false and run
    # Alembic migrations explicitly (ADR-0017).
    auto_create_schema: bool = True

    @property
    def audit_key_bytes(self) -> bytes:
        return self.audit_hmac_key.encode("utf-8")
