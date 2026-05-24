# ADR-0011 — Sub-product extraction posture

**Status:** Accepted
**Date:** 2026-05-24

## Context

Per ADR-0001, Kavach Platform is structured as substrate + use cases +
experiences. Per ADR-0007, the substrate decomposes into capabilities
with formal extension points. Per ADR-0008, capabilities communicate
through events.

This raises a strategic question: are these capabilities also
*products*?

Not all are. Some capabilities (the audit ledger, the policy engine,
the operator console) solve problems that exist independently of the
BFSI agent accountability use case. A bank's CISO who is not deploying
Kavach Platform may still want a tamper-evident audit ledger for
human-operator activity. A compliance team may want a policy engine
they can configure without buying the full platform.

Other capabilities (the enrichment capability, the DPI bridge, the
SDK glue) are inherently coupled to the Kavach product. They make
sense only as part of the larger system.

The question matters because:

1. **Optionality.** If certain capabilities can be packaged as
   standalone sub-products, Aurvia has multiple revenue paths from
   the same substrate investment. A standalone "Audit-as-a-Service"
   product reaches a different buyer than the full platform.

2. **Architectural discipline.** Designing for extractability imposes
   constraints on the capability — stricter boundary discipline,
   no implicit cross-capability dependencies, a self-contained
   data model. These constraints make the capability *better*
   regardless of whether extraction ever happens.

3. **Investor narrative.** A platform with credible standalone
   sub-products has a stronger story than a monolithic platform
   that does one thing. The discipline today preserves the option
   even if Aurvia never exercises it.

4. **Risk management.** If the BFSI agent accountability thesis turns
   out to be wrong (regulators relax, partners delay, agents don't
   proliferate as expected), having capabilities that can be sold
   into adjacent markets is genuine optionality.

Designing every capability for extraction is overkill and slows the
build. Designing none of them for extraction forecloses the optionality.
The right answer is a deliberate posture per capability, declared
explicitly, designed for accordingly.

## Decision

**Capabilities are classified by extraction potential into three
postures:**

### High-extractability capabilities

These capabilities are explicitly designed to be packageable as
standalone Aurvia sub-products. They follow stricter discipline:

- **Audit capability** (`kavach/capabilities/audit/`). A tamper-evident,
  hash-chained audit ledger has standalone value for compliance teams,
  internal audit functions, and any organization storing
  evidence-grade activity records. Standalone target: "Aurvia Audit"
  or similar branding; deployment as an SaaS or self-hosted package
  consumed via an SDK and a console.

- **Policy capability** (`kavach/capabilities/policy/`). A
  declarative policy engine with evidence-carrying decisions has
  standalone value for any team that needs configurable rule
  evaluation with audit trails. Standalone target: a policy
  evaluation service that integrates with arbitrary business
  systems via SDK and webhooks.

- **Operator Console experience** (`kavach/experiences/console/`).
  A multi-tenant operator console showing real-time activity,
  trust scores, and override workflows has standalone value
  beyond BFSI. Standalone target: a console product for any
  vertical where human operators supervise automated systems.

Design discipline for high-extractability capabilities:

1. **No implicit dependencies on other Kavach capabilities.** All
   inter-capability dependencies go through Protocol declarations
   in `contracts.py` (per ADR-0007). The composition layer wires
   them; the capability itself does not import other capabilities.

2. **Self-contained data model.** All tables the capability requires
   are owned by the capability. No foreign keys into other
   capabilities' tables. Cross-capability associations happen by
   ID-reference in events, not by relational joins.

3. **Self-contained event vocabulary.** The capability emits and
   consumes a coherent event vocabulary that makes sense in
   isolation. If extracted, the standalone deployment exchanges
   events with whatever the consumer system is, not with the full
   Kavach event log.

