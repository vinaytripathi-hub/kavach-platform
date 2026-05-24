#!/usr/bin/env bash
# Kavach Platform — developer environment bootstrap.
#
# This script:
#   1. Verifies uv is installed (and installs it if missing, after confirmation).
#   2. Ensures Python 3.12 is installed via uv (uv python install 3.12).
#   3. Creates a project virtual environment at .venv/ pinned to Python 3.12.
#   4. Installs Kavach in editable mode with [dev] extras.
#   5. Installs Pramana SDK in editable mode from ../Pramana-protocol/sdk/python
#      (Pattern B per ADR-0003), overriding the PyPI declaration in
#      pyproject.toml.
#   6. Installs pre-commit hooks (commit + push stages).
#   7. Runs the smoke test suite as a sanity check.
#
# Usage:
#   ./scripts/dev-setup.sh

set -euo pipefail

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
KAVACH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRAMANA_DIR_CANDIDATE="$KAVACH_DIR/../Pramana-protocol"

cd "$KAVACH_DIR"

echo "============================================================"
echo "Kavach Platform — Developer Environment Setup"
echo "============================================================"
echo "Kavach repo:   $KAVACH_DIR"

# ----------------------------------------------------------------------------
# 1. Verify uv is installed
# ----------------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo ""
  echo "uv is not installed. uv is the Python toolchain manager Kavach uses"
  echo "for Python version installation and virtual environment management."
  echo ""
  echo "Install uv with:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo ""
  echo "Then re-run this script."
  exit 1
fi

echo "✓ uv found: $(uv --version)"

# ----------------------------------------------------------------------------
# 2. Ensure Python 3.12 is available via uv
# ----------------------------------------------------------------------------
echo ""
echo "Ensuring Python 3.12 is available..."
uv python install 3.12 2>&1 | tail -3 || true

# Verify uv can resolve a 3.12 interpreter
if ! uv python find 3.12 >/dev/null 2>&1; then
  echo "ERROR: uv could not locate or install Python 3.12."
  echo "Try: uv python install 3.12 --verbose"
  exit 1
fi
echo "✓ Python 3.12 available via uv"

# ----------------------------------------------------------------------------
# 3. Create / refresh virtual environment
# ----------------------------------------------------------------------------
echo ""
if [[ -d .venv ]]; then
  echo "Using existing virtual environment at .venv/"
else
  echo "Creating virtual environment at .venv/ (Python 3.12)..."
  uv venv --python 3.12 .venv
fi

# Activate venv for subsequent commands
# shellcheck disable=SC1091
source .venv/bin/activate
echo "✓ Virtual environment active: $(python --version) at $(which python)"

# ----------------------------------------------------------------------------
# 4. Install Kavach in editable mode with [dev] extras
# ----------------------------------------------------------------------------
echo ""
echo "Installing Kavach Platform + [dev] dependencies..."
uv pip install --upgrade pip wheel setuptools
uv pip install -e ".[dev]"
echo "✓ Kavach installed in editable mode with dev dependencies"

# ----------------------------------------------------------------------------
# 5. Override Pramana with local editable install if local checkout exists
# ----------------------------------------------------------------------------
echo ""
if [[ -d "$PRAMANA_DIR_CANDIDATE/sdk/python" ]]; then
  pramana_resolved="$(cd "$PRAMANA_DIR_CANDIDATE/sdk/python" && pwd)"
  echo "Found local Pramana SDK checkout at:"
  echo "  $pramana_resolved"
  echo ""
  echo "Installing Pramana SDK in editable mode (Pattern B per ADR-0003)..."
  uv pip install -e "$pramana_resolved"
  echo "✓ Pramana SDK installed in editable mode from local source"
else
  echo "No local Pramana SDK checkout found at $PRAMANA_DIR_CANDIDATE/sdk/python."
  echo "Pramana SDK will be resolved from PyPI per the pyproject.toml declaration"
  echo "(currently this will fail since Pramana is not yet published to PyPI;"
  echo "expected to be resolved by W01-S05)."
fi

# ----------------------------------------------------------------------------
# 6. Install pre-commit hooks
# ----------------------------------------------------------------------------
echo ""
echo "Installing pre-commit hooks (commit + push stages)..."
pre-commit install --hook-type pre-commit
pre-commit install --hook-type pre-push
echo "✓ Pre-commit hooks installed"

# ----------------------------------------------------------------------------
# 7. Run smoke test suite
# ----------------------------------------------------------------------------
echo ""
echo "Running smoke test suite..."
if pytest tests/test_smoke.py -q --no-cov; then
  echo "✓ Smoke tests pass"
else
  echo "✗ Smoke tests failed — review output above"
  exit 1
fi

# ----------------------------------------------------------------------------
# Done
# ----------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "Setup complete."
echo "============================================================"
echo ""
echo "To activate the environment in a new shell:"
echo "  source $KAVACH_DIR/.venv/bin/activate"
echo ""
echo "Common commands:"
echo "  pytest -q                  # Fast unit tests"
echo "  pytest -m integration      # Integration tests (needs Postgres)"
echo "  pytest --cov               # With coverage report"
echo "  ruff check .               # Lint"
echo "  ruff format .              # Auto-format"
echo "  mypy kavach tests          # Strict type check"
echo "  pre-commit run --all-files # Run all hooks against all files"
echo ""
echo "Next:"
echo "  - Review docs/engineering-handbook.md (added in W01-S02 Block E)"
echo "  - Review docs/adr/ for foundational decisions (added in Blocks C and D)"
echo "  - Begin W01-S03 (first substrate capability) when ready"
