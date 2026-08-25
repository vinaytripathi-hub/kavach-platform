"""ASGI entrypoint for the Kavach API (ADR-0016, ADR-0017).

Wires the substrate with the enabled use cases and exposes ``app`` for
uvicorn (``uvicorn kavach.server:app``). Configuration comes from the
environment (``KAVACH_*``); see ``kavach.composition.config``.
"""

from __future__ import annotations

from fastapi import FastAPI

from kavach.api import create_app
from kavach.capabilities.policy import PolicyRuleProvider
from kavach.composition import build_substrate
from kavach.composition.config import SubstrateConfig
from kavach.usecases.customer_service import CustomerServiceRules


def enabled_rule_providers() -> list[PolicyRuleProvider]:
    """Use cases wired into the prototype. Credit/Trading land later."""
    return [CustomerServiceRules()]


def build_app(config: SubstrateConfig | None = None) -> FastAPI:
    substrate = build_substrate(
        config or SubstrateConfig(), rule_providers=enabled_rule_providers()
    )
    return create_app(substrate)


app = build_app()
