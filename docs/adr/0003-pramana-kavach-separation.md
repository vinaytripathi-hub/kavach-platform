# ADR-0003 — Pramana–Kavach IP separation

**Status:** Accepted
**Date:** 2026-05-24

## Context

Aurvia Global owns both:

- **Pramana Protocol** — open-source agent identity infrastructure
  (W3C DIDs, Verifiable Credentials, AP2 commerce, delegation chains,
  hash-chained audit primitives). Licensed under AGPL-3.0. Repository:
  https://github.com/vinaysflow/pramana-protocol. PyPI distribution:
  `aurvia-pramana` (Python import name: `pramana`).
- **Kavach Platform** — proprietary BFSI commercial layer (this
  repository). Licensed as "All Rights Reserved." Repository:
  https://github.com/vinaysflow/kavach-platform (private).

Two strategic goals are in tension here:

1. **Pramana must be a credible open-source substrate.** That means
   genuine community usability, no "internal version that's better
   than the public version" trick, and a license (AGPL-3.0) strong
   enough that downstream commercial users coordinate with Aurvia
   rather than competing.
2. **Kavach must be cleanly proprietary.** That means no AGPL
   contamination, no question about who owns the Kavach IP, no
   ambiguity for investors or partners about what is sellable and
   what is open.

Naive approaches that fail:

- **Vendoring Pramana source into Kavach.** Triggers AGPL distribution
  obligations on Kavach. Defeats the whole separation.
- **Forking Pramana privately.** Splits engineering effort, weakens
  the public substrate's credibility, and creates an internal-version
  vs public-version trust gap.
- **Keeping everything proprietary.** Loses the community-substrate
  positioning that makes Aurvia more than just another BFSI vendor.

## Decision

A strict, explicit, documented IP boundary between Pramana and Kavach.

**Three operational rules:**

1. **Kavach contains no Pramana source code.** All Pramana
   functionality is consumed through the public Python SDK boundary
   (`import pramana`).
2. **Pramana is developed in the Pramana repository.** Improvements,
   bug fixes, and new features go upstream to Pramana, where the
   community can see and use them. Aurvia's commitment to public
   substrate quality is demonstrated by where the work lands.
3. **Kavach depends on a specific published Pramana version.** The
   dependency is declared in `pyproject.toml` as
   `aurvia-pramana>=0.3.0,<1.0.0` (current). Production deployments
   use a pinned version via the lockfile (when established in W01-S03+).

**Development pattern — "Pattern B editable install":**

During day-to-day development, the developer has both repos checked
out side-by-side at `~/Documents/Pramana-protocol/` and
`~/Documents/kavach-platform/`. The `scripts/dev-setup.sh` bootstrap
installs the formal `aurvia-pramana` dependency from PyPI as declared
in `pyproject.toml`, then overrides it with
`uv pip install -e ../Pramana-protocol/sdk/python` (editable install
from local source).

Effect: edits to Pramana source are immediately visible in Kavach
without rebuild or reinstall. The fast feedback loop is preserved
while the IP boundary remains formally intact: production uses the
PyPI dependency; development uses the editable override.

Use cases for Kavach code accessing Pramana:

- **In-process function calls** for the bulk of the SDK
  (`pramana.credentials`, `pramana.delegation`, `pramana.identity`,
  hash-chain math, validation, signing). These are pure Python, fast,
  and require no network. This is the dominant pattern.
- **Network calls** via the SDK's client classes (e.g.,
  `pramana.client.PramanaClient`, `pramana.idp.client.IDPClient`) for
  Pramana services that genuinely run as separate processes (IDP
  gateway, trust registry queries). The SDK hides the HTTP under method
  calls.

Both flavors are `import pramana`. The boundary is the import; the
mechanism beneath is hidden.

## Consequences

**Positive:**

- AGPL contamination risk is contained to Pramana itself. Kavach's
  proprietary license is defensible because Kavach contains no AGPL
  code, only references AGPL code via a public interface.
- The NOTICE file at the Kavach repo root accurately states "Kavach
  Platform contains NO Pramana Protocol source code." This is
  durable, not aspirational.
- Pramana's open-source credibility is maintained. The public version
  is the only version. There is no internal fork.
- Engineering effort on shared concerns goes upstream to Pramana,
  improving the public substrate over time. The community benefits;
  Aurvia retains the strategic advantage of being the largest and
  most authoritative Pramana contributor.
- The Pattern B editable install keeps the developer feedback loop
  fast while honoring the formal boundary.

**Negative:**

- Cannot make a Pramana-improving fix from inside the Kavach repo.
  Every cross-repo change requires two commits: one in Pramana, one
  in Kavach. For solo-founder velocity this is acceptable; for a
  scaled team it is a discipline cost worth paying.
- A Pramana breaking change can break Kavach. Mitigation: Kavach's
  dependency constraint caps at `<1.0.0` for the 0.x series; once
  Pramana ships 1.0 stable, the cap becomes `<2.0.0`. Major version
  bumps are gated by explicit Kavach validation.
- The boundary discipline must be defended in code review. The
  temptation to "just copy this one Pramana function into Kavach for
  a small tweak" is real. The engineering handbook (W01-S02 Block E)
  documents this prohibition explicitly.

## Alternatives Considered

- **Vendoring Pramana into Kavach.** Triggers AGPL distribution
  obligations on Kavach itself, contradicting the proprietary licensing
  posture. Rejected.
- **Forking Pramana privately as `aurvia-pramana-internal` with
  unpublished improvements.** Splits engineering, weakens the public
  substrate, creates a trust gap, and risks accidental cross-pollination
  in code review. Rejected.
- **Making Pramana commercially licensed (BSL or dual-license with
  paid commercial tier).** Tempting for revenue capture, but undermines
  the open-source substrate credibility that the strategy depends on.
  Rejected for the 0.x series; revisitable at 1.0 if the community
  posture justifies it (it almost certainly will not).
- **MIT-licensing Pramana instead of AGPL.** MIT permits downstream
  commercial use without coordination, which means competitors can
  build BFSI products on Pramana without engaging Aurvia. AGPL forces
  commercial redistributors to either open-source their work or
  negotiate a commercial license with Aurvia — a stronger strategic
  position. Rejected MIT in favor of AGPL after W01-S01 deliberation.

## References

- W01-S01 commit `3c7fbc6` on Pramana — initial AGPL-3.0 relicense
- W01-S02 commit `10a05f8` on Pramana — SDK distribution rename to
  `aurvia-pramana`, version 0.3.0
- W01-S02 commit `5d9bf6f` on Kavach — dependency declaration and
  Pramana-resolution smoke test
- ADR-0001 — Three-layer architecture
- LICENSE and NOTICE files at this repository root
- `docs/ip-provenance.md` (added in W01-S02 Block E) — full legal and
  architectural analysis of the boundary
