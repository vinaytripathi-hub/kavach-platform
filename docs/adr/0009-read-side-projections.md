# ADR-0009 — Read-side projections over the event stream

**Status:** Accepted
**Date:** 2026-05-24

## Context

ADR-0008 established that domain events are the substrate's primary
output. Capabilities emit events; the event log is the durable record;
the substrate's contract with the rest of the system is the event
schema, not the internal database schema.

This creates a follow-on question: how does the experience layer
actually read what it needs?

Experiences need queries like:

- "Show me Agent-X's activity timeline for the last 24 hours."
- "What is Agent-X's current trust score, broken down by dimension?"
- "Which agents handled credit decisions over ₹50 lakh today?"
- "Give me the audit trail for transaction T-789, signed and exportable."
- "Show me all anomalies flagged in the last hour, grouped by use case."
- "Which agents have a stale baseline (no activity in >7 days)?"

The naive approach — query the event log directly with SQL or filters
at read time — fails on three counts:

1. **Performance.** A query like "current trust score" requires
   aggregating potentially thousands of events per agent. Doing this
   at read time, every time, doesn't scale.

2. **Coupling.** Every experience that reads events directly couples
   tightly to the event schema. Schema evolution becomes hard.

3. **Composition.** Real experience queries cross multiple event
   types (trust events + activity events + policy events). Joining
   these at read time is expensive and complex.

The well-known answer is read-side projections: materialized views
maintained incrementally as events arrive. The substrate emits events;
projection builders consume those events and update projection tables;
experiences query the projection tables.

The remaining design questions: where do projections live structurally,
who builds them, when do they update, and how do we handle the case
where a new projection needs to backfill from historical events.

## Decision

**Projections live under `kavach/query/projections/`** as a top-level
substrate concern, parallel to `kavach/capabilities/` and
`kavach/events/`. They are NOT inside any capability. This is
deliberate: projections are cross-capability views of the event stream,
and putting them inside a capability would couple them to that
capability's lifecycle.

**Each projection is a module declaring:**

1. The set of event types it consumes
2. The projection table(s) it maintains
3. The handler function that updates the projection given an event
4. The (optional) rebuild function that replays history from scratch

A sketched shape:

```python
# kavach/query/projections/agent_trust_current.py — sketch
@projection
class AgentTrustCurrentProjection:
    """Current trust score per agent, by dimension."""

    consumes = {
        TrustAssessmentEmitted,
        AgentRetired,
    }
    tables = ["agent_trust_current"]

    async def handle(self, event: DomainEvent, conn: AsyncConnection) -> None:
        if isinstance(event, TrustAssessmentEmitted):
            await conn.execute(
                "INSERT INTO agent_trust_current (agent_id, dimensions, ...) "
                "VALUES (...) ON CONFLICT (agent_id) DO UPDATE ..."
            )
        elif isinstance(event, AgentRetired):
            await conn.execute(
                "DELETE FROM agent_trust_current WHERE agent_id = ..."
            )

    async def rebuild(self, conn: AsyncConnection) -> None:
        """Replay all relevant historical events from scratch."""
        # Implementation: walk events table chronologically, dispatch to handle().
```

**Projections are updated synchronously by default, asynchronously by
exception.** When a capability emits an event, the projection update
runs in the same database transaction. This guarantees that immediately
after a capability commits, any projection reading the event sees a
consistent view. The simplicity is worth the small latency cost at our
scale.

For projections that are expensive (e.g., a rolling aggregate over
millions of events), the projection can opt out of synchronous updates
and use a background worker that consumes from an event outbox. This
is the exception, not the default. We will not optimize prematurely;
the first projections (W01-S03+) are synchronous.

**Projection rebuilds are part of the projection's API.** Every
projection ships with a `rebuild()` method that walks the events table
chronologically and replays the projection from scratch. This is what
makes "add a new projection later" feasible: the projection backfills
itself from history. It also serves as disaster recovery — if a
projection table is corrupted, rebuild reconstitutes it from the
authoritative event log.

**Projections are not the source of truth.** The event log is. If a
projection disagrees with the event log, the projection is wrong by
definition. Tests assert this directionally: projection tests are
"given this event stream, the projection table looks like this," not
the other way around.

**Schemas for projection tables are managed via Alembic migrations**,
just like any other Postgres schema. The fact that projection content
is derivable from events does not exempt projection tables from
normal migration discipline.

