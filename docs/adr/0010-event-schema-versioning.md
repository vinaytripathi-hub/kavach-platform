# ADR-0010 — Event schema versioning and stability

**Status:** Accepted
**Date:** 2026-05-24

## Context

ADR-0008 established that events are the substrate's primary output;
the event schema is the substrate's contract with use cases, experiences,
projections, and (when ADR-0011 in Block D.3 is realized) extracted
sub-products.

A contract has a stability discipline. Events are no different. Without
that discipline, the following failures are inevitable:

1. **Silent breakage.** Someone renames a field in an event class.
   The schema still parses, but a projection that depended on the old
   field name silently produces null values. Production data degrades;
   nobody notices until a compliance export turns up empty.

2. **Replay incompatibility.** Old events stored in the event log no
   longer match the current schema. Replay-based rebuilds fail. The
   "disaster recovery is replay" guarantee from ADR-0009 breaks.

3. **Cross-process drift.** When the substrate is extracted into
   sub-products (ADR-0011), the producer and consumer of an event
   live in different deployments. They evolve at different rates.
   Without versioning, either nothing can change, or everything breaks.

4. **Audit and compliance failure.** A regulator or auditor reading
   a historical event must be able to interpret it correctly. If
   schemas change without versioning, old events become uninterpretable
   without spelunking through git history.

The Kavach substrate must treat its event schemas the way well-run
public APIs treat their JSON contracts: explicit, versioned, additive
by default, breaking changes rare and ceremonial.

## Decision

**Event schemas are public API.** Every event class declares:

1. A stable name (the event type identifier, e.g., `AgentSessionStarted`)
2. A schema version (semver-ish; 1, 2, 3...; integer not dotted)
3. A Pydantic model defining the event's fields and types

A sketched shape:

```python
# kavach/events/schemas/agent_session.py — sketch
class AgentSessionStartedV1(DomainEvent):
    """Emitted when an agent begins a workflow session."""
    event_type: ClassVar[str] = "AgentSessionStarted"
    schema_version: ClassVar[int] = 1
    agent_id: AgentID
    session_id: SessionID
    delegation_chain_root: CredentialHash
    started_at: datetime
    # ... other fields
```

**Three classes of change:**

1. **Additive (no version bump):** Adding a new optional field with a
   default value. Old consumers ignore it; new consumers can use it.
   These changes don't require a new version.

2. **Compatible (no version bump):** Adding new field validation that
   doesn't reject any previously-valid event. Tightening a string max
   length where no real event exceeds the new limit. These are
   reviewable on a case-by-case basis; default to no version bump but
   document the change in CHANGELOG.

3. **Breaking (new version required):** Removing a field, renaming a
   field, changing a field's type, making an optional field required,
   removing a value from an enum. These require a new schema version
   (`AgentSessionStartedV2`) and an explicit migration story for
   stored events.

**Breaking changes follow a four-phase rollout:**

1. **Introduce V_new** alongside V_old. Both classes exist; both are
   emittable; consumers handle both.

2. **Migrate producers** to emit V_new. V_old is no longer emitted but
   the class still exists; historical events stored as V_old are still
   readable.

3. **Migrate consumers** (projection handlers, experience queries,
   downstream services) to consume only V_new. V_old handling code
   is retained as long as V_old events exist in the historical log.

4. **Retire V_old** only when all V_old events have been archived or
   re-projected. The V_old class is moved to `kavach/events/schemas/_archive/`
   and remains importable for historical replay.

**Schema definitions live under `kavach/events/schemas/`** organized by
domain (e.g., `kavach/events/schemas/agent_session.py`,
`kavach/events/schemas/policy.py`, `kavach/events/schemas/audit.py`).
Each module's `__all__` declares the events it exports; consumers
import from the module, not from internal sub-modules.

**Schema changes are reviewed differently than code changes.** A PR
that touches `kavach/events/schemas/` requires explicit acknowledgment
in the PR description of which class of change it is (additive,
compatible, breaking) and what consumers are affected. Breaking changes
require an updated ADR (or a new ADR explaining the rationale and the
migration plan) before merge.

**The event log records the schema version with each event.** When an
event is persisted, the `event_type` and `schema_version` are stored
alongside the payload. Replay walks the log and dispatches to the
correct schema class based on `(event_type, schema_version)`.