4. **Independent versioning posture.** When the capability is
   extracted into a sub-product, that sub-product will have its
   own version stream, separate from Kavach Platform's. The
   capability code is designed to support both modes: integrated
   into Kavach (sharing Kavach's version stream) and extracted
   (with its own).

5. **Public API documented separately.** Each high-extractability
   capability gets its own `docs/capabilities/<name>/` directory
   in the longer arc, containing API documentation written for the
   standalone audience, not for the integrated audience.

### Low-extractability capabilities

These capabilities are inherently coupled to the Kavach product;
extracting them as standalone products would not make commercial
sense.

- **Enrichment capability** (`kavach/capabilities/enrichment/`).
  Augments agent activity with KYC context, behavioral baselines,
  and risk signals. Useful as part of Kavach; not a coherent
  standalone product because the augmentation pipeline assumes
  a multi-capability substrate.

- **DPI bridge capability** (`kavach/capabilities/dpi_bridge/`).
  Integrates with India's Digital Public Infrastructure
  (Aadhaar, DigiLocker, Account Aggregator, UPI). Has value
  only inside an Indian BFSI deployment; the integration semantics
  are tightly coupled to BFSI use cases.

- **SDK bridge capability** (`kavach/capabilities/sdk_bridge/`).
  Mediates between Kavach internals and the Pramana SDK. Inherently
  coupled to both repos.

Design posture: still follow ADR-0007's modular architecture, but
do not pay the additional cost of strict cross-capability dependency
discipline if it conflicts with reasonable internal design choices.
We accept these capabilities as Kavach-only.

### Mixed-extractability components

Some components don't fit cleanly into either category:

- **Storage capability** (`kavach/capabilities/storage/`). Provides
  shared persistence primitives. Inherently part of any deployment
  but might end up factored differently depending on how high-
  extractability capabilities are packaged.

- **Composition layer** (`kavach/composition/`). Inherently
  Kavach-deployment-specific; not extracted, but a thin equivalent
  exists in any standalone sub-product deployment.

- **Events package** (`kavach/events/`). The base event taxonomy
  is shared; high-extractability sub-products bring their own
  capability-specific events but consume the shared
  `kavach.events.DomainEvent` base.

These are treated case-by-case. The default is: stay integrated;
factor only if a specific extraction reveals the seam.

## Consequences

**Positive:**

- **Optionality is preserved.** Even if Aurvia never extracts a
  sub-product, the discipline imposed by designing for extractability
  makes high-extractability capabilities better-isolated and easier
  to refactor.

- **The investor narrative gets concrete examples.** "Audit-as-a-Service"
  and "Policy-as-a-Service" are not speculative bullet points; they
  are capability boundaries already documented as standalone-ready.

- **Sub-product extraction is a strategic decision, not an engineering
  excavation.** If Aurvia decides to extract Audit as a standalone
  product in 2027, the work is: package the capability with its
  contracts, build a standalone composition layer, wrap in deployment
  tooling. Months, not years.

- **Strict discipline on the right capabilities, freedom on the
  others.** The cost of cross-capability dependency discipline is
  paid only where it earns optionality. Enrichment and DPI bridge
  don't pay it.

- **Risk hedging.** If the BFSI agent accountability thesis weakens,
  Aurvia has multiple capability-level products to fall back on,
  each with its own market.

**Negative:**

- **The "high-extractability discipline" is a real cost.** Audit,
  Policy, and Console pay ~15-25% more in code volume than they
  would with tight cross-capability coupling. The bet is that this
  cost is repaid by optionality.

- **The classification can be wrong.** A capability we classify as
  low-extractability might turn out to have standalone value we
  didn't anticipate. Mitigation: this ADR is revisitable; if a
  capability's extraction potential changes, we upgrade its
  discipline accordingly.

- **Cross-capability optimization is harder.** A clever optimization
  that involves a shortcut between two high-extractability
  capabilities is forbidden by the discipline. We accept the local
  performance cost in exchange for the global structure.

- **New engineering hires must understand the classification.**
  Why is the audit capability written with stricter discipline than
  enrichment? Because of this ADR. The engineering handbook
  (W01-S02 Block E) documents the classification and the rationale.

## Alternatives Considered

- **Everything is high-extractability.** Considered. Rejected
  because the discipline cost on capabilities that genuinely have
  no standalone market (DPI bridge, enrichment) is wasted effort.
  Better to focus the discipline where it earns optionality.

- **Nothing is high-extractability; build a monolithic platform.**
  Considered. Rejected because it forecloses real strategic
  optionality and produces a worse-architected substrate even
  inside Kavach. The high-extractability discipline makes audit
  and policy better even if they are never extracted.

- **Wait to decide.** Defer extraction posture to "when it's
  needed." Rejected because the discipline is hard to retrofit;
  a capability that grew up tightly coupled to others is expensive
  to disentangle. Designing for extraction is cheap in the design
  phase, expensive in the refactor phase.

- **Microservice from the start.** Build each high-extractability
  capability as a separate service. Rejected per ADR-0001's
  reasoning: operational cost is not justified at solo-founder scale,
  and the in-process Protocol-based discipline gives most of the
  benefit at a fraction of the cost.

## References

- ADR-0001 — Three-layer architecture
- ADR-0007 — Modular capability architecture (the structural
  discipline that high-extractability capabilities follow strictly)
- ADR-0008 — Events as primary output (extracted sub-products
  consume and produce events with the same discipline)
- ADR-0010 — Event schema versioning (cross-deployment event
  contracts require versioning rigor)
- ADR-0014 (Block D.4) — Multidimensional trust substrate
  (a high-extractability capability in the long arc)
- `docs/capabilities/<name>/` directories established in W01-S03+
  for each high-extractability capability
- `docs/engineering-handbook.md` (planned, W01-S02 Block E) —
  classification of each capability and the discipline expected
