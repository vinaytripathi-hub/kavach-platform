"""Parent-mandate attenuation checks (ADR-0018)."""

from __future__ import annotations

from kavach.capabilities.mandate.scope import scope_is_strict_subset
from kavach.events.schemas.mandate import Mandate, MandateConstraint


def _tighter(parent: MandateConstraint, child: MandateConstraint) -> bool:
    if parent.path != child.path or parent.operator != child.operator:
        return False
    op = parent.operator
    if op in ("lte", "lt"):
        return bool(child.value <= parent.value)
    if op in ("gte", "gt"):
        return bool(child.value >= parent.value)
    if op == "in":
        return set(child.value) <= set(parent.value)
    return bool(child.value == parent.value)


def constraints_at_least_as_tight(parent: Mandate, child: Mandate) -> bool:
    """Every parent constraint has a child constraint that is as tight or tighter."""
    for bound in parent.constraints:
        if not any(_tighter(bound, candidate) for candidate in child.constraints):
            return False
    return True


def attenuation_ok(parent: Mandate | None, child: Mandate) -> tuple[bool, str]:
    """Return whether ``child`` may be derived from ``parent``."""
    if child.parent_mandate_id is None:
        return True, "Root mandate."
    if parent is None:
        return False, "Parent mandate was not supplied."
    if parent.mandate_id != child.parent_mandate_id:
        return False, "Parent mandate id does not match."
    if not scope_is_strict_subset(parent.action_scope, child.action_scope):
        return False, "Sub-mandate scope is not a strict subset of the parent."
    if not constraints_at_least_as_tight(parent, child):
        return False, "Sub-mandate constraints are broader than the parent."
    return True, "Attenuation verified."
