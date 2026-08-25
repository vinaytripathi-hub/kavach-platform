"""Kavach external HTTP API (ADR-0016).

The substrate's network boundary. ``create_app`` builds the FastAPI
application around a wired ``Substrate``.
"""

from __future__ import annotations

from kavach.api.app import create_app

__all__ = ["create_app"]
