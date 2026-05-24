"""Top-level pytest configuration and shared fixtures.

This conftest.py is at the tests/ root. Per-package conftest.py files can
be added under tests/<package>/ as needed when specific fixtures become
relevant to particular packages.

Fixtures defined here are available to ALL tests in the suite.

See ADR-0006 (Block C) and docs/engineering-handbook.md (Block E) for the
TDD discipline this conftest supports.
"""
from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest


# ----------------------------------------------------------------------------
# Repository paths
# ----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Path to the repository root.

    Tests use this to resolve fixture files and verify repository invariants
    without hardcoding absolute paths.
    """
    # tests/conftest.py is exactly one level below the repo root.
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def fixtures_dir(repo_root: Path) -> Path:
    """Path to tests/fixtures/.

    Tests load synthetic data, snapshot baselines, and other read-only test
    inputs from this directory.
    """
    return repo_root / "tests" / "fixtures"


# ----------------------------------------------------------------------------
# Environment isolation
# ----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_kavach_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip any KAVACH_* environment variables from the test session.

    Prevents host-environment configuration from leaking into tests. Tests
    that need specific environment values should set them explicitly inside
    the test using monkeypatch.setenv().
    """
    for key in list(os.environ.keys()):
        if key.startswith("KAVACH_"):
            monkeypatch.delenv(key, raising=False)


# ----------------------------------------------------------------------------
# Marker auto-assignment by directory location
# ----------------------------------------------------------------------------


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Auto-mark tests by directory location for filterability.

    Convention:
      tests/integration/...   -> @pytest.mark.integration
      tests/e2e/...           -> @pytest.mark.e2e
      everything else         -> @pytest.mark.unit (default)

    This means a test author can write a plain test function under
    tests/capabilities/audit/test_audit_writer.py and have it automatically
    marked as a unit test, without sprinkling @pytest.mark.unit decorators.

    Tests under tests/integration/ and tests/e2e/ get their marks
    automatically too. Authors can add additional marks
    (@pytest.mark.slow, @pytest.mark.external) explicitly when warranted.
    """
    del config  # unused; pytest-required signature
    for item in items:
        path_str = str(item.fspath)
        if "/integration/" in path_str:
            item.add_marker(pytest.mark.integration)
        elif "/e2e/" in path_str:
            item.add_marker(pytest.mark.e2e)
        else:
            item.add_marker(pytest.mark.unit)
