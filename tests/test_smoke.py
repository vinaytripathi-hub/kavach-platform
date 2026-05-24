"""Smoke test: verifies the Python package skeleton is correctly wired.

This is the only test file in sub-block B.2. It validates:
- Pytest collects tests from tests/ root
- The shared fixtures from tests/conftest.py work
- The kavach package imports successfully
- The kavach.__version__ string is present and well-formed
- The expected top-level subpackages exist and are importable

This file will remain in place until W01-S03 lands the first real
capability, at which point a more substantive set of smoke tests at the
capability level will replace this single test file.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_kavach_package_imports() -> None:
    """The top-level kavach package imports cleanly."""
    import kavach

    assert hasattr(kavach, "__version__")
    assert isinstance(kavach.__version__, str)
    # Pre-release version 0.x.y
    assert kavach.__version__.startswith("0.")


def test_kavach_subpackages_import() -> None:
    """All target subpackages import as empty packages."""
    subpackages = [
        "kavach.events",
        "kavach.capabilities",
        "kavach.capabilities.sdk_bridge",
        "kavach.capabilities.enrichment",
        "kavach.capabilities.dpi",
        "kavach.capabilities.audit",
        "kavach.capabilities.policy",
        "kavach.capabilities.storage",
        "kavach.composition",
        "kavach.query",
        "kavach.usecases",
        "kavach.usecases.customer_service",
        "kavach.usecases.credit_underwriting",
        "kavach.usecases.trading",
        "kavach.experiences",
    ]

    for name in subpackages:
        module = importlib.import_module(name)
        assert module is not None, f"{name} failed to import"


def test_repo_root_fixture_resolves(repo_root: Path) -> None:
    """The repo_root fixture resolves to a real directory containing LICENSE."""
    assert repo_root.is_dir()
    assert (repo_root / "LICENSE").is_file()
    assert (repo_root / "pyproject.toml").is_file()
    assert (repo_root / "kavach" / "__init__.py").is_file()


def test_fixtures_dir_fixture_resolves(fixtures_dir: Path) -> None:
    """The fixtures_dir fixture resolves to tests/fixtures/."""
    assert fixtures_dir.is_dir()
    assert fixtures_dir.name == "fixtures"
    assert fixtures_dir.parent.name == "tests"


@pytest.mark.parametrize(
    "operation,expected",
    [
        ("identity", 1),
        ("addition", 2),
        ("string_op", "K"),
    ],
)
def test_pytest_parametrize_works(operation: str, expected: object) -> None:
    """Sanity check: pytest's parametrize machinery functions correctly."""
    if operation == "identity":
        result: object = 1
    elif operation == "addition":
        result = 1 + 1
    elif operation == "string_op":
        result = "kavach"[0].upper()
    else:
        pytest.fail(f"Unknown operation: {operation}")
    assert result == expected
