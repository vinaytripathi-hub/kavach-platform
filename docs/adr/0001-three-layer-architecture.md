# ADR-0001 — Three-layer architecture (substrate / use cases / experiences)

**Status:** Accepted
**Date:** 2026-05-24

## Context

Kavach Platform is the proprietary commercial layer Aurvia Global offers
to BFSI enterprises. It needs to:

1. Solve concrete, monetizable business problems for the three Tier-A
   BFSI use cases — customer service, credit underwriting, and trading
   agent supervision.
2. Share enough machinery across those use cases that adding the fourth
   (e.g., insurance underwriting, wealth advisory, fraud investigation)
   in the future is straightforward.
3. Present operator-facing and customer-facing experiences (consoles,
   inspectors, evidence exports) that consume the underlying machinery.
4. Stay disciplined about which parts can be reused versus which are
   genuinely use-case-specific, so that the system doesn't accrete into
   a tangle where every change risks every customer.

A naive monolith mixes substrate logic, use-case logic, and user-facing
surfaces. This works at very small scales and breaks rapidly as the
product matures. A naive microservice fan-out scatters logic across too
many independent services for a solo-founder phase to be tractable.

We need a middle path: a deliberate, layered architecture that supports
multiple use cases and multiple experience surfaces from a coherent
shared core, without paying the operational cost of distributed
microservices on day one.

## Decision

Kavach Platform is structured in three explicit layers:

1. **Substrate.** The shared engine: capabilities (audit, policy,
   enrichment, DPI integration, SDK bridge, storage), event taxonomy,
   composition (capability wiring), and read-side projections over the
   event stream. The substrate is what makes Kavach Kavach — the
   reusable, domain-rich machinery that every use case consumes.

2. **Use Case Configs.** Per-use-case declarative specifications: the
   rule sets, the integration endpoints, the use-case-specific
   projections, the use-case-specific event schemas. A use case
   *configures* the substrate; it does not duplicate substrate logic.
   Adding a new use case is primarily a configuration exercise, not a
   substrate rewrite.

3. **Experiences.** The user-facing surfaces: operator console, post-hoc
   inspector, regulator evidence export, customer-facing transparency
   views. Experiences consume substrate projections; they do not query
   substrate internal state directly. Frontend code lives here.

The Python package layout reflects this:

- `kavach/events/` and `kavach/capabilities/<name>/` plus
  `kavach/composition/` and `kavach/query/` — the substrate.
- `kavach/usecases/<name>/` — the use case configs.
- `kavach/experiences/<name>/` — the experiences.

Tests mirror the source tree exactly under `tests/`.

## Consequences

**Positive:**

- New use cases are predominantly config work, not new substrate work.
  The cost of expanding from three use cases to a fourth is small.
- Experiences can be added or replaced independently. A web console and
  a mobile inspector can both consume the same substrate without
  duplication.
- The substrate has a clear ownership boundary, which makes test
  discipline, coverage targets, and code review focus naturally.
- The layered separation makes "what is sellable as a standalone
  product" a tractable question. Some substrate capabilities (audit,
  policy, the operator console experience) are designed for standalone
  extractability per ADR-0011 (planned in Block D).

**Negative:**

- More discipline required than a monolith. The temptation to put
  "just one bit of use-case logic" inside a substrate capability is
  constant. Code review and ADRs guard against this.
- Some use-case-specific concerns end up duplicated across use cases
  because they don't fit cleanly into shared substrate primitives. We
  accept this duplication rather than over-generalize the substrate
  prematurely.
- Three layers means three places where the boundary discipline can
  break. Periodic architectural review (suggested quarterly) is needed
  to ensure the layers haven't quietly merged.

## Alternatives Considered

- **Monolithic single-layer.** Faster to start. Rejected because the
  three Tier-A use cases have meaningfully different policy, enrichment,
  and integration shapes; a monolith would either fail to support all
  three well, or accumulate the layered structure organically with
  worse discipline.
- **Microservice fan-out.** One service per capability, one service per
  use case. Rejected for solo-founder operational cost. Microservices
  also imply network calls between capabilities; in-process function
  calls are dramatically simpler and faster for the bulk of the
  substrate. We may extract specific capabilities into standalone
  services later (per ADR-0011 in Block D), but the default is
  in-process.
- **Substrate + experiences only (no explicit use-case layer).**
  Tempting because experiences already consume substrate projections.
  Rejected because BFSI use cases have meaningfully different rule
  sets, integrations, and outcome models. Without a formal use-case
  layer, those differences either pollute the substrate or get hidden
  inside experience code, both of which are worse.

## References

- ADR-0002 — Substrate-first build order
- ADR-0003 — Pramana–Kavach IP separation
- ADR-0007 (planned, Block D) — Modular capability architecture
- ADR-0008 (planned, Block D) — Events as the substrate's primary output
- ADR-0011 (planned, Block D) — Sub-product extraction posture
