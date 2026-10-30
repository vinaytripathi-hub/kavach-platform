# Kavach Platform — Status

_Agent accountability for Indian BFSI. Proprietary, source-available._

**Last updated:** 2026-10-29 · **Latest tag:** _none yet (pre-`v0.0.1`)_

---

## TL;DR

| | |
|---|---|
| **Working prototype (Phase 1)** | **Shipped** — substrate, `/v1` API, Customer Service use case, operator console, on-prem Docker packaging |
| **SDK packaging + publish (Phase 1.5)** | **Gate OPEN** — Python (`aurvia-kavach`) and TypeScript (`@aurvia/kavach`) packages build, validate, and dry-run-pack cleanly; publish workflows wired. First live release to PyPI + npm is the one remaining step (needs registry/identity setup on the current GitHub account). |
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
| `aurvia-kavach` (Python, import `kavach`) | PyPI / TestPyPI (Trusted Publishing, OIDC) | Built + `twine check` clean; **not yet published** |
| `@aurvia/kavach` (TypeScript) | npm (`--provenance`) | Builds + packs clean; **not yet published** |

Publish is fully CI-driven: a signed `v*` tag runs the build + smoke-install
matrix + TestPyPI/npm dry-runs; a published GitHub Release pushes to PyPI and
npm. See [`.github/workflows/publish-python.yml`](.github/workflows/publish-python.yml)
and [`.github/workflows/publish-npm.yml`](.github/workflows/publish-npm.yml).

**Remaining action to close the Phase 1.5 gate:** configure the PyPI + TestPyPI
Trusted Publishers, the `NPM_TOKEN` secret, and the `pypi` / `testpypi` GitHub
environments on this repository, then cut the first signed `v0.0.1` tag and
Release.

## More

Overview: [`README.md`](README.md) · Roadmap: [`docs/roadmap.md`](docs/roadmap.md) ·
ADR index: [`docs/adr/README.md`](docs/adr/README.md)
