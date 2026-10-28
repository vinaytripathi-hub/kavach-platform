"""Action-scope subset checks for mandate attenuation (ADR-0018).

The grammar is the same ``fnmatch`` dialect the policy engine uses, with
a documented restriction: a pattern is either ``*``, a literal action
type, or a dotted prefix ending in ``.*``. Non-trivial globs (a ``*``
in the middle) are rejected by ``is_supported_pattern``.
"""

from __future__ import annotations


def is_supported_pattern(pattern: str) -> bool:
    """True when ``pattern`` is in the restricted mandate grammar."""
    if not pattern or pattern == "*":
        return pattern == "*"
    if "*" not in pattern:
        return True
    return pattern.endswith(".*") and pattern.count("*") == 1


def pattern_covers(parent: str, child: str) -> bool:
    """Whether every action matched by ``child`` is matched by ``parent``."""
    if not is_supported_pattern(parent) or not is_supported_pattern(child):
        return False
    if parent == "*":
        return True
    if parent == child:
        return True
    if parent.endswith(".*"):
        prefix = parent[:-2]
        if child == prefix or child.startswith(prefix + "."):
            return True
    return False


def scope_is_subset(parent_scopes: list[str], child_scopes: list[str]) -> bool:
    """True when every child pattern is covered by some parent pattern."""
    if not child_scopes:
        return False
    return all(
        any(pattern_covers(parent, child) for parent in parent_scopes) for child in child_scopes
    )


def scope_is_strict_subset(parent_scopes: list[str], child_scopes: list[str]) -> bool:
    """Subset, and not an identical grant."""
    if not scope_is_subset(parent_scopes, child_scopes):
        return False
    return set(child_scopes) != set(parent_scopes)


def scope_covers_action(scopes: list[str], action_type: str) -> bool:
    """Whether ``action_type`` (a literal) is inside ``scopes``."""
    return any(pattern_covers(scope, action_type) for scope in scopes)
