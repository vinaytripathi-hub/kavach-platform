# ADR-0008 — Domain events as the substrate's primary output

**Status:** Accepted
**Date:** 2026-05-24

## Context

Per ADR-0005, Kavach's product is operational accountability for BFSI
agents: who did what, on whose authority, with what evidence, with what
outcome. The substrate must produce information rich enough to support
all of the following experience-layer features:

- Real-time agent activity dashboards
- Historical timeline reconstruction ("what did Agent-X do last Tuesday")
- Trust score breakdowns ("why is Agent-X's trust score 67")
- Compliance evidence exports for regulators
- Comparative analysis between agents handling similar cases
- Anomaly detection over behavioral patterns
- Post-hoc inspector ("at the moment of this decision, what was the
  agent state")
- Customer-facing transparency ("here's what your assigned agent did
  for you")
- Operator override / step-up authentication workflows

The naive approach — design each experience as a separate query over
the substrate's internal state — creates one custom backend per
experience. Every new view requires custom code, custom API endpoints,
custom database queries, and tight coupling between the experience's
needs and the substrate's state shape. The platform doesn't compose;
it accretes.

The architecturally clean approach is well-known: structured events.
Capabilities emit events at every meaningful state transition; experiences
read projections built from those events; the substrate's contract with
the rest of the system is the event stream, not internal application
state. This is the foundation of the "trust infrastructure" positioning
in ADR-0005 — events are the substance of what we mean by "accountability."

Two questions remained open until this ADR resolves them:

1. **Is the event stream the substrate's primary output, or a secondary
   observability concern?** A naive answer says "events are for
   debugging/audit, internal state is the real product." An ambitious
   answer says "events ARE the product; internal state is a private
   convenience."

2. **Pure event sourcing, or pragmatic event-driven?** Pure ES derives
   all state from the event log; the database has only the event log
   plus projections. Pragmatic ED maintains state in tables for
   queryability AND emits events alongside state changes. Pure ES is
   theoretically cleaner; pragmatic ED is operationally simpler.

## Decision

**Domain events are the substrate's primary output.** Capabilities
are event transformers: they consume input events, produce output
events. Internal state is a private implementation convenience, not
part of the substrate's external contract.

The substrate's contract with use cases and experiences is the event
schema, not the database schema. Frontend code reads projections
(ADR-0009 in Block D.2) built from the event stream, not the
capabilities' internal tables.

**Pragmatic event-driven, not pure event sourcing.** State lives in
Postgres tables for queryability; events are emitted alongside state
changes. Any state that matters for compliance, audit, timeline
reconstruction, or experience-layer projections is *also* captured as
events. Capabilities can later migrate to pure event sourcing
per-capability if it becomes justified for a specific capability
(unlikely for most; possibly relevant for audit).

**The substrate's correctness lives at three layers, not one:**

1. **Logic correctness inside each capability.** Rules engines, hash
   chain math, signature verifiers, etc., must be correct. This is
   where false positives and false negatives originate. Tested by
   unit tests on the logic.

2. **Event correctness at the capability boundary.** Output events
   faithfully reflect what the logic decided. The event for a "deny"
   decision contains the right rule_id, inputs, reasoning, confidence.
   Tested by tests asserting "given these input events, this capability
   emits these output events with these fields."

3. **System correctness across capabilities.** Events flow correctly
   between capabilities. Ordering is preserved where it matters. No
   events are dropped or duplicated. The audit chain is unbroken.
   Tested by integration tests tracing event flow end-to-end.

Internal state is not part of the substrate's contract, so it can
restructure freely. But "internal state can be wrong as long as events
are right" is a misframing — if internal logic has bugs, the events
themselves are wrong, and we have no separate ground truth against
which to detect the wrongness. Correctness at all three layers is the
discipline.

**Every decision event carries evidence, reasoning, and confidence.**
(See ADR-0012 in Block D.3 for the formal rule.) A policy decision
event includes the rule_id that fired, the input attributes evaluated,
the model version (if probabilistic), the reasoning trace, and the
confidence. A trust assessment event includes the per-dimension scores,
the composition function, and the data sufficiency band (per ADR-0013
in Block D.4).

**Feedback events close the FP/FN loop.** When a human operator marks
an anomaly as a false positive (or confirms it as a true positive), that
classification is itself an event. The substrate accumulates labeled
training data through normal operation, which becomes the moat for
ML capabilities added later. This is documented further in ADR-0012.

## Consequences

**Positive:**

- **Every experience-layer feature becomes a projection over events.**
  Adding a new view to the frontend often requires zero substrate
  changes — just a new projection in `kavach/query/projections/`.
  This is the explicit leverage the architecture was designed to
  produce, per ADR-0005.

- **Time travel is cheap.** "What did the agent state look like at
  time T" becomes "replay events up to T." This is exactly what
  compliance audits and post-hoc inspectors need.

- **Disaster recovery is replay.** State can be rebuilt from the
  event log. Disaster recovery becomes "start with empty state,
  replay events." Backups focus on the event log; projection tables
  are derivable.

- **Cross-capability behavior is observable.** Cross-capability bugs
  (e.g., "audit didn't record the policy decision") become "this
  policy event was emitted but no corresponding audit event was
  emitted." Tracing event flow makes integration bugs concrete.

- **Sub-product extraction (ADR-0011) becomes more tractable.**
  Capabilities that consume and produce events can be lifted into
  standalone deployments by replacing the in-process event bus with
  a network-bridged one. Audit, Policy, and Console especially.

- **The event log is durable IP.** Aurvia's accumulating BFSI event
  log — across multiple customers, with human feedback labels — becomes
  training data for ML capabilities that competitors cannot replicate.
  This is the long-term substrate moat.

**Negative:**

- **Event schema design becomes a substrate concern.** Schemas are
  public API per ADR-0010 (Block D.2); breaking changes require
  migration. The cost of getting a schema wrong is higher than the
  cost of getting an internal data structure wrong. Mitigation:
  schemas live under `kavach/events/schema/` with explicit
  versioning; major schema changes require an ADR.

- **Pragmatic ED means double-writing.** State changes write to a
  table AND emit an event. This is a small overhead per write; we
  accept it for the queryability benefit.

- **Event volume can be high.** A real BFSI deployment may emit
  millions of events per day. The event log must be partitioned and
  archived correctly; Postgres alone handles this fine at our
  expected scale (low-thousands of agents, low-millions of events
  per day for a Tier-A pilot) but scaling to large-thousands of
  agents needs deliberate planning.

- **Operator console performance depends on projection performance.**
  If projections are slow, the operator console is slow. Mitigation:
  projections are materialized in tables; expensive ones are
  precomputed on event ingest, not at read time.

- **Pure event sourcing temptation.** Engineers familiar with pure
  ES may push to convert capabilities. We commit to per-capability
  evaluation rather than a blanket move; only specific capabilities
  benefit enough to justify the operational cost. Pragmatic ED is
  the default; pure ES is the exception.

## Alternatives Considered

- **Events as observability only (debugging/audit; not the primary
  output).** This was the framing in early architectural discussions.
  Rejected because it underweighted the experience-layer leverage
  events provide. The frontend reads events not because it's a nice
  side effect — but because events ARE the product surface.

- **Pure event sourcing across the substrate.** Considered seriously.
  Rejected for operational reasons: pure ES requires snapshotting
  discipline, projection replay infrastructure, careful migration
  story for schema evolution. The complexity is justified for systems
  where the event log IS the source of truth (e.g., financial ledgers).
  We get the leverage of events without the operational ceremony by
  keeping state in tables and emitting events alongside.

- **CQRS without event sourcing.** A common compromise: separate read
  and write models, but write model is state-based not event-based.
  Rejected because the event log itself is the durable IP and the
  audit-grade evidence; we want events as first-class, not as a
  derivative of the write model.

- **Service-bus-based events between microservices.** Right pattern
  if the substrate is decomposed into microservices. Rejected at
  current scale per ADR-0001's reasoning. The same event pattern
  works in-process; we can extract specific capabilities to
  microservices later (per ADR-0011) without changing the event
  semantics.

## References

- ADR-0001 — Three-layer architecture
- ADR-0005 — Accountability positioning (the events ARE what makes
  accountability operational)
- ADR-0007 — Modular capability architecture (the modular structure
  this ADR's events flow through)
- ADR-0009 (Block D.2) — Read-side projections over events
- ADR-0010 (Block D.2) — Event schema versioning and stability
- ADR-0011 (Block D.3) — Sub-product extraction (enabled by event boundary)
- ADR-0012 (Block D.3) — Decision events carry evidence and reasoning
- ADR-0013 (Block D.4) — Multimodal data sufficiency
- ADR-0014 (Block D.4) — Multidimensional trust substrate
- `kavach/events/` — events package scaffold (planned, W01-S02 Block E)
