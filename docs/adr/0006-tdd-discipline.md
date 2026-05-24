# ADR-0006 — TDD as the engineering default

**Status:** Accepted
**Date:** 2026-05-24

## Context

Kavach Platform is built by a solo founder directing AI coding
assistants (Cursor with Claude). This combination is extraordinarily
productive for code volume but has known failure modes:

- **Plausible-but-wrong code.** AI assistants generate code that
  looks correct, compiles, and reads sensibly but is subtly wrong.
  Without test pressure, these bugs ship.
- **Regression drift.** Without tests pinning behavior, refactors
  that AI assistants happily perform can silently change semantics.
- **Context gaps.** AI assistants don't remember the system the way
  a long-tenured engineer would. Tests serve as durable memory of
  what the system is supposed to do.
- **Audit and compliance posture.** BFSI customers, partners, and
  regulators will eventually ask "how do you know this code is
  correct?" An answer that begins with "we test it" is required;
  an answer that begins with "the AI usually gets it right" is not.

At the same time, naive TDD discipline can fail in solo-founder
contexts:

- Hand-writing tests for every line of substrate code is slow.
- Coverage targets enforced too aggressively cause test-writing
  fatigue and a shift toward low-value tests written purely to
  satisfy the metric.
- TDD without judgment produces tests that pin implementation
  details, making future refactoring harder.

We need a TDD discipline that is rigorous enough to catch the
AI-coding-assistant failure modes and forgiving enough to not bog
down a one-person team.

## Decision

TDD is the engineering default for Kavach Platform. Specific
discipline:

**Test-first by default:**

- For every substrate capability (under `kavach/capabilities/`),
  every domain event schema, every policy rule, every audit
  primitive — write the test first, then the implementation.
- Tests live next to source in the mirrored `tests/` tree
  (`tests/capabilities/audit/test_audit_writer.py`,
  `tests/composition/test_substrate.py`, etc.). This is enforced
  by the directory layout established in W01-S02 Block B.1.
- Use cases (`kavach/usecases/`) and experiences
  (`kavach/experiences/`) get tests as well, but with relaxed
  coverage expectations because their content is more
  configuration than logic.

**Coverage floors (enforced in CI):**

- `kavach.capabilities.*` — 80% line + branch coverage minimum
- `kavach.events`, `kavach.composition`, `kavach.query` — 80% minimum
- `kavach.usecases.*` — 70% minimum
- `kavach.experiences.*` — 70% minimum

Currently CI enforces a single global floor of 80% via
`--cov-fail-under=80` in `.github/workflows/ci.yml`. Per-package
floors will be split out in W01-S03 when the first real capability
lands and realistic coverage is observable.

**Test pyramid:**

- **Unit tests** — fast (sub-second per test), isolated, no
  database, no network. The majority of tests. Default marker
  (`tests/capabilities/...`, `tests/events/...`, etc.).
  Auto-marked as `@pytest.mark.unit` per `tests/conftest.py`.
- **Integration tests** — exercise the substrate against a real
  Postgres 16 service container. Used for capabilities whose
  correctness genuinely depends on database semantics (storage,
  audit hash chain persistence, projections). Live under
  `tests/integration/`. Auto-marked as `@pytest.mark.integration`.
- **End-to-end tests** — exercise a full use case through the
  experience layer. Slow, hand-curated, few in number. Live under
  `tests/e2e/`. Auto-marked as `@pytest.mark.e2e`.

**What we test:**

- **Behavior, not implementation.** Tests should pin "given these
  inputs, this capability produces these output events" — not
  "this method was called with these arguments." Resilient to
  refactoring.
- **Edge cases explicitly.** For every capability, the test suite
  must exercise: empty inputs, malformed inputs, boundary values,
  concurrent access where relevant, and at least one
  property-based test (via Hypothesis) for invariants that should
  hold for arbitrary valid inputs.
- **Failure modes.** Every place the code can fail (network
  error, malformed credential, signature mismatch, policy
  evaluation timeout) needs at least one test that exercises that
  failure path and asserts the right event is emitted or the right
  exception is raised.

**What we don't test:**

- **Third-party library internals.** We test that we call
  `cryptography.hazmat.primitives.hashes.SHA256` correctly; we
  do not test that SHA256 works.
- **Trivial getters and setters.** Pydantic models, dataclasses,
  and simple data shapes are exercised by tests that use them
  rather than tested directly.
- **Generated code.** Alembic migrations are reviewed but not
  unit-tested; they are tested by being applied to a real
  Postgres in integration tests.

**Branching and review discipline:**

- `main` is protected. Only Vinay merges to main during the solo
  founder phase. When the team grows, this becomes a `2 reviewer
  approval` requirement.
