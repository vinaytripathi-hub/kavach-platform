# Phase 1.5 — Gate-Closure Evidence

**Status: CLOSED** · **Date:** 2026-10-30 · **Release:** `v0.0.1`
([GitHub Release](https://github.com/vinaytripathi-hub/kavach-platform/releases/tag/v0.0.1))

Phase 1.5 ships the two first-class SDKs as installable packages on their public
registries, published from CI with supply-chain provenance, and verified by a
clean-room install from the **live** registries driving the full accountability
loop end to end. This document is the durable evidence that the gate is met.

## Published artifacts

| Package | Ecosystem | Version | Registry | Supply-chain |
|---|---|---|---|---|
| `aurvia-kavach` (import `kavach`) | PyPI | 0.0.1 | <https://pypi.org/project/aurvia-kavach/0.0.1/> | PyPI Trusted Publishing (OIDC) + PEP 740 attestations |
| `@aurvia/kavach` | npm | 0.0.1 | <https://www.npmjs.com/package/@aurvia/kavach/v/0.0.1> | npm provenance (`--provenance`) |

Both were published by the same GitHub Release (`v0.0.1`) through
`.github/workflows/publish-python.yml` and `.github/workflows/publish-npm.yml`.
Python requires `>=3.11,<3.14`; TypeScript requires Node 18+. The two clients
mirror each other 1:1 and are held in lockstep by a cross-SDK contract test.

## CI evidence

- **Tag `v0.0.1` (dry-run gate):** build sdist+wheel → smoke-install on Python
  3.11/3.12/3.13 → TestPyPI upload (OIDC) → npm `--dry-run` — all green.
- **GitHub Release `v0.0.1` (publish):** `Publish to PyPI` succeeded; npm
  `Build + publish` succeeded with a signed provenance statement recorded in the
  public transparency log.

## Clean-room verification — Python (from live PyPI)

Fresh Python 3.12 virtualenv, nothing pre-installed:

```
$ pip install aurvia-kavach          # resolved 0.0.1 from pypi.org
$ python -c "import kavach; print(kavach.__version__)"   # 0.0.1
```

Running the customer-service demo (`run_demo_flow`) against a locally booted
server produced:

```
health.version        0.0.1
kyc_outcome           allow
transfer_outcome      step_up
resolved_outcome      allow
mandate_id            m-demo-1
audit_record_count    12
audit_signed          true        (HMAC-SHA256)
timeline_len          7
```

## Clean-room verification — Node (from live npm)

Fresh Node project, nothing pre-installed:

```
$ npm install @aurvia/kavach@0.0.1   # added 1 package from registry.npmjs.org
```

Running `examples/node/minimal-agent` against a locally booted server produced:

```
1. mandate issued ......... m-wrcngi
2. transfer decision ...... step_up
3. operator resolution .... allow
4. evidence export ........ 7 record(s), HMAC-SHA256
MINIMAL AGENT FLOW PASSED
```

## Local quality bars (at the release commit)

- Test suite: 163 collected — 159 unit/integration passing, 2 Postgres
  integration skipped (need `KAVACH_DATABASE_URL`), 2 e2e deselected from the
  push gate; **coverage 85.44%** (gate 70%).
- TypeScript SDK: 15 contract tests passing; `tsc` typecheck + build clean.
- Python dist: `twine check` PASSED on sdist + wheel; no direct-URL
  dependencies in published metadata.

## Conclusion

All Phase 1.5 acceptance criteria are met and verified against the **live**
registries. **Phase 1.5 gate: CLOSED.**
