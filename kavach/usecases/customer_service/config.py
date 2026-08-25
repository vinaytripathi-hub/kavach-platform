"""Customer Service use case configuration and trust dimension catalog.

Per ADR-0014, use cases extend the substrate's base trust dimensions with
use-case-specific ones. The substrate ships ``credential_integrity`` and
peers; Customer Service adds ``script_adherence`` (does the agent follow
the approved conversational/process script) and weights the composition
toward conversational quality.
"""

from __future__ import annotations

from kavach.events.schemas import CompositionSpec

USE_CASE = "customer_service"
DISPLAY_NAME = "Customer Service"

# Use-case-specific trust dimensions layered on the substrate base set.
USE_CASE_TRUST_DIMENSIONS = ("script_adherence",)

# Default composition for this use case: weight conversational adherence
# and policy compliance, with credential integrity as a gating baseline.
DEFAULT_TRUST_COMPOSITION = CompositionSpec(
    method="weighted_average",
    weights={
        "credential_integrity": 0.4,
        "policy_compliance": 0.3,
        "script_adherence": 0.3,
    },
    notes="Customer Service weights conversational adherence and compliance.",
)
