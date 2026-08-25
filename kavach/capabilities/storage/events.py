"""Events emitted/consumed by the storage capability.

The storage capability emits no domain events of its own: it is the
substrate's persistence mechanism, not a decision-making capability. It
consumes (persists) every event the other capabilities emit. This module
exists to satisfy the ADR-0007 capability structure and to document that
deliberate emptiness.
"""

from __future__ import annotations

__all__: list[str] = []
