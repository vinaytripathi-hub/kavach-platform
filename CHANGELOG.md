# Changelog

All notable changes to Kavach Platform are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and Kavach Platform versioning will follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once the first stable release lands.

## [Unreleased]

### Added — Signed mandates, AP2 verification, and monitoring

- **ADR-0018 (Accepted)** — signed mandates as a substrate capability.
  `POST /v1/mandates`, presentation on `X-Kavach-Mandate`, revocation,
  and per-rule `mandate_required`. Fake HMAC verifier, plus an AP2
  verifier that checks a Google AP2 SDK SD-JWT payment chain when the
  `ap2` extra is installed (HS256 stand-in otherwise). Customer-service
  transfers require a mandate.
- **ADR-0019 (Accepted)** — monitor capability with rate, outcome-drift,
  scope-expansion, and confidence-drop detectors. Open anomaly severity
  is a policy input. Operator console anomalies view.
- **Signer protocol** on the audit chain (`HMACSigner`, `KmsSignerStub`).
- **MCP server** (`python -m kavach.experiences.mcp_server`) exposing
  decide, mandate, step-up, trust, and timeline tools. The server is built
  on the official MCP SDK and speaks both `stdio` and `streamable-http`;
  conformance is tested with the official MCP client over in-memory and
  HTTP transports.
- **Audit `Signer`** is now byte-oriented (`sign(bytes) -> bytes`,
  `verify(bytes, bytes) -> bool`, `key_id`), so an HSM or KMS adapter can
  return raw signature bytes. The HMAC chain stores the hex form and
  verifies bit-for-bit as before.
- **Swarm scorecard** runner at `kavach/testing/swarm.py`.

### Added — Phase 1.5: installable SDKs (Python + TypeScript)

- **Python distribution renamed to `aurvia-kavach`** (import package stays
  `kavach`), with support widened to Python 3.11 / 3.12 / 3.13.
- **TypeScript SDK `@aurvia/kavach`** under `sdks/typescript/`: types generated
  from `docs/api/openapi.yaml`, and a hand-polished `KavachClient` whose methods
  mirror the Python reference client 1:1 (camelCase). Non-2xx responses throw
  `KavachApiError` carrying the RFC 7807 body.
- **Cross-SDK contract tests** keep the two clients in lockstep
  (`tests/sdk/test_python_sdk_contract.py` + `sdks/typescript/test/contract.spec.ts`).
- **Node reference agent** at `examples/node/minimal-agent/` and a one-command
  cross-language proof `scripts/smoke-sdk-node.sh` (issue mandate → decide →
  step-up → export evidence).
- **Publish CI**: `sdk-typescript.yml` (typecheck/test/build + OpenAPI
  types-in-sync check), `publish-python.yml` (3.11/3.12/3.13 smoke-install
  matrix → TestPyPI dry-run → PyPI via Trusted Publishing on release), and
  `publish-npm.yml` (`npm publish --provenance`). First public-registry release
  is pending credentials and the `@aurvia` npm scope.

### Fixed

- Duplicate mandate issuance now returns `409 mandate_already_exists`
  (RFC 7807) instead of surfacing a database integrity error as `500`.

### Tested — Phase 1 hardening

- AP2 SD-JWT verifier unhappy/edge matrix at parity with the fake verifier:
  expired, wrong agent, scope mismatch, revoked, wrong nonce, amount over
  range, disallowed payee, and malformed chains all fail closed.
- Real Postgres `@pytest.mark.integration` suite exercising full issue →
  duplicate-409 → decide and revoke → deny flows against the production
  database target (not just in-memory SQLite).
- API edge cases: malformed `X-Kavach-Mandate` header (never trusted, no
  `500`), tenant-isolated timelines, revoke/get on unknown mandates (`404`),
  step-up queue, unknown step-up resolve (`404`), trust `404`, and agent
  self-scoped metrics.
- Policy-engine mandate paths (originator-kind gating, constraint
  satisfaction and violation, payee fallback, unsupported/typed operators)
  and direct attenuation coverage (now 100%). Suite coverage ≥ 85%.

### Added — W01-S03 Working Prototype

- **ADRs 0015–0017** — Pramana SDK packaging and AGPL posture (Protocol-
  based dependency, offline fake verifier, vendored-wheel bridge);
  external API surface, contract, and versioning; on-prem deployment
  posture (single-host Docker Compose first).
- **`docs/api/openapi.yaml`** — frozen `/v1` external contract (ingress,
  decisions, step-up resolve, trust, timeline, audit export, webhooks,
  admin, step-up queue) with RFC 7807 errors and idempotency.
