# ADR-0007 — Modular capability architecture with formal extension points

**Status:** Accepted
**Date:** 2026-05-24

## Context

Per ADR-0001, Kavach is structured in three layers: substrate, use cases,
experiences. The substrate itself decomposes into capabilities (audit,
policy, enrichment, DPI integration, SDK bridge, storage). Without
explicit discipline, this decomposition can fail in three known ways:

1. **Tangled internal coupling.** Capabilities import each other's
   internals, leaving the substrate as a single tightly-coupled blob
   rather than a composable set of modules. Future refactoring becomes
   expensive; sub-product extraction (per ADR-0011 in Block D.3) becomes
   impossible.

2. **Public API drift.** Without an explicit declaration of what a
   capability's public surface is, every internal symbol becomes a de
   facto public API as soon as something outside the capability imports
   it. Version evolution then requires either freezing the entire
   internal structure or breaking unknown consumers.

3. **Extension impossibility.** New use cases need to plug into existing
   capabilities (e.g., a use case provides its policy rules to the
   policy capability). Without formal extension points, that plug-in
   happens through ad-hoc inheritance, monkey-patching, or conditional
   logic inside the capability — all of which compound badly.

We need a per-capability structural discipline that solves all three at
once.

## Decision

Every capability under `kavach/capabilities/<name>/` follows this
structure:

```
kavach/capabilities/<name>/
├── __init__.py          # PUBLIC API. Only re-exports here are stable.
├── _internal/           # Implementation details. Private.
│   ├── __init__.py
│   └── <impl modules>
├── events.py            # Domain events this capability emits and consumes.
├── contracts.py         # Protocol classes the capability depends on.
└── extension_points.py  # Optional. Protocols use cases implement.
```

**The five rules:**

1. **`__init__.py` is the only public surface.** Symbols re-exported from
   `__init__.py` are part of the capability's public API. Everything in
   `_internal/` is private and may change without notice.

2. **`_internal/` is private.** Modules under `_internal/` may not be
   imported from outside the capability. Code review enforces this; the
   ruff/pyflakes rules will not catch it automatically, but the engineering
   handbook (W01-S02 Block E) documents the prohibition explicitly.

3. **`events.py` declares all events emitted and consumed.** Domain events
   are the capability's primary externally-observable behavior per
   ADR-0008. Listing them in a dedicated module makes the contract
   discoverable.

4. **`contracts.py` declares dependencies as Protocol classes.** When a
   capability needs something another capability provides, it imports a
   `Protocol` (from `typing.Protocol`) describing the shape of what it
   needs, not the concrete implementation. The composition layer
   (`kavach/composition/`) wires concrete implementations to the
   Protocols at startup. This is dependency inversion.

5. **`extension_points.py` (optional) declares Protocols that use cases
   implement.** When a capability is genuinely extensible by use cases
   (e.g., the policy capability needs use-case-specific rule providers),
   it declares Protocols that use cases provide concrete implementations
   for. The composition layer wires these too.

**Composition pattern (`kavach/composition/`):**

A capability does not instantiate its dependencies. The composition
layer does. Conceptually:

```python
# kavach/composition/substrate.py — sketch, not final
def build_substrate(
    config: SubstrateConfig,
    policy_rule_providers: list[PolicyRuleProvider],
    step_up_handlers: list[StepUpHandler],
    # ...
) -> Substrate:
    storage = build_storage(config.storage)
    event_bus = build_event_bus(config.event_bus, storage)
    audit = AuditCapability(event_bus=event_bus, storage=storage)
    policy = PolicyCapability(
        event_bus=event_bus,
        rule_providers=policy_rule_providers,
        step_up_handlers=step_up_handlers,
    )
    enrichment = EnrichmentCapability(event_bus=event_bus, ...)
    # ... wire the rest
    return Substrate(audit=audit, policy=policy, enrichment=enrichment, ...)
```

The use case layer calls `build_substrate(...)` once at startup, passing
in use-case-specific implementations of extension points. The capability
code itself contains zero knowledge of which use cases exist.

## Consequences

**Positive:**

- **Capabilities are independently developable, testable, and
  refactorable.** Internal restructuring within `_internal/` does not
  affect the rest of the substrate, as long as `__init__.py`, `events.py`,
  `contracts.py`, and `extension_points.py` remain stable.

- **Sub-product extraction becomes mechanical (ADR-0011).** If
  Aurvia decides to extract Audit, Policy, or Console as a standalone
  product, the work is: package the capability with its contracts and
  extension points, provide an alternative composition layer for the
  standalone deployment. The capability code itself does not change.

- **New use cases are config work, not substrate work.** Adding a use
  case requires implementing the relevant extension point Protocols
  (e.g., a use case's `PolicyRuleProvider`), registering it with the
  composition layer, and writing the use case config. The substrate
  itself does not need modification.

- **Dependency injection makes testing tractable.** Each capability can
  be tested in isolation by passing mock implementations of its
  contracts. No global state, no test framework mocking magic, no
  service locator anti-pattern.

- **The public API is reviewable.** Anyone auditing what a capability
  exposes reads its `__init__.py`. The set of names re-exported there
  is the contract; nothing else is.

**Negative:**

- **~15-20% more code volume than a tight monolith.** Protocols,
  composition wiring, and the discipline of keeping `_internal/`
  internal have a real cost. We accept this cost because the
  alternative (no boundaries) compounds much worse as the codebase
  grows.

- **The composition layer becomes a coordination point.** Every
  capability must be wired in `kavach/composition/`. As capabilities
  multiply, the composition layer grows. Mitigation: composition is
  itself broken into per-area modules (e.g.,
  `kavach/composition/substrate.py`, `kavach/composition/usecases.py`)
  rather than a single mega-function.

- **Code review must enforce the private/public boundary.** Python does
  not have a true "private module" mechanism; the `_internal/` convention
  is a strong signal that humans honor. The engineering handbook makes
  the rule explicit; reviewers reject PRs that violate it.

- **Protocol-based contracts can be over-engineered.** Not every
  inter-capability dependency needs a full Protocol declaration. The
  discipline applies to capability-to-capability dependencies and to
  use-case-to-capability extension points; trivial helper functions
  internal to a capability do not need Protocols.

## Alternatives Considered

- **Flat capabilities (no `_internal/` distinction).** Simpler to write
  initially. Rejected because every internal symbol becomes a de facto
  public API on first external import, freezing the internal structure
  prematurely.

- **Tightly coupled capabilities (direct imports between them).**
  Simpler than Protocol-based contracts. Rejected because it makes
  sub-product extraction impossible and testing dramatically harder.

- **Microservice fan-out (one service per capability).** Provides the
  strongest isolation. Rejected per ADR-0001's reasoning: in-process
  function calls are dramatically faster and simpler at solo-founder
  scale; microservice operational cost is unjustified until a specific
  capability genuinely needs independent deployment.

- **Plugin systems via Python entry points.** Adds runtime discovery
  complexity for no current benefit. The use cases that exist are known
  at build time; explicit composition is clearer than dynamic discovery.
  Revisit if Aurvia ever ships a Kavach SDK that third parties extend
  (not currently planned).

## References

- ADR-0001 — Three-layer architecture
- ADR-0008 — Events as the substrate's primary output (this ADR's
  cousin; events are the contract, capabilities are the contract's
  producers)
- ADR-0011 (Block D.3) — Sub-product extraction posture
- `docs/engineering-handbook.md` (planned, W01-S02 Block E) — code
  review checklist for the `_internal/` boundary
