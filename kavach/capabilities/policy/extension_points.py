"""Extension points use cases implement for the policy capability (ADR-0007).

A use case provides its rule set through a ``PolicyRuleProvider``. The
composition layer collects providers and wires the resulting rule sets
into policy engines, one per use case.
"""

from __future__ import annotations

from typing import Protocol

from kavach.capabilities.policy._internal.rules import PolicyRuleSet


class PolicyRuleProvider(Protocol):
    """Supplies a rule set for a single use case."""

    @property
    def use_case(self) -> str: ...

    def rule_set(self) -> PolicyRuleSet: ...
