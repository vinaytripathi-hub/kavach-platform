"""Events for the sdk_bridge capability.

The sdk_bridge verifies credentials at the request boundary and emits no
domain events of its own in the prototype; verification outcomes are
captured as evidence on the decisions they gate (ADR-0012).
"""

from __future__ import annotations

__all__: list[str] = []
