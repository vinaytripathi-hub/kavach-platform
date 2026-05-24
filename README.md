# Kavach Platform

**Agent Accountability for Indian BFSI**

Proprietary platform for the Banking, Financial Services, and Insurance
sector. Built on [Pramana Protocol](https://github.com/vinaysflow/pramana-protocol)
(AGPL-3.0 open-source substrate).

---

## What this repo is

The Kavach Platform is the **commercial layer** Aurvia Global offers to
BFSI enterprises. It transforms Pramana's identity and credentials
primitives into business outcomes for three Tier-A use cases:

- **Customer Service** — agent-driven KYC, complaint resolution, account
  operations.
- **Credit Underwriting** — AI-assisted credit decisioning with full
  audit trail and cryptographic evidence.
- **Trading** — broker / PMS agent supervision and pre-trade controls.

This is the foundation work (W01). The Kavach Platform is in active
construction; this README will evolve as architecture, infrastructure,
and use cases land.

---

## Architecture (overview)

Kavach is built in three layers atop the Pramana substrate:

1. **Substrate (capabilities + events + composition)** — the shared
   engine that all use cases consume. Modular, event-driven, designed
   for extensibility and sub-product extraction.
2. **Use Case Configs** — declarative specifications per use case.
3. **Experiences** — operator console, post-hoc inspector, customer
   surfaces.

Architectural decisions are documented as ADRs under `docs/adr/`. The
foundational ADRs (numbered 0001-0014) will be added in subsequent
W01-S02 blocks.

---

## Development setup

### Prerequisites

- Python 3.11 or 3.12
- Git configured with a GPG signing key
- Pramana checkout at `~/Documents/Pramana-protocol/` for editable
  install (interim arrangement until Pramana SDK is published to PyPI)

### Bootstrap

The full development bootstrap (virtual environment, editable install,
pre-commit hooks, smoke tests) will be provided by `scripts/dev-setup.sh`,
added in a subsequent W01-S02 block. For now, the repository contains
only legal and identity documentation.

---

## Repository structure (planned)

The full structure will be populated across W01-S02 blocks. The
target layout is:

```
kavach-platform/
├── docs/
│   ├── adr/                         # Architecture Decision Records
│   ├── cla/                         # CLA templates for Pramana contributors
│   ├── ip-provenance.md             # Pramana-Kavach IP separation analysis
│   └── engineering-handbook.md      # TDD, code review, branching, observability
├── kavach/
│   ├── events/                      # Event taxonomy, bus, persistence
│   ├── capabilities/                # Modular capabilities (audit, policy, etc.)
│   ├── composition/                 # Capability wiring
│   ├── query/                       # Read-side projections over events
│   ├── usecases/                    # Per-use-case configs
│   └── experiences/                 # UI surfaces (Week 9+)
├── tests/                           # Test suite mirroring source tree
├── scripts/                         # Dev/ops scripts
├── .github/workflows/               # CI workflows
├── pyproject.toml                   # Project metadata, deps, tool config
├── LICENSE                          # Proprietary, all rights reserved
├── NOTICE                           # Attribution
└── README.md                        # This file
```

---

## Licensing

- **Kavach Platform** (this repository): **Proprietary, all rights
  reserved.** See [LICENSE](LICENSE).
- **Pramana Protocol** (foundational dependency): GNU AGPL-3.0. See
  https://github.com/vinaysflow/pramana-protocol.

For commercial Pramana licenses (an alternative to AGPL-3.0
obligations): vinay@aurviaglobal.com.

---

## Status

W01 foundation work in progress. This commit (Block A of W01-S02)
establishes legal and identity documentation only. Subsequent blocks
add project skeleton (Block B), architectural ADRs (Blocks C and D),
and the events infrastructure plus operational artifacts (Block E).

---

## Confidentiality

This repository is **private**. Source code, ADRs, designs, and
discussions in this repository are confidential to Aurvia Global. Do
not share, fork to a public namespace, or discuss publicly without
explicit written authorization from Vinay Tripathi.
