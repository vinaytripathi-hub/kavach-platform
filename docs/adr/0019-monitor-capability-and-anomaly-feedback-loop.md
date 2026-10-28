# ADR-0019 — Monitor capability and anomaly feedback loop

**Status:** Proposed
**Date:** 2026-10-27

## Context

NIST tenet 09 (*Continuous Monitoring*) requires that agent access
and behaviour be monitored with agent-specific metrics, thresholds,
    10|and anomaly detection, at the scale and velocity at which agents
operate. The accompanying rationale is explicit: without continuous
monitoring, agent compromise, configuration drift, and privilege
escalation go undetected, and the risk compounds with long-running
or persistent agents.

Kavach today has the raw material for this but no detector:

- Read-side projections (ADR-0009) materialise per-agent timelines,
  trust assessments, and the step-up queue.
    20|- `TrustAssessmentEmitted` events track credential integrity and
  will carry behavioural dimensions as they are added (ADR-0014).
- `DecisionFeedbackRecorded` (ADR-0012) closes a false-positive /
  true-positive loop — but it depends on something emitting the
  original "this was anomalous" signal.
- ADR-0012 explicitly reserves `AnomalyDetected` for "when the
  monitoring capability is established."

This ADR establishes it. It does so under two non-negotiable
constraints inherited from the surrounding architecture:

    30|1. **Policy must remain deterministic (tenet 08).** A detector may
   use probabilistic methods internally, but what it emits to policy
   must be a labelled, bounded signal that policy's rules evaluate
   deterministically. The detector's internals and policy's inputs
   are separated by a Pydantic contract.
2. **Monitoring must not live inside the policy engine (tenet 07).**
   The reasoning that decides *what is anomalous* is architecturally
   outside the reasoning that decides *what is allowed*. These are
   different concerns with different failure modes, and conflating
   them re-introduces exactly the policy/reasoning entanglement
    40|   tenet 07 forbids.

The right shape, under those two constraints, is a new capability
that reads the event stream, maintains per-agent baselines, emits
`AnomalyDetected` events as a first-class decision-grade signal, and
exposes the current anomaly state through a projection that the
policy engine can read like any other input.

## Decision

**1. A new `monitor` capability** lands at
    50|`kavach/capabilities/monitor/` with the same shape every capability
in ADR-0007 follows:

```
kavach/capabilities/monitor/
├── __init__.py           # public re-exports
├── contracts.py          # AnomalyDetector Protocol, VerifiedAnomaly
├── events.py             # re-exports monitor events for convenience
└── _internal/
    ├── baselines.py      # per-tenant, per-agent rolling baselines
    ├── worker.py         # bus subscriber; produces metrics + anomalies
    60|    ├── snapshot.py       # metric snapshotting logic
    └── detectors/
        ├── rate.py              # decisions-per-minute anomaly
        ├── outcome_drift.py     # deny-rate shift
        ├── scope_expansion.py   # new action-type appearances
        └── confidence_drop.py   # mean-confidence decrease
```

Each detector is a small, independently-testable module implementing
the `AnomalyDetector` Protocol. New detectors are added by writing a
new module and registering it in composition — the extension-point
    70|pattern ADR-0007 established.

**2. Detector output is labelled and bounded.** The Protocol:

```python
class AnomalyDetector(Protocol):
    detector_id: str
    consumes: frozenset[str]              # event types that drive it

    def observe(
        self,
        session: AsyncSession,
    80|        event: DomainEvent,
        baseline: AgentBaseline,
    ) -> list[AnomalyDetected] | None: ...
```

A detector returns zero or more `AnomalyDetected` events. Each
`AnomalyDetected` carries:

- `detector_id` — which detector fired.
- `severity: Literal["info", "warn", "critical"]` — the bounded,
  deterministic label policy will evaluate.
    90|- `signal_score: float | None` — the raw probabilistic score, when
  the detector is probabilistic. **Advisory only**; policy does not
  branch on it (tenet 08).
- `sufficiency: DataSufficiency` — the ADR-0013 band
  (`thin`/`moderate`/`sufficient`), so downstream consumers know
  whether to trust the finding or treat it as cold-start.
- `description` — human-readable explanation.
- `triggering_event_ids: list[str]` — the events that drove the
  detection, enabling a replay of the anomaly from the audit chain.

   100|**3. Three new events enter the schema** (versioned per ADR-0010):

