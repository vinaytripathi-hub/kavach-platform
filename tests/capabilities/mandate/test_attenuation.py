"""Direct unit tests for parent-mandate attenuation (ADR-0018)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from kavach.capabilities.mandate._internal.attenuation import (
    attenuation_ok,
    constraints_at_least_as_tight,
)
from kavach.events.schemas.mandate import Mandate, MandateConstraint


def _mandate(
    *,
    mandate_id: str = "m-child",
    parent_id: str | None = None,
    scope: list[str] | None = None,
    constraints: list[MandateConstraint] | None = None,
) -> Mandate:
    now = datetime.now(UTC)
    return Mandate(
        mandate_id=mandate_id,
        originator_id="cust-1",
        originator_kind="human",
        agent_id="agent-1",
        action_scope=scope if scope is not None else ["account.funds.transfer"],
        constraints=constraints or [],
        issued_at=now,
        expires_at=now + timedelta(hours=1),
        parent_mandate_id=parent_id,
        nonce="n1",
    )


def _c(path: str, op: str, value: object) -> MandateConstraint:
    return MandateConstraint(path=path, operator=op, value=value)  # type: ignore[arg-type]


# -- constraints_at_least_as_tight -------------------------------------------


def test_lte_child_tighter_is_ok() -> None:
    parent = _mandate(constraints=[_c("amount", "lte", 50000)])
    child = _mandate(constraints=[_c("amount", "lte", 40000)])
    assert constraints_at_least_as_tight(parent, child) is True


def test_lte_child_broader_is_rejected() -> None:
    parent = _mandate(constraints=[_c("amount", "lte", 50000)])
    child = _mandate(constraints=[_c("amount", "lte", 60000)])
    assert constraints_at_least_as_tight(parent, child) is False


def test_gte_child_tighter_is_ok() -> None:
    parent = _mandate(constraints=[_c("amount", "gte", 100)])
    child = _mandate(constraints=[_c("amount", "gte", 500)])
    assert constraints_at_least_as_tight(parent, child) is True


def test_in_child_subset_is_ok_superset_rejected() -> None:
    parent = _mandate(constraints=[_c("region", "in", ["IN", "SG", "US"])])
    tight = _mandate(constraints=[_c("region", "in", ["IN"])])
    broad = _mandate(constraints=[_c("region", "in", ["IN", "EU"])])
    assert constraints_at_least_as_tight(parent, tight) is True
    assert constraints_at_least_as_tight(parent, broad) is False


def test_eq_requires_equal_value() -> None:
    parent = _mandate(constraints=[_c("currency", "eq", "INR")])
    same = _mandate(constraints=[_c("currency", "eq", "INR")])
    diff = _mandate(constraints=[_c("currency", "eq", "USD")])
    assert constraints_at_least_as_tight(parent, same) is True
    assert constraints_at_least_as_tight(parent, diff) is False


def test_missing_matching_constraint_is_rejected() -> None:
    parent = _mandate(constraints=[_c("amount", "lte", 50000)])
    child = _mandate(constraints=[_c("currency", "eq", "INR")])
    assert constraints_at_least_as_tight(parent, child) is False


def test_different_operator_is_not_a_match() -> None:
    parent = _mandate(constraints=[_c("amount", "lte", 50000)])
    child = _mandate(constraints=[_c("amount", "lt", 50000)])
    assert constraints_at_least_as_tight(parent, child) is False


# -- attenuation_ok ----------------------------------------------------------


def test_root_mandate_is_ok() -> None:
    ok, reason = attenuation_ok(None, _mandate(parent_id=None))
    assert ok is True
    assert "Root" in reason


def test_missing_parent_is_rejected() -> None:
    ok, reason = attenuation_ok(None, _mandate(parent_id="m-parent"))
    assert ok is False
    assert "not supplied" in reason


def test_parent_id_mismatch_is_rejected() -> None:
    parent = _mandate(mandate_id="m-other")
    child = _mandate(parent_id="m-parent")
    ok, reason = attenuation_ok(parent, child)
    assert ok is False
    assert "does not match" in reason


def test_scope_not_subset_is_rejected() -> None:
    parent = _mandate(mandate_id="m-parent", scope=["account.funds.transfer"])
    child = _mandate(parent_id="m-parent", scope=["account.funds.transfer", "kyc.read"])
    ok, reason = attenuation_ok(parent, child)
    assert ok is False
    assert "strict subset" in reason


def test_broader_constraints_rejected() -> None:
    parent = _mandate(
        mandate_id="m-parent",
        scope=["account.funds.transfer", "kyc.read"],
        constraints=[_c("amount", "lte", 50000)],
    )
    child = _mandate(
        parent_id="m-parent",
        scope=["account.funds.transfer"],
        constraints=[_c("amount", "lte", 60000)],
    )
    ok, reason = attenuation_ok(parent, child)
    assert ok is False
    assert "broader" in reason


def test_valid_attenuation_is_accepted() -> None:
    parent = _mandate(
        mandate_id="m-parent",
        scope=["account.funds.transfer", "kyc.read"],
        constraints=[_c("amount", "lte", 50000)],
    )
    child = _mandate(
        parent_id="m-parent",
        scope=["account.funds.transfer"],
        constraints=[_c("amount", "lte", 25000)],
    )
    ok, reason = attenuation_ok(parent, child)
    assert ok is True
    assert "verified" in reason.lower()