## Consequences

**Positive:**

- **Experience-layer queries are fast.** Reading a materialized
  projection table is a normal Postgres query, indexed and tuned like
  any other. The expensive aggregation work happened at event ingest,
  not at read time.

- **Decoupling.** Experiences read projection tables, not events. The
  event schema can evolve (per ADR-0010) without breaking experiences,
  as long as projection builders are updated to translate new event
  versions into the same projection shape.

- **New views are cheap.** Adding "show me agents with a stale
  baseline" is a new projection that consumes existing events plus
  a clock tick. No capability changes, no event schema changes; just
  a new module under `kavach/query/projections/` and a migration for
  the new projection table.

- **Time travel and audit reconstruction work.** A "what did the
  system look like at time T" projection replays events up to T and
  produces the same state the system actually had. This is exactly
  what compliance audits and post-hoc inspectors need.

- **Disaster recovery is replay.** If a projection table is lost or
  corrupted, `rebuild()` recreates it from the event log. The event
  log itself is what backups focus on.

- **Sub-product extraction (ADR-0011, Block D.3) becomes
  straightforward.** A standalone Audit sub-product, for instance,
  bundles its own projections (audit-chain timelines, compliance
  export views) and consumes events from the substrate's event bus.

**Negative:**

- **Two places store related data.** The events table stores
  history; projection tables store current views. Disk usage roughly
  doubles for data that lives in both. We accept this; storage is
  cheap, projection performance is valuable.

- **Projection consistency depends on event handler correctness.** A
  bug in a projection handler can produce a wrong view. Mitigation:
  projection tests assert "given event stream, projection table looks
  like this"; integration tests run real event sequences through real
  projection handlers.

- **Synchronous projection updates extend write latency.** Each
  emit-event-and-update-projection becomes a slightly longer
  transaction. At our scale this is fine; it would not be fine for a
  high-volume event source like a trading exchange where microseconds
  matter. Mitigation: that scale isn't our target; we use background
  workers for the rare expensive projection.

- **Schema migration discipline doubles.** Capability state has
  Alembic migrations; projection tables have Alembic migrations too.
  The CI integration suite must exercise both. We accept this.

- **The "projections aren't source of truth" rule must be defended.**
  The temptation to fix a wrong projection by editing the projection
  table directly is real. The right fix is: find the bug in the
  projection handler, fix it, run `rebuild()`. The engineering
  handbook (W01-S02 Block E) documents this explicitly.

## Alternatives Considered

- **Query the event log directly at read time.** Rejected for the
  performance and coupling reasons in Context. Some experience views
  may still query the event log directly for genuinely
  audit-/inspector-style use cases where reading the full event
  stream is the point; those queries don't go through projections.

- **Use a separate analytical database (ClickHouse, DuckDB,
  Snowflake) for read-side queries.** Considered. Rejected at current
  scale: Postgres handles our projection volume fine, and a second
  database doubles operational burden. Revisit when projection
  workloads reach scale where Postgres becomes a bottleneck.

- **Materialized views (Postgres native).** Considered for some
  projections. Rejected as the general pattern because materialized
  views are coarse-grained (refresh the whole view) where projection
  handlers are fine-grained (update only what changed). Postgres
  materialized views are a fine implementation choice for specific
  projections that fit the all-at-once refresh model; we don't
  preclude using them for those cases.

- **Use CQRS framework libraries (e.g., eventsourcing.dev).**
  Considered. Rejected because the existing libraries bring more
  ceremony than we need, and the projection pattern we want is
  small enough to implement directly. Revisit if the homegrown
  approach starts duplicating library functionality.

## References

- ADR-0001 — Three-layer architecture
- ADR-0007 — Modular capability architecture (capabilities emit
  events; projections live outside capabilities)
- ADR-0008 — Events as the substrate's primary output (the event
  stream projections consume)
- ADR-0010 — Event schema versioning (projection builders must handle
  versioned events)
- ADR-0011 (Block D.3) — Sub-product extraction (extracted sub-products
  bring their projections along)
- `kavach/query/projections/` directory established in W01-S02 Block B.1
- `docs/engineering-handbook.md` (planned, W01-S02 Block E) — projection
  discipline including the "events are source of truth, projections
  are derivative" rule
