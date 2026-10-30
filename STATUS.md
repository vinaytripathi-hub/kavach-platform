# Kavach Platform — Status

_Agent accountability for Indian BFSI. Proprietary, source-available._

**Last updated:** 2026-10-30 · **Latest release:** `v0.0.1`

---

## TL;DR

| | |
|---|---|
| **Working prototype (Phase 1)** | **Shipped** — substrate, `/v1` API, Customer Service use case, operator console, on-prem Docker packaging |
| **SDK packaging + publish (Phase 1.5)** | **CLOSED** — `aurvia-kavach` live on PyPI and `@aurvia/kavach` live on npm (both `0.0.1`), published from CI with Trusted Publishing / provenance and verified by a clean-room install from the live registries running the full accountability loop. See [gate-closure evidence](docs/guides/phase-1.5-gate-closure.md). |
| **Tests** | 163 collected — **159 unit/integration passing**, 2 Postgres-integration skipped (need `KAVACH_DATABASE_URL`), 2 e2e deselected from the push gate; TS SDK **15 contract tests** passing |
| **Coverage** | **85.44%** (push gate: 70%) |
| **ADRs** | **19** — see [`docs/adr/README.md`](docs/adr/README.md) |
| **License** | Proprietary, source-available ([LICENSE](LICENSE), [NOTICE](NOTICE)); built on the AGPL-3.0 Pramana Protocol via its public SDK only |

## NIST agentic-IAM scorecard (6 / 3 / 1)

Crosswalk against the NIST 10-tenet agentic IAM model
([full mapping](docs/compliance/nist-agentic-iam-mapping.md)):

| Disposition | Count | Tenets |
|---|---|---|
| **Implemented** | 6 | 05, 06, 07, 08, 09, 10 |
| **Partial** | 3 | 01, 02, 03 |
| **Weak** | 1 | 04 |

Standards alignment also tracked for AP2, Mastercard Verifiable Intent, and the
FIDO agentic work ([FIDO/AATWG mapping](docs/compliance/fido-agentic-standards-mapping.md)).

## Distribution

| Package | Registry | Status |
|---|---|---|
| `aurvia-kavach` (Python, import `kavach`) | [PyPI](https://pypi.org/project/aurvia-kavach/0.0.1/) — Trusted Publishing (OIDC) + attestations | **Published `0.0.1`** |
| `@aurvia/kavach` (TypeScript) | [npm](https://www.npmjs.com/package/@aurvia/kavach/v/0.0.1) — `--provenance` | **Published `0.0.1`** |

```bash
pip install aurvia-kavach        # Python 3.11–3.13, import kavach
npm install @aurvia/kavach       # Node 18+
```

Publish is CI-driven: a signed `v*` tag runs the build + smoke-install matrix +
TestPyPI/npm dry-runs; a published GitHub Release pushes to PyPI and npm. See
[`.github/workflows/publish-python.yml`](.github/workflows/publish-python.yml)
and [`.github/workflows/publish-npm.yml`](.github/workflows/publish-npm.yml).

## More

Overview: [`README.md`](README.md) · Roadmap: [`docs/roadmap.md`](docs/roadmap.md) ·
ADR index: [`docs/adr/README.md`](docs/adr/README.md) ·
Phase 1.5 evidence: [`docs/guides/phase-1.5-gate-closure.md`](docs/guides/phase-1.5-gate-closure.md)
