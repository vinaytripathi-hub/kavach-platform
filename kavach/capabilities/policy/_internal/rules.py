"""Declarative policy rule model (maps to the OpenAPI PolicyRule schema)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Operator = Literal[
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "contains",
    "mandate_covers_action",
    "mandate_constraint_satisfied",
]
Effect = Literal["allow", "deny", "step_up"]


class PolicyCondition(BaseModel):
    """A single attribute test against a request's evaluation context."""

    model_config = ConfigDict(extra="forbid")

    attribute: str
    operator: Operator
    value: Any = None


class PolicyRule(BaseModel):
    """A rule: an action-type glob plus optional conditions and an effect."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    description: str = ""
    action_type: str
    effect: Effect
    conditions: list[PolicyCondition] = Field(default_factory=list)
    step_up_role: str | None = None
    priority: int = 100
    mandate_required: bool = False
    mandate_originator_kinds: list[str] | None = None


class PolicyRuleSet(BaseModel):
    """A versioned set of rules for a use case."""

    model_config = ConfigDict(extra="forbid")

    use_case: str
    version: str = "0"
    rules: list[PolicyRule] = Field(default_factory=list)
    default_effect: Effect = "deny"
    default_step_up_role: str = "supervisor"
