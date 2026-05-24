# ADR-0002 — Substrate-first build order

**Status:** Accepted
**Date:** 2026-05-24

## Context

Given the three-layer architecture (ADR-0001), there are three
defensible build orders:

1. **Substrate-first.** Build the shared engine before any use case
   exists. Then build the first use case as a thin config over the
   substrate. Then build the first experience surface.
2. **Use-case-first.** Build one complete use case end-to-end
   (substrate + use case + experience), prove value, then extract the
   substrate by refactoring shared pieces out as the second use case
   lands.
3. **Experience-first.** Build the operator console with mocked data,
   prove that the surface is right, then back-fill the substrate.

Each has trade-offs. The decision matters because in a solo-founder
phase with limited weekly hours, build-order mistakes compound.

## Decision

Build the substrate first.

Specifically, the W01–W08 plan is:

- **W01–W04** — Substrate capabilities, events infrastructure, composition,
  projections. End state: a working substrate with audit, policy,
  enrichment, DPI, and storage capabilities; the event log persists and
  can be queried; basic projections produce trust scores and timelines.
- **W05–W06** — First use case (Customer Service). Built as a config
  over the substrate, exercising it end-to-end. Forces substrate
  refinement where reality diverges from plan.
- **W07–W08** — Operator console (first experience). Reads from
  substrate projections. Demonstrates the full three-layer story.

Subsequent use cases (Credit Underwriting, Trading) follow in
W09–W10, by which point the substrate's shape is stable.

## Consequences

**Positive:**

- Forces clarity on what the substrate is and is not. By the time the
  first use case lands, the boundary between substrate and use case is
  already exercised by code in the substrate, not by guesswork.
- Avoids the "substrate that's just one use case's leftovers" failure
  mode that use-case-first builds frequently produce.
- The investor and partner narrative is clearer: "Aurvia builds the
  trust infrastructure; the use cases are the wedge into BFSI." That
  narrative requires the substrate to exist as a recognizable thing
  before the use cases are built on top.

**Negative:**

- The first 6–8 weeks produce no use-case-visible output. The substrate
  exists, has tests, has a console preview at best, but no BFSI partner
  could pilot it yet. This is hard for a solo founder under pressure to
  show progress.
- Risk of over-engineering the substrate. Without a real use case
  pulling on it, the substrate can grow features that no use case
  actually needs. Mitigation: every substrate capability built in
  W01–W04 must be explicitly justified by anticipated use-case needs,
  documented in the capability's design notes.
- The first use case (Customer Service) will surface substrate gaps and
  may require small substrate revisions. We treat W05–W06 as a
  "substrate hardening" period as much as a use case build.

## Alternatives Considered

- **Use-case-first.** Build Customer Service end-to-end, then extract
  the substrate when adding Credit Underwriting. Rejected because
  refactoring under commercial pressure is slow and risky, and BFSI
  customers typically expect the substrate to be stable before they
  trust the use case built on it. Also: a substrate extracted from one
  use case tends to encode that use case's assumptions in ways that are
  hard to undo.
- **Experience-first.** Build the operator console with mocked data,
  validate the surface with target customers, then back-fill. Rejected
  because the substrate is the moat; an attractive console over a
  weak substrate is easy to replicate. Spend the early weeks where the
  real defensibility lives.
- **Parallel substrate and use case.** A more experienced team might
  reasonably build the substrate and the first use case in tandem.
  Rejected at the solo-founder phase because the cognitive load of
  designing both simultaneously is too high; substrate decisions
  should not be biased by a single use case's immediate needs.

## References

- ADR-0001 — Three-layer architecture
- ADR-0005 — "Accountability for BFSI agents" positioning
- ADR-0006 — TDD discipline
