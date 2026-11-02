# Kavach Platform — Status

_Agent accountability for Indian BFSI. Proprietary, source-available._

**Last updated:** 2026-10-30 · **Latest release:** `v0.0.1`

---

## TL;DR

| | |
|---|---|
| **Phase 2a (NIST tenet 04)** | **CLOSED** — session credentials, credential-family revocation, and holder re-verification on refresh. Re-checked on SQLite and Postgres 16: a revoked credential's refresh tokens return `401 credential_revoked` and do not mint a new session. |
| **Working prototype (Phase 1)** | **Shipped** — substrate, `/v1` API, Customer Service use case, operator console, on-prem Docker packaging |
| **SDK packaging + publish (Phase 1.5)** | **CLOSED** — `aurvia-kavach` live on PyPI and `@aurvia/kavach` live on npm (both `0.0.1`). See [gate-closure evidence](docs/guides/phase-1.5-gate-closure.md). |
| **Tests** | **176 unit passing**; Postgres integration passing (full flow, mandate revocation, credential-family refresh); 2 e2e passing. Live Keycloak test still skips without an issuer. |
| **Coverage** | **82.8%** on the unit run (push gate: 70%; CI unit floor 80%) |
| **ADRs** | **21** — see [`docs/adr/README.md`](docs/adr/README.md) |
| **License** | Proprietary, source-available ([LICENSE](LICENSE), [NOTICE](NOTICE)); built on the AGPL-3.0 Pramana Protocol via its public SDK only |

## NIST agentic-IAM scorecard (7 / 3 / 0)

Crosswalk against the NIST 10-tenet agentic IAM model
([full mapping](docs/compliance/nist-agentic-iam-mapping.md)):

| Disposition | Count | Tenets |
|---|---|---|
| **Implemented** | 7 | 04, 05, 06, 07, 08, 09, 10 |
| **Partial** | 3 | 01, 02, 03 |
| **Weak** | 0 | — |

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
