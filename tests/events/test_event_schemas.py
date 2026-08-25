"""Tests for the substrate event schemas and replay registry."""

from __future__ import annotations

import pytest

from kavach.events import deserialize_event, known_events, resolve_event
from kavach.events._base import DomainEvent
from kavach.events.schemas import (
    ActionExecuted,
    Confidence,
    DataSufficiency,
    DecisionEmitted,
    DecisionFeedbackRecorded,
    Evidence,
    EvidenceRecorded,
    ModalitySufficiency,
    PolicyEvaluated,
    ReasoningTrace,
    StepUpRequested,
    StepUpResolved,
    TrustAssessment,
    TrustAssessmentEmitted,
    TrustDimension,
    compose_sufficiency,
    rule_deterministic,
    worst_band,
)

ALL_EVENT_CLASSES: list[type[DomainEvent]] = [
    ActionExecuted,
    PolicyEvaluated,
    DecisionEmitted,
    EvidenceRecorded,
    TrustAssessmentEmitted,
    DecisionFeedbackRecorded,
    StepUpRequested,
    StepUpResolved,
]


def _decision() -> DecisionEmitted:
    return DecisionEmitted(
        tenant_id="t1",
        agent_id="agent-1",
        session_id="s1",
        decision_id="d1",
        action_type="account.funds.transfer",
        parameters={"amount": 100000},
        outcome="step_up",
        evidence=Evidence(attributes={"amount": 100000}),
        reasoning=ReasoningTrace(
            kind="rule", rule_id="r-high-value", decision_path="amount > 50000"
        ),
        confidence=rule_deterministic(),
        decided_by="rule:r-high-value",
        step_up_reason="High-value transfer",
        step_up_role="senior_ops",
    )


class TestEnvelope:
    def test_event_has_envelope_defaults(self) -> None:
        evt = ActionExecuted(
            tenant_id="t1",
            agent_id="agent-1",
            session_id="s1",
            action_type="kyc.document.verify",
        )
        assert evt.event_id
        assert evt.tenant_id == "t1"
        assert evt.occurred_at.tzinfo is not None
        assert evt.aggregate_id() == "agent-1"

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValueError):
            ActionExecuted(
                tenant_id="t1",
                agent_id="a",
                session_id="s",
                action_type="x",
                bogus="nope",  # type: ignore[call-arg]
            )

    def test_event_is_frozen(self) -> None:
        evt = ActionExecuted(tenant_id="t1", agent_id="a", session_id="s", action_type="x")
        with pytest.raises(ValueError):
            evt.__setattr__("agent_id", "b")


class TestRegistry:
    def test_all_eight_events_registered(self) -> None:
        registered = set(known_events())
        for cls in ALL_EVENT_CLASSES:
            assert (cls.event_type, cls.schema_version) in registered

    def test_resolve_returns_class(self) -> None:
        assert resolve_event("ActionExecuted", 1) is ActionExecuted

    def test_resolve_unknown_raises(self) -> None:
        with pytest.raises(KeyError):
            resolve_event("NopeEvent", 99)

    @pytest.mark.parametrize("cls", ALL_EVENT_CLASSES)
    def test_roundtrip_serialize_deserialize(self, cls: type[DomainEvent]) -> None:
        # Build a minimal valid instance per class via the decision sample
        # where rich fields are required, else simple construction.
        evt = _sample_for(cls)
        payload = evt.payload()
        restored = deserialize_event(cls.event_type, cls.schema_version, payload)
        assert restored == evt


class TestDataSufficiency:
    def test_worst_band_wins(self) -> None:
        assert worst_band(["warm", "cold", "thin"]) == "cold"
        assert worst_band(["warm", "warm_stale"]) == "warm_stale"
        assert worst_band([]) == "cold"

    def test_compose_picks_worst(self) -> None:
        suff = compose_sufficiency(
            {
                "a": ModalitySufficiency(modality="a", band="warm", observations=100),
                "b": ModalitySufficiency(modality="b", band="thin", observations=3),
            }
        )
        assert suff.band == "thin"