- Feature branches: `feature/<short-description>`. Spike branches:
  `spike/<topic>` — exempt from full TDD enforcement, but cannot
  merge to main without being rewritten as proper TDD work.
- Every commit on main is GPG-signed (enforced by the
  `scripts/check-gpg-signature.sh` pre-push hook). This is
  non-negotiable; it underpins the provenance story for audit and
  compliance.
- No `Co-authored-by:` trailers on Kavach commits. Sole-authorship
  is the discipline. The local `commit-msg` hook strips Cursor
  agent shell's trailer injection.

**Pre-commit and CI gates:**

- Pre-commit stage (every commit): generic hygiene + ruff lint
  with `--fix` + ruff format + mypy strict + fast unit tests.
- Pre-push stage (every push to remote): full unit + integration
  suite with coverage gate + GPG signature enforcement on main.
- CI on push and pull request: lint, unit tests with 80% coverage
  floor, integration tests against Postgres 16, security audit
  via pip-audit, wheel build sanity check, weekly CodeQL static
  analysis.

## Consequences

**Positive:**

- AI-coding-assistant code is gated by tests before it lands.
  Plausible-but-wrong code is caught at the test boundary, not in
  production.
- Refactoring is safe. The substrate can evolve through W01–W08
  without fear that working code is being silently broken.
- The audit and compliance answer to "how do you know this code is
  correct?" is concrete: "Here are the unit tests, the integration
  tests against real Postgres, the property-based tests, the
  coverage report, the CI history."
- Test-next-to-source layout keeps tests honest. They live where
  the code they test lives; orphaned tests are obvious.
- Type discipline (mypy strict + ruff annotations) catches a
  separate class of bug from tests, complementing rather than
  duplicating test coverage.

**Negative:**

- Slower than no-test development. Time-to-first-feature is longer.
  The trade-off is favorable because every BFSI-relevant feature
  needs to be defensible; untested code that needs to be made
  defensible later costs more than well-tested code shipped
  initially.
- Test discipline is sustained by external enforcement (CI gates,
  pre-commit hooks, coverage floors), not by willpower. The
  infrastructure to enforce it (W01-S02 Block B.3) is itself
  significant work. We accept this cost.
- Property-based tests via Hypothesis can be slow and flaky in
  CI. Mitigation: tightly-scoped property tests with seeds pinned
  in CI; failing examples added to a regression suite.
- Coverage metrics are imperfect. 80% line coverage does not mean
  80% behavior coverage. We accept the imperfection because the
  metric is good enough to catch the worst neglect and because the
  alternative (no metric at all) is worse. Engineering review of
  what's actually being tested is the deeper layer.

## Alternatives Considered

- **No TDD discipline; ship and iterate.** Tempting at the
  earliest pre-revenue stage where velocity matters most.
  Rejected because the cost of AI-coding-assistant bugs in BFSI
  is much higher than in low-stakes domains, and because
  retrofitting tests onto an existing codebase is dramatically
  more expensive than writing them up front.
- **TDD for substrate only; less rigorous for use cases.**
  Considered. Partially accepted — use cases and experiences have
  a relaxed coverage floor (70% vs 80%) and are encouraged to
  use end-to-end tests rather than dense unit coverage. But the
  test-first habit applies to all layers; only the rigor of the
  metric differs.
- **Behavior-driven development (BDD) with Gherkin/pytest-bdd.**
  Considered. Rejected because the audience that benefits from
  Gherkin (non-engineering stakeholders writing test specs) is
  not present at the solo-founder phase; the overhead of
  maintaining a Gherkin layer would not pay off.
- **Snapshot testing as the primary mechanism (via syrupy).**
  Considered. Snapshot tests are present as a tool (declared in
  `[dev]` deps) for specific use cases — audit record shapes,
  event schemas — but not the primary mechanism. Snapshots are
  too easy to "fix" by regenerating, which defeats their pinning
  purpose unless used judiciously.

## References

- ADR-0001 — Three-layer architecture
- ADR-0002 — Substrate-first build order
- `pyproject.toml` — pytest, ruff, mypy, hypothesis, syrupy,
  pre-commit configuration (W01-S02 Block B.2)
- `.pre-commit-config.yaml` — commit-stage and push-stage hooks
  (W01-S02 Block B.3, fixed in commit `8c33546`)
- `.github/workflows/ci.yml` — CI pipeline with coverage floors
- `scripts/check-gpg-signature.sh` — pre-push GPG enforcement
- `docs/engineering-handbook.md` (planned, W01-S02 Block E) —
  full discipline guide including code review checklist
