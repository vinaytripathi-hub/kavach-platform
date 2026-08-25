"""Tests for the ASGI server builder (kavach.server)."""

from __future__ import annotations

from fastapi import FastAPI

from kavach.composition.config import SubstrateConfig
from kavach.server import build_app, enabled_rule_providers


def test_enabled_rule_providers_includes_customer_service() -> None:
    providers = enabled_rule_providers()
    use_cases = {p.use_case for p in providers}
    assert "customer_service" in use_cases


def test_build_app_returns_fastapi_with_routes() -> None:
    app = build_app(SubstrateConfig(database_url="sqlite+aiosqlite://"))
    assert isinstance(app, FastAPI)
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]
    assert "/v1/health" in paths
    assert "/v1/agents/{agent_id}/decisions" in paths
    assert "/v1/step-ups" in paths
