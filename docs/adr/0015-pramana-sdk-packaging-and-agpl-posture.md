# ADR-0015 — Pramana SDK packaging and AGPL posture for on-prem distribution

**Status:** Accepted
**Date:** 2026-06-12

## Context

ADR-0003 established a strict IP boundary: Kavach consumes Pramana only
through its public SDK, contains no Pramana source code, and uses a
Pattern B editable install (`pip install -e ../Pramana-protocol/sdk/python`)
during development. The runtime dependency in `pyproject.toml` is
declared as `aurvia-pramana>=0.3.0,<1.0.0`.

The on-prem working prototype (the W01-S03+ build) forces three
questions that the foundational ADRs deferred:

1. **How does Pramana reach a partner deployment?** The editable
   install assumes a local Pramana checkout. A BFSI partner running
   Kavach on their own host has no such checkout. `aurvia-pramana` is
   not yet on a public or private PyPI index.

2. **What is the AGPL-3.0 obligation when Kavach ships in a container
   alongside Pramana?** Pramana is AGPL-3.0. Kavach is proprietary.
   Bundling the two in one deployable artifact must not create a
   reciprocal-licensing obligation on Kavach's proprietary source.

3. **How does the prototype run end-to-end today, before a published
   index exists?** The substrate must be buildable and demoable now,
   not blocked on packaging logistics.

## Decision

**1. The substrate depends on a Protocol, not on `import pramana`
directly.** Per ADR-0007, the `sdk_bridge` capability declares its
dependency on Pramana as a `Protocol` (`CredentialVerifier`,
`DelegationVerifier`) in `contracts.py`. The concrete adapter that
calls `import pramana` lives in `sdk_bridge/_internal/`. No other
capability imports `pramana`. This means:

- Pramana's presence is a composition-time concern, not a
  compile-time coupling spread across the substrate.
- The prototype ships a built-in `LocalPramanaAdapter` (wrapping the
  real SDK) and a `FakeCredentialVerifier` (deterministic, no SDK
  required) selectable by configuration. Tests and offline demos use
  the fake; real deployments wire the adapter.

**2. AGPL boundary: Pramana runs as a separately-licensed process or
import consumed only via its published SDK API.** The container build
(ADR-0017) installs `aurvia-pramana` from its own distribution as an
independent dependency, exactly as it installs FastAPI or SQLAlchemy.
Kavach's proprietary code calls the SDK's public functions; it does
not link Pramana source into Kavach modules. The NOTICE file already
records this consumption-via-SDK-boundary posture; this ADR confirms
it survives containerization. The AGPL network-use clause is satisfied
by Pramana's own source availability (its public repository), not by
opening Kavach's source.

**3. Distribution mechanism: private index first, vendored wheel as
fallback.** The target is to publish `aurvia-pramana` to a private
package index (or PyPI) so the constraint
`aurvia-pramana>=0.3.0,<1.0.0` resolves normally in CI and on-prem
builds. Until that index exists, the container build vendors the
Pramana wheel built from the pinned source revision into the image's
build stage. The vendored wheel is the exact published artifact, not
a fork; this is a logistics bridge, not an IP change. Publishing the
index is tracked as a cross-repo task in the Pramana repository.

## Consequences

**Positive:**

- The prototype runs today: offline via the fake verifier, fully via
  the local editable install or a vendored wheel.
- The substrate never hard-couples to Pramana internals; swapping the
  identity root (e.g., an EUDI Wallet adapter for EU deployments) is a
  new adapter behind the same Protocol, not a substrate rewrite.
- The AGPL boundary is mechanically defensible: Kavach source contains
  no Pramana code; the SDK is consumed as an external dependency.

**Negative:**

- Two verifier implementations (real adapter + fake) must be kept in
  sync against the `CredentialVerifier` Protocol. Mitigation: the
  Protocol is small and contract-tested against both.
- The vendored-wheel bridge is operational debt until the private
  index is live. Mitigation: the wheel is the published artifact,
  reproducible from a pinned revision; the bridge is removed once the
  index exists.

## Alternatives Considered

- **Hard `import pramana` throughout the substrate.** Rejected: spreads
  the dependency, makes offline demos impossible, and couples every
  capability to Pramana's availability.
- **Re-license Kavach as AGPL to avoid the boundary question.**
  Rejected: contradicts ADR-0003 and the commercial model.
- **Reimplement the needed identity primitives inside Kavach.**
  Rejected: duplicates Pramana, violates ADR-0003's separation, and
  discards the substrate Pramana is purpose-built to be.

## References

- ADR-0003 — Pramana–Kavach IP separation
- ADR-0007 — Modular capability architecture (Protocol-based contracts)
- ADR-0017 — On-prem deployment posture (how the container installs Pramana)
- `kavach/capabilities/sdk_bridge/` — the capability this ADR governs
- NOTICE — attribution and consumption-via-SDK-boundary statement
