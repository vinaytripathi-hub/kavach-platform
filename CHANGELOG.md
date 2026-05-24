# Changelog

All notable changes to Kavach Platform are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and Kavach Platform versioning will follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once the first stable release lands.

## [Unreleased]

### Added — W01-S02 Block D.3 (this commit)

- `docs/adr/0011-sub-product-extraction-posture.md` — capabilities
  classified by extraction potential. High-extractability (Audit,
  Policy, Operator Console) designed strictly for standalone
  packaging: no implicit cross-capability dependencies, self-contained
  data models, self-contained event vocabularies, independent
  versioning posture. Low-extractability (Enrichment, DPI bridge,
  SDK bridge) accept Kavach-only coupling. Mixed (Storage,
  Composition, Events) handled case-by-case. Optionality preserved
  even if extraction is never exercised; discipline produces
  better-isolated capabilities regardless.
- `docs/adr/0012-decision-events-with-evidence-and-reasoning.md`
  — every decision event the substrate emits carries four mandatory
  embedded fields: Evidence (structured inputs, by-reference for
  large records), ReasoningTrace (rule/model/composite/human with
  decision path), Confidence (rule_deterministic / probabilistic /
  human_judged with calibration metadata), and decided-by (which
  rule/model/operator produced the decision). Feedback events
  (DecisionFeedbackRecorded) close the FP/FN loop and become
  labeled training data. Decision-primitive types versioned per
  ADR-0010. Privacy via inline-vs-reference data minimization.

### Changed — W01-S02 Block D.3

- `docs/adr/README.md` — "Current ADRs" table extended with rows
  for 0011 and 0012; "planned ADRs" paragraph trimmed to mention
  only 0013–0014.

### Added — W01-S02 Block D.2 (this commit)

- `docs/adr/0009-read-side-projections.md` — projections under
  `kavach/query/projections/` are top-level substrate concerns (not
  inside any capability). Each projection declares the events it
  consumes, the projection tables it maintains, a handler function,
  and a `rebuild()` method for replay-based backfill. Synchronous
  updates by default (same transaction as the producing event);
  asynchronous via outbox for the rare expensive case. Projections
  are derivative; the event log is source of truth.
- `docs/adr/0010-event-schema-versioning.md` — event schemas are
  public API. Three change classes: additive (no bump), compatible
  (no bump, reviewed), breaking (new version + four-phase rollout).
  Versioned classes accumulate; retired versions move to
  `_archive/` but remain importable for replay. Decision events'
  embedded evidence and reasoning types are versioned too.

### Changed — W01-S02 Block D.2

- `docs/adr/README.md` — "Current ADRs" table extended with rows
  for 0009 and 0010; "planned ADRs" paragraph updated to reflect
  that 0009 and 0010 are now Accepted (remaining planned:
  0011–0014).

### Added — W01-S02 Block D.1 (this commit)

- `docs/adr/0007-modular-capability-architecture.md` — per-capability
  structural discipline: `__init__.py` as the only public surface,
  `_internal/` for private implementation, `events.py` for emitted
  events, `contracts.py` for Protocol-based dependencies,
  `extension_points.py` for use-case-implementable interfaces.
  Composition layer (`kavach/composition/`) wires concrete
  implementations to Protocols at startup.
- `docs/adr/0008-events-as-substrate-primary-output.md` — domain
  events are the substrate's primary contract with the rest of the
  system. Capabilities are event transformers; internal state is a
  private implementation convenience. Pragmatic event-driven
  (not pure event sourcing): state lives in Postgres tables for
  queryability, events emitted alongside state changes. Correctness
  lives at three layers (logic, event boundary, system). Frontend
  reads projections built from events, not capability internal state.

### Changed — W01-S02 Block D.1

- `docs/adr/README.md` — "Current ADRs" table extended with rows for
  0007 and 0008; "planned ADRs" paragraph updated to reflect that
  0007 and 0008 are now Accepted (remaining planned: 0009–0014).

### Added — W01-S02 Block C (this commit)

- `docs/adr/README.md` — index document for Architecture Decision
  Records, with format conventions, status meanings, and rationale
  for the ADR practice.
- `docs/adr/0001-three-layer-architecture.md` — substrate / use cases
  / experiences three-layer architecture.
- `docs/adr/0002-substrate-first-build-order.md` — substrate first,
  use cases on top of it, experiences last.
- `docs/adr/0003-pramana-kavach-separation.md` — strict IP boundary
  between Pramana (AGPL-3.0 open-source substrate) and Kavach
  (proprietary commercial layer); Pattern B editable install for
  development; "Kavach contains no Pramana source code" as a
  durable commitment.
- `docs/adr/0004-self-hosted-postgres-on-yotta.md` — self-hosted
  PostgreSQL 16 on Yotta Yntraa for sovereign Indian data
  residency; matches CI integration-test target.
