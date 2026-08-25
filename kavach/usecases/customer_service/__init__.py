"""Customer Service use case (ADR-0001 use-case layer).

A use case configures the substrate; it does not duplicate substrate
logic. This package provides the policy rule provider and the use-case
configuration (trust dimensions, composition).
"""

from __future__ import annotations

from kavach.usecases.customer_service.config import (
    DEFAULT_TRUST_COMPOSITION,
    DISPLAY_NAME,
    USE_CASE,
    USE_CASE_TRUST_DIMENSIONS,
)
from kavach.usecases.customer_service.policy_rules import (
    CustomerServiceRules,
    build_rule_set,
)

__all__ = [
    "DEFAULT_TRUST_COMPOSITION",
    "DISPLAY_NAME",
    "USE_CASE",
    "USE_CASE_TRUST_DIMENSIONS",
    "CustomerServiceRules",
    "build_rule_set",
]