- `AgentMetricSnapshot(tenant_id, agent_id, window_start, window_end, metrics)` — periodic snapshot of per-agent metrics the detectors derive baselines from. Replayable; forms the baseline reconstruction path.
- `AnomalyDetected(tenant_id, agent_id, detector_id, severity, signal_score, sufficiency, description, triggering_event_ids)` — a detector finding. Carries the four decision-grade fields embedded (ADR-0012): evidence (the triggering events), reasoning (the detector logic + baseline), confidence (bounded by sufficiency), decided-by (`monitor:<detector_id>`).
- `AnomalyAcknowledged(anomaly_id, operator_id, resolution, rationale)` — operator feedback on an anomaly. `resolution: Literal["true_positive", "false_positive", "needs_investigation"]`. Flows into `DecisionFeedbackRecorded` so the labelled-data pipeline from ADR-0012 picks it up.

**4. A new projection surfaces current anomaly state.**
`AgentAnomalyCurrentRow` holds, per (tenant_id, agent_id), the
highest-severity open anomaly, its detector, its sufficiency, and
   110|its first-seen timestamp. The policy engine reads this projection as
a condition input, exactly like it reads parameters today — no new
coupling into the engine itself.

**5. Policy integration is via a condition operator, not a function
call.** Rule authors gain:

```python
# Example rule fragment (customer_service)
PolicyRule(
    rule_id="transfer.initiate.with-anomaly",
    action_type="transfer.initiate",
   120|    effect="step_up",
    conditions=[
        PolicyCondition(
            attribute="agent.anomaly_severity",
            operator="in",
            value=["warn", "critical"],
        ),
    ],
    priority=10,
)
```

   130|`PolicyEngine` resolves `agent.anomaly_severity` by reading
`AgentAnomalyCurrentRow`. The rule itself is pure, deterministic, and
reviewable; the detector's internals are not in the engine's blast
radius. This is the shape tenet 07 requires.

The default integration pattern is: a `critical` anomaly on a
mandate-covered or high-impact action promotes the outcome from
`allow` to `step_up`; a `warn` can tighten mandate requirements or
require secondary review. These are per-use-case rule-set decisions,
not substrate decisions.

   140|**6. The worker is bus-driven, not polling-driven.** `monitor` is