- `docs/adr/0005-accountability-positioning.md` — "Agent
  Accountability for Indian BFSI" as the market wedge; BFSI-first
  not BFSI-only.
- `docs/adr/0006-tdd-discipline.md` — TDD as the engineering
  default; coverage floors (80% capabilities/events/composition/query,
  70% usecases/experiences); test pyramid; signed-commit
  requirement; pre-commit and CI enforcement.

### Removed — W01-S02 Block C (this commit)

- `docs/adr/.gitkeep` — placeholder removed now that real ADRs
  populate the directory.

### Added — W01-S02 Block B (this commit set: 3 commits)

- **Directory skeleton** for the modular substrate architecture:
  `kavach/{events,capabilities/{sdk_bridge,enrichment,dpi,audit,policy,storage},composition,query,usecases/{customer_service,credit_underwriting,trading},experiences}/`
  with `__init__.py` placeholders. `tests/` mirrors the source tree
  exactly, plus `tests/{integration,e2e,fixtures}/` subdirectories
  per the test pyramid.
- **pyproject.toml**: full project configuration with hatchling build,
  Python 3.12 pin, runtime dependencies (declaring forward-looking
  `pramana>=0.1.0,<0.2.0`, FastAPI, Pydantic, SQLAlchemy[asyncio] +
  asyncpg, cryptography, structlog), dev dependencies (pytest + plugins,
  hypothesis, syrupy, ruff, mypy, pre-commit, test utilities), pytest /
  coverage / ruff / mypy strict configurations.
- **.python-version**: pins to `3.12`.
- **tests/conftest.py**: shared fixtures (`repo_root`, `fixtures_dir`),
  environment isolation (auto-strip `KAVACH_*` env vars), automatic
  marker assignment by test location.
- **tests/test_smoke.py**: four smoke tests verifying package imports,
  fixture resolution, and pytest parametrize machinery.
- **.pre-commit-config.yaml**: pre-commit-stage hooks (hygiene, ruff,
  mypy, fast unit tests) and pre-push-stage hooks (full unit +
  integration suite with coverage gate, GPG signature enforcement).
- **scripts/dev-setup.sh**: one-command developer bootstrap using uv —
  verifies uv, installs Python 3.12, creates venv, installs Kavach with
  [dev] extras, installs Pramana SDK in editable mode from local
  checkout, installs pre-commit hooks, runs smoke test.
- **scripts/check-gpg-signature.sh**: pre-push hook helper that enforces
  GPG signatures on commits to `main`.
- **.github/workflows/ci.yml**: CI pipeline running lint, unit tests
  (Python 3.12) with `--cov-fail-under=80`, integration tests against
  Postgres 16, security audit (pip-audit), wheel build sanity check.
  Uses uv via `astral-sh/setup-uv@v3` for fast cached installs.
- **.github/workflows/codeql.yml**: weekly static security analysis
  (Python) using GitHub's CodeQL with `security-and-quality` query
  pack.

### Added — W01-S02 Block A (this commit)

- LICENSE (proprietary, all rights reserved) with explicit
  "No License Granted by Mere Possession" clause.
- NOTICE attributing Pramana Protocol (AGPL-3.0) as a foundational
  dependency consumed solely via the public SDK boundary, with
  explicit statement that Kavach Platform contains no Pramana source
  code.
- README oriented to internal team and diligence reviewers.
- CONTRIBUTING gating contributions to authorized Aurvia Global
  personnel with IP-assignment-clause employment / contractor
  agreements.
- SECURITY vulnerability disclosure policy with email-first reporting
  and PGP key reference.
- CODE_OF_CONDUCT (Contributor Covenant v2.1).
- .gitignore covering Python, virtual environments, coverage, IDE
  artifacts, secrets, macOS metadata, log files, and macOS Finder
  duplicates.
- .gitattributes for line-ending normalization and GitHub language
  stat exclusions.

### Planned — subsequent W01-S02 blocks

- **Block B**: project skeleton (`kavach/` package layout),
  `pyproject.toml`, pre-commit configuration, GitHub Actions CI
  workflows, dev-setup script.
- **Block C**: foundational ADRs (0001-0006) — three-layer
  architecture, build order, Pramana-Kavach separation, Postgres on
  Yotta, "Accountability" positioning, TDD discipline.
- **Block D**: advanced architectural ADRs (0007-0014) — modular
  capability architecture, events as primary output, projections,
  event schema versioning, sub-product extraction posture, decision
  evidence and reasoning, multimodal data sufficiency,
  multidimensional trust.
- **Block E**: events infrastructure scaffolding, IP Provenance
  Document, CLA templates, Engineering Handbook, smoke tests, final
  verification, push to origin.
