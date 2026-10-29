"""Phase 1.5 SDK contract tests (ADR-0016).

Two guarantees:

1. The Python distribution is published under the name ``aurvia-kavach`` while
   the import package stays ``kavach`` (Stripe-style: ``pip install
   aurvia-kavach`` / ``import kavach``).
2. Every public method on the reference :class:`kavach.client.KavachClient`
   has a 1:1 counterpart on the TypeScript ``KavachClient`` (camelCase), so the
   two SDKs cannot drift. The TS method inventory is derived from the committed
   SDK source under ``sdks/typescript/``.
"""

from __future__ import annotations

import importlib.metadata
import inspect
import re
from pathlib import Path

import kavach
from kavach.client import KavachClient

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TS_CLIENT = _REPO_ROOT / "sdks" / "typescript" / "src" / "client.ts"


def _snake_to_camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _python_client_methods() -> set[str]:
    """Public, non-dunder methods on the reference Python client."""
    return {
        name
        for name, member in inspect.getmembers(KavachClient, predicate=inspect.isfunction)
        if not name.startswith("_") and name not in {"close"}
    }


def test_distribution_is_named_aurvia_kavach() -> None:
    meta = importlib.metadata.metadata("aurvia-kavach")
    assert meta["Name"] == "aurvia-kavach"


def test_import_package_is_kavach_with_version() -> None:
    assert kavach.__version__
    assert importlib.metadata.version("aurvia-kavach") == kavach.__version__


def test_typescript_client_mirrors_every_python_method() -> None:
    assert _TS_CLIENT.exists(), f"TS client not found at {_TS_CLIENT}"
    source = _TS_CLIENT.read_text(encoding="utf-8")
    # Collect `name(` method declarations inside the class.
    ts_methods = set(re.findall(r"^\s{2}(?:async\s+)?([a-zA-Z][a-zA-Z0-9]*)\s*\(", source, re.M))
    for py_method in _python_client_methods():
        camel = _snake_to_camel(py_method)
        assert camel in ts_methods, (
            f"Python method '{py_method}' has no TS counterpart '{camel}' in client.ts"
        )