registered as a projection handler on the event bus (same shape as
`AuditChainWriter`). On every relevant event, it updates baselines
and runs the detectors synchronously within the event's transaction.
Rationale: anomaly signals must be available for the *next* policy
decision, not minutes later. Metric snapshots are emitted on a wall-
clock schedule by the background worker (ADR-0017's `worker` service).

**7. API surface.** `/v1` gains:

- `GET /v1/agents/{agent_id}/anomalies` — list open anomalies for an
   150|  agent, newest first; operator-authenticated.
- `POST /v1/anomalies/{anomaly_id}/acknowledge` — operator resolves
  an anomaly with a `resolution` and `rationale`; emits
  `AnomalyAcknowledged` and (per the resolution) a
  `DecisionFeedbackRecorded`.
- `GET /v1/agents/{agent_id}/metrics` — the latest
  `AgentMetricSnapshot` and a short history.

The operator console gains an "anomalies" screen that reads these
endpoints; existing timeline / trust / step-up screens remain.

   160|**8. First-cut detectors (sufficient for the POC):**

- **Rate anomaly** — decisions per minute vs the per-agent rolling
  mean; fires `warn` at 3σ, `critical` at 5σ, suppressed while
  sufficiency is `thin`.
- **Outcome drift** — deny-rate shift over sliding windows; fires
  `warn` on >2× shift sustained for N decisions.
- **Scope expansion** — appearance of an `action_type` the agent has
  never emitted before; fires `info` on first occurrence, `warn`
  when combined with elevated rate.
   170|- **Confidence drop** — mean `Confidence.score` across recent
  probabilistic decisions dropping below the per-agent baseline;
  fires `warn` and surfaces the triggering decisions.

Additional detectors (parameter outliers, cross-session correlation,
mandate-expiry pressure) are future work; the Protocol-based
registration makes them additive.

## Consequences

**Positive:**
   180|
- **Closes NIST tenet 09** with a concrete, implemented capability.
  The crosswalk row flips from Partial to Implemented, with named
  detectors and an operator-visible workflow.
- **Preserves tenets 07 and 08.** Detectors can be probabilistic;
  policy's view of them is deterministic (`severity` label). The
  reasoning that decides anomaly is architecturally outside the
  reasoning that decides access.
- **Natural extension of existing infrastructure.** New capability
  under the ADR-0007 pattern; new events under the ADR-0010
   190|  versioning rules; new projection under the ADR-0009 shape; new
  API endpoints under the ADR-0016 contract. No existing module
  changes shape.
- **Closes the feedback loop for free.** Operator acknowledgement of
  anomalies feeds `DecisionFeedbackRecorded`, which ADR-0012 already
  specified as the labelled-data pipeline. Detector thresholds can
  be tuned from accumulated feedback; eventually, detectors
  themselves can be learned.
- **Supports the "undetected agent compromise" scenario NIST calls
  out.** A compromised agent that attempts actions outside its
   200|  behavioural baseline raises `scope_expansion` + `rate` warnings
  immediately; policy tightens; audit chain preserves the signal.

**Negative:**

- **Baseline cold-start.** A newly-registered agent has no behaviour
  to baseline against. Mitigated by ADR-0013 data-sufficiency bands:
  detectors emit anomalies with `thin` sufficiency during warm-up,
  and rules can be written to ignore `thin`-sufficiency findings for
  the first N decisions.
   210|- **False-positive risk → alert fatigue.** This is exactly the
  consent-fatigue concern NIST calls out in tenet 05. The acknowledge
  loop plus per-severity rate caps in rules mitigate it; the operator
  console surfaces anomaly rate as a first-order metric.
- **Operational overhead.** Baselines need persistence; the worker
  carries more weight. For the prototype this is a Postgres table
  and in-process computation; production scale may demand per-agent
  partitioning or an external store.
- **Detector authoring is skill-dependent.** A badly-authored
  detector produces noise. Mitigation: each detector ships with
   220|  property-based tests and a documented sufficiency band; the
  Protocol forces explicit sufficiency reporting.
- **Monitoring the monitor.** The monitor itself can fail silently
  (worker crashes, baselines corrupt). Mitigated by surfacing a
  "monitor health" signal in the console and emitting a
  `MonitorDegraded` event on detector exceptions (follow-up work;
  not blocking for the POC).

## Alternatives Considered

   230|- **Put anomaly detection inside the policy engine.** Rejected.
  Violates tenet 07. Also makes the policy engine's blast radius
  include detector bugs, which is unacceptable for a deterministic
  access layer (tenet 08).
- **Rely entirely on an external SIEM / observability stack.**
  Rejected. The policy engine needs anomaly state as a decision
  input; routing that through an external system adds latency,
  couples a deployment-critical path to a non-substrate dependency,
  and loses the feedback loop into ADR-0012's labelled-data
  pipeline. The right posture is: Kavach has a *small* in-substrate
   240|  detector that owns the policy-feedback path; detailed telemetry
  still flows to the partner's SIEM via the signed-webhook egress
  (ADR-0008 outbox).
- **Use purely probabilistic signals as policy inputs.** Rejected.
  Tenet 08 is explicit: probabilistic information may inform the
  decision but may not be the primary mechanism. Labelling via
  bounded severity resolves this cleanly.
- **Build only after labelled feedback accumulates.** Rejected. The
  feedback loop requires something to label; the "something" is the
  detector. Bootstrapping with simple, well-understood statistical
   250|  detectors is cheap and gives the feedback pipeline substance to
  operate on.
- **Emit anomalies but do not feed them back to policy.** Rejected.
  That reduces monitoring to passive observation. NIST tenet 09's
  rationale (*prevents undetected agent compromise, configuration
  drift, or privilege escalation*) requires the signal to reach the
  access path; otherwise detection is diagnostic, not preventive.
- **Make the monitor its own service, not a substrate capability.**
  Considered. Rejected for the prototype because the in-process,
  transactional path is simpler and keeps the anomaly signal
   260|  available on the very next decision. A separate service is
  revisited when scale demands it; the capability's Protocol
  boundary makes the extraction straightforward.

## References

- NIST / NCCoE, *Design Tenets for Agent Identity Management
  Systems*, Cybersecurity Insights blog, 27 October 2026 — tenet 09
  (*Continuous Monitoring*).
- [docs/compliance/nist-agentic-iam-mapping.md](../compliance/nist-agentic-iam-mapping.md) —
   270|  the crosswalk row this ADR targets.
- [ADR-0007](./0007-modular-capability-architecture.md) — the
  capability + extension-point shape `monitor` follows.
- [ADR-0008](./0008-events-as-substrate-primary-output.md) —
  `AnomalyDetected`, `AgentMetricSnapshot`, `AnomalyAcknowledged`
  as first-class events.
- [ADR-0009](./0009-read-side-projections.md) —
  `AgentAnomalyCurrentRow` as a projection the policy engine reads.
- [ADR-0010](./0010-event-schema-versioning.md) — the three new
  events are versioned under this discipline.
   280|- [ADR-0012](./0012-decision-events-with-evidence-and-reasoning.md) —
  `AnomalyDetected` is a decision event; `AnomalyAcknowledged`
  flows into `DecisionFeedbackRecorded`.
- [ADR-0013](./0013-multimodal-data-sufficiency.md) — sufficiency
  bands applied to detector output.
- [ADR-0014](./0014-multidimensional-trust-substrate.md) — detector
  signals become candidate trust dimensions.
- [ADR-0016](./0016-external-api-surface-and-versioning.md) — the
  `/v1` surface the three new endpoints extend.
