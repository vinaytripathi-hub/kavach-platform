"""Live Keycloak check for the operator verifier (ADR-0021).

Skipped unless ``KAVACH_OIDC_ISSUER`` names a reachable issuer. Unit and
e2e tests mint RS256 tokens in-process and do not boot Keycloak.
"""

from __future__ import annotations

import os

import pytest

from kavach.composition.config import SubstrateConfig
from kavach.identity.oidc import OperatorIdentityVerifier

_ISSUER = os.environ.get("KAVACH_OIDC_ISSUER", "")

pytestmark = pytest.mark.skipif(
    not _ISSUER.startswith("http"),
    reason="Set KAVACH_OIDC_ISSUER to a live issuer to run.",
)


def test_live_jwks_client_constructs() -> None:
    config = SubstrateConfig(
        oidc_issuer=_ISSUER,
        oidc_jwks_url=os.environ.get(
            "KAVACH_OIDC_JWKS_URL",
            f"{_ISSUER}/protocol/openid-connect/certs",
        ),
        oidc_audience=os.environ.get("KAVACH_OIDC_AUDIENCE", "kavach"),
    )
    verifier = OperatorIdentityVerifier.from_config(config)
    assert verifier.configured
    assert verifier._jwks_client is not None
