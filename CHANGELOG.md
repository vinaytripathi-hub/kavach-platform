# Changelog

All notable changes to Kavach Platform are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and Kavach Platform versioning will follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once the first stable release lands.

## [Unreleased]

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