**Decision events specifically** (per ADR-0012 in Block D.3) carry
evidence, reasoning, and confidence. The structure of those embedded
fields is also versioned (e.g., a `ReasoningTrace` type has its own
version). Changes to those embedded types follow the same discipline.

## Consequences

**Positive:**

- **Replay works across schema generations.** Historical events in
  the event log remain interpretable as long as the relevant schema
  classes are retained. Disaster recovery is unaffected by schema
  evolution.

- **Sub-product extraction (ADR-0011) is safer.** Producer and
  consumer in separate deployments can evolve at different rates as
  long as both honor the versioning discipline. V_old support is the
  bridge during a coordinated rollout.

- **Audit and compliance evidence stays interpretable.** A regulator
  reading a 5-year-old event interprets it via the V1 schema, which
  is still in the codebase. There's no "version archaeology" required.

- **Type safety holds across evolution.** Pydantic's strict mode plus
  mypy strict catches a wide class of "I forgot to handle V_new" bugs
  at type-check time, before they reach production.

- **The schema discipline forces clarity about what events MEAN.**
  Adding a new field with a clear name and a documented purpose is
  cheap and welcomed; adding a field "just in case" is harder to
  justify when the cost of removing it later is a versioned migration.
  Schema discipline is a forcing function for thinking carefully.

**Negative:**

- **Versioned classes accumulate.** Over time `kavach/events/schemas/`
  grows. The archive (`_archive/`) accumulates retired classes that
  remain importable for replay. Mitigation: a yearly review prunes
  classes that have no historical events left.

- **The "additive vs compatible vs breaking" judgment is sometimes
  ambiguous.** Adding a new value to an enum is breaking for consumers
  that exhaustively switch on the enum, but additive for consumers
  that handle unknown values gracefully. Mitigation: document the
  intended consumer pattern in the schema's docstring; default to
  breaking-change discipline if uncertain.

- **Migration plans for breaking changes are real work.** A new
  schema version requires coordinated updates to producers,
  consumers, and replay infrastructure. We accept this cost; the
  alternative (no versioning) is worse.

- **Cross-version projections add complexity.** A projection handler
  may need to handle V1 and V2 of the same event differently. The
  handler becomes a small dispatch function. This is the right place
  for the complexity to live.

## Alternatives Considered

- **No versioning; schemas evolve freely.** Tempting at solo-founder
  velocity. Rejected because the cost of replay breakage in BFSI is
  high (compliance evidence becomes uninterpretable, projection
  rebuilds fail). The discipline cost is small compared to the
  downside.

- **Single global event version (everything is V1, then everything
  is V2).** Considered. Rejected because most schema changes affect
  one event class, not all of them; a global version forces
  unnecessary work and obscures which changes are actually breaking.

- **Use a schema registry (e.g., Confluent Schema Registry, Apicurio).**
  Considered. Rejected at current scale: a registry adds operational
  complexity for a problem that's tractable with Python type discipline.
  Revisit if Kavach ever runs schemas across enough services to make
  a registry justified.

- **Use Protocol Buffers or Avro instead of Pydantic.** Considered.
  Both have stronger versioning stories than Pydantic. Rejected because
  Pydantic integrates better with the rest of our Python stack
  (FastAPI, SQLAlchemy serialization, structlog) and the discipline
  rules in this ADR cover the versioning gap. Revisit if cross-language
  consumers (e.g., a JVM-based sub-product) become a hard requirement.

- **Allow only additive schema changes, ever.** Considered. Rejected
  because some breaking changes are genuinely necessary (we will get
  schemas wrong; refusing to fix them produces accumulating cruft).
  The four-phase rollout makes breaking changes manageable; refusing
  to make them is worse than disciplining them.

## References

- ADR-0007 — Modular capability architecture (events.py per capability
  declares emitted events)
- ADR-0008 — Events as primary output (the contract this ADR governs)
- ADR-0009 — Read-side projections (projection handlers depend on
  versioned events)
- ADR-0011 (Block D.3) — Sub-product extraction (extracted producers
  and consumers need versioning discipline to coordinate)
- ADR-0012 (Block D.3) — Decision events with embedded evidence and
  reasoning (those embedded types are versioned too)
- `kavach/events/schemas/` — established in W01-S02 Block E
- `docs/engineering-handbook.md` (planned, W01-S02 Block E) — code
  review checklist for schema changes