- **`kavach/events/`** — versioned Pydantic event schemas for the eight
  core events plus embedded decision primitives (ADR-0012), data
  sufficiency (ADR-0013), and the multidimensional trust tensor
  (ADR-0014); a replay registry keyed by `(event_type, schema_version)`.
- **`kavach/capabilities/storage/`** — async SQLAlchemy models, the event
  store with a transactional outbox, idempotency and webhook stores, and
  engine/session helpers; Alembic baseline migration under `migrations/`.
- **`kavach/capabilities/audit/`** — HMAC-SHA256 hash-chained audit
  records written transactionally per event, plus a signed evidence-pack
  exporter and verifier.
- **`kavach/capabilities/policy/`** — declarative rule model, evaluation
  engine producing decision-grade events with graduated step-up, and the
  `PolicyRuleProvider` extension point.
- **`kavach/capabilities/sdk_bridge/`** — `CredentialVerifier` Protocol
  with a real Pramana adapter and an offline fake, selectable by config.
- **`kavach/composition/`** — `build_substrate` wiring, the append-and-
  fan-out event bus, the transactional substrate service, and the outbox
  webhook dispatcher worker.
- **`kavach/query/projections/`** — `agent_timeline`,
  `agent_trust_current`, `decision_log`, and `step_up_queue` projections,
  each rebuildable from the event log (ADR-0009).
- **`kavach/api/`** — FastAPI application implementing the frozen
  contract, with agent/operator auth, idempotency, and webhook
  subscriptions; `kavach/server.py` ASGI entrypoint and `kavach/worker.py`
  dispatcher entrypoint; `kavach/client.py` partner reference client.
- **Customer Service use case** — `PolicyRuleProvider`, trust-dimension
  config, and a synthetic agent harness driving the end-to-end demo.
- **Operator console** — zero-build SPA (`kavach/experiences/operator_console/`)
  with timeline, trust, step-up queue, and evidence-export screens.
- **On-prem packaging** — `Dockerfile`, `docker-compose.yml`,
  `.env.example`, `scripts/smoke-onprem.sh`, and
  `docs/deployment/on-prem-runbook.md`.
- **Compliance & security pack** — EU (AI Act + eIDAS/EUDIW) and India
  (RBI/SEBI/IRDAI/DPDP) regulatory mappings under `docs/compliance/`, plus
  a security whitepaper, threat model, and DPA template under
  `docs/security/`.
- **`docs/roadmap.md`** — phased plan from foundation to on-prem prototype.

### Changed — W01-S03 Working Prototype

- `pyproject.toml` — `aurvia-pramana` moved from a core dependency to the
  optional `[pramana]` extra (ADR-0015); added a flake8-bugbear immutable-
  calls allowlist for FastAPI dependency markers; coverage omits the
  integration-only entrypoints (client, worker, harness).
- `docs/adr/README.md` — index extended with ADRs 0015–0017.
- `README.md` — documents the working prototype, dev setup, and on-prem
  quickstart.

### Added — W01-S02 Block D.4 (this commit)

- `docs/adr/0013-multimodal-data-sufficiency.md` — every
  data-driven substrate output carries a `DataSufficiency`
  indicator with four bands (cold / thin / warm / warm_stale),
  per-modality breakdowns (observations counts, earliest/latest
  timestamps, reasons), and a conservative "worst-band-wins"
  default composition. Cold-start agents emit honest cold-band
  outputs rather than fabricated authoritative ones. Downstream
  policy, anomaly detection, and operator console all read
  sufficiency. Decision events embed their inputs' sufficiency
  in evidence per ADR-0012.
- `docs/adr/0014-multidimensional-trust-substrate.md` — trust
  in the Kavach substrate is a tensor, not a scalar.
  `TrustAssessment` carries a dict of `TrustDimension` (each
  with value, per-dimension `DataSufficiency`, contributors,
  reason) and an optional `CompositionSpec` for context-dependent
  rollup. Substrate ships core BFSI-relevant dimensions
  (credential_integrity, behavioral_consistency, policy_compliance,
  outcome_quality, peer_alignment); use cases extend the set.
  Different policies in the same use case may use different
  compositions; the choice is decision-grade. The first
  TrustAssessmentEmitted event uses the multidimensional schema
  from day one (potentially with a single dimension), avoiding
  later wholesale migration. Neural engine framing is a
  projection over the substrate, not an alternative to it.

### Changed — W01-S02 Block D.4

- `docs/adr/README.md` — "Current ADRs" table extended with rows
  for 0013 and 0014; "planned ADRs" paragraph replaced with a
  closing note that Blocks C and D produced the complete initial
  ADR set 0001–0014; subsequent ADRs will be added as new
  decisions arise.

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