class TestTrustComposition:
    def _assessment(self) -> TrustAssessment:
        suff = compose_sufficiency(
            {"m": ModalitySufficiency(modality="m", band="warm", observations=50)}
        )
        return TrustAssessment(
            agent_id="agent-1",
            context="customer_service",
            dimensions={
                "credential_integrity": TrustDimension(
                    name="credential_integrity", value=0.9, sufficiency=suff
                ),
                "policy_compliance": TrustDimension(
                    name="policy_compliance", value=0.6, sufficiency=suff
                ),
            },
        )

    def test_weighted_average(self) -> None:
        from kavach.events.schemas import CompositionSpec

        a = self._assessment()
        spec = CompositionSpec(
            method="weighted_average",
            weights={"credential_integrity": 1.0, "policy_compliance": 1.0},
        )
        scalar = a.compose(spec)
        assert scalar == pytest.approx(0.75)

    def test_min_composition(self) -> None:
        from kavach.events.schemas import CompositionSpec

        a = self._assessment()
        assert a.compose(CompositionSpec(method="min")) == pytest.approx(0.6)

    def test_no_spec_returns_none(self) -> None:
        assert self._assessment().compose() is None


class TestConfidence:
    def test_rule_deterministic_is_full(self) -> None:
        c = rule_deterministic()
        assert c.kind == "rule_deterministic"
        assert c.score == 1.0

    def test_probabilistic_score_bounds(self) -> None:
        with pytest.raises(ValueError):
            Confidence(kind="probabilistic", score=1.5)


def _sample_for(cls: type[DomainEvent]) -> DomainEvent:  # noqa: PLR0911
    """Construct a minimal valid event instance for the given class."""
    suff: DataSufficiency = compose_sufficiency(
        {"m": ModalitySufficiency(modality="m", band="cold", observations=0)}
    )
    evidence = Evidence(attributes={"k": "v"})
    if cls is ActionExecuted:
        return ActionExecuted(tenant_id="t1", agent_id="a", session_id="s", action_type="x")
    if cls is PolicyEvaluated:
        return PolicyEvaluated(
            tenant_id="t1",
            agent_id="a",
            session_id="s",
            decision_id="d",
            action_type="x",
            matched_rule_id="r1",
            outcome="allow",
        )
    if cls is DecisionEmitted:
        return _decision()
    if cls is EvidenceRecorded:
        return EvidenceRecorded(tenant_id="t1", agent_id="a", evidence=evidence)
    if cls is TrustAssessmentEmitted:
        return TrustAssessmentEmitted(
            tenant_id="t1",
            agent_id="a",
            context="customer_service",
            assessment=TrustAssessment(
                agent_id="a",
                context="customer_service",
                dimensions={
                    "credential_integrity": TrustDimension(
                        name="credential_integrity", value=0.5, sufficiency=suff
                    )
                },
            ),
        )
    if cls is DecisionFeedbackRecorded:
        return DecisionFeedbackRecorded(
            tenant_id="t1",
            decision_id="d",
            agent_id="a",
            feedback="true_positive",
            provided_by="operator:op1",
            evidence=evidence,
            reasoning=ReasoningTrace(kind="human", decision_path="confirmed"),
            confidence=Confidence(kind="human_judged", score=0.8),
        )
    if cls is StepUpRequested:
        return StepUpRequested(
            tenant_id="t1",
            agent_id="a",
            session_id="s",
            decision_id="d",
            action_type="x",
            reason="high value",
            required_role="senior_ops",
        )
    if cls is StepUpResolved:
        return StepUpResolved(
            tenant_id="t1",
            agent_id="a",
            decision_id="d",
            resolution="approve",
            operator_id="op1",
            final_outcome="allow",
        )
    raise AssertionError(f"no sample for {cls}")
