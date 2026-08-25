# Architecture Decision Records (ADRs)

This directory holds the foundational architectural decisions for the
Kavach Platform. Each ADR documents a single decision, the context that
produced it, the alternatives considered, and the consequences accepted.

ADRs are immutable once merged. If a decision is later superseded, a new
ADR is added that references the prior one and changes its status to
`Superseded by ADR-NNNN`. The original ADR is not edited (beyond status
metadata).

## Why ADRs

Several reasons:

- **Onboarding.** When a new engineer joins, they read ADRs in numerical
  order and understand why the system is the way it is, not just how it
  is. This is faster and more accurate than archaeology through git
  history.
- **Audit and compliance.** BFSI partners, regulators, and security
  auditors routinely ask "why did you choose X over Y?" ADRs provide a
  written answer at the time the decision was made, not a
  rationalization after the fact.
- **Investor diligence.** Strategic decisions (positioning, IP
  separation, data residency) are reviewable through ADRs without
  requiring a verbal walk-through.
- **Founder discipline.** Writing the decision down forces the founder
  and CTO to articulate trade-offs explicitly. Vague intuitions become
  legible commitments.

## Format

Each ADR has these sections:

- **Status** — Proposed / Accepted / Superseded by ADR-NNNN / Deprecated.
- **Date** — When the decision was made (not when it was written down).
- **Context** — What problem or question prompted this decision.
- **Decision** — What we are doing.
- **Consequences** — What this commits us to. Both positive and negative.
- **Alternatives Considered** — Other options we evaluated, with the
  specific reason each was rejected. Future ADRs that reverse an earlier
  decision should reference back to the relevant Alternatives section.
- **References** — Links to related ADRs, external sources, prior
  discussions, or supporting evidence.

## ADR Numbering

ADRs are numbered sequentially starting at 0001. Numbers are never
reused, even for superseded ADRs. When an ADR is superseded, its status
metadata is updated but its file remains and its number is preserved.

## Current ADRs

| Number | Status | Title |
|-------:|--------|-------|
| 0001 | Accepted | Three-layer architecture (substrate / use cases / experiences) |
| 0002 | Accepted | Substrate-first build order |
| 0003 | Accepted | Pramana–Kavach IP separation |
| 0004 | Accepted | Self-hosted Postgres 16 on Yotta Yntraa for data residency |
| 0005 | Accepted | "Accountability for BFSI agents" market positioning |
| 0006 | Accepted | TDD as the engineering default |
| 0007 | Accepted | Modular capability architecture with formal extension points |
| 0008 | Accepted | Domain events as the substrate's primary output |
| 0009 | Accepted | Read-side projections over the event stream |
| 0010 | Accepted | Event schema versioning and stability |
| 0011 | Accepted | Sub-product extraction posture |
| 0012 | Accepted | Decision events carry evidence, reasoning, and confidence |
| 0013 | Accepted | Multimodal data sufficiency |
| 0014 | Accepted | Multidimensional trust substrate |
| 0015 | Accepted | Pramana SDK packaging and AGPL posture for on-prem distribution |
| 0016 | Accepted | External API surface, contract, and versioning |
| 0017 | Accepted | On-prem deployment posture (Docker Compose first) |

ADRs 0001–0014 cover the foundational and advanced architectural
commitments for Kavach Platform's substrate and product positioning,
produced in W01-S02 across Blocks C and D. ADRs 0015–0017 were added
in the W01-S03+ working-prototype build: Pramana SDK packaging, the
external HTTP API contract, and the on-prem deployment posture.
Subsequent ADRs (0018 and beyond) will be added as new architectural
decisions arise.

## Adding a new ADR

1. Pick the next available number (one higher than the highest existing).
2. Create `NNNN-short-kebab-case-title.md` in this directory.
3. Use the section structure described above.
4. The ADR ships in its own GPG-signed commit, with a commit message
   subject of the form `ADR-NNNN: <Title>`.
5. Update the "Current ADRs" table in this README in the same commit.
