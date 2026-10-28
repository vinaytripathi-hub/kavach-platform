# Kavach Platform — API + worker image (ADR-0017).
#
# Multi-stage build. The runtime image runs either the API
# (uvicorn kavach.server:app) or the worker (python -m kavach.worker),
# selected by the compose service command. The default sdk_bridge mode is
# the offline fake verifier (ADR-0015), so no Pramana wheel is required for
# the prototype. To enable real Pramana verification, place the
# aurvia-pramana wheel in ./vendor and uncomment the pramana install line.

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build a wheel of the Kavach package and its dependencies.
COPY pyproject.toml README.md ./
COPY kavach ./kavach
RUN pip install --upgrade pip build && python -m build --wheel --outdir /dist .

# ---------------------------------------------------------------------------

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Create an unprivileged user.
RUN useradd --create-home --uid 10001 kavach

WORKDIR /app

# Install the Kavach wheel and the pinned AP2 SDK so
# KAVACH_MANDATE_VERIFIER_MODE=ap2 verifies a real SD-JWT chain.
# git is only needed to fetch that commit, then removed.
COPY --from=builder /dist/*.whl /tmp/
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && pip install /tmp/*.whl \
      "ap2 @ git+https://github.com/google-agentic-commerce/AP2.git@e1ea56db72a6385bce3e5c1112b3a56ce60acb43" \
      "mcp>=2.3.0,<3.0.0" \
    && rm -f /tmp/*.whl \
    && apt-get purge -y git \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# To enable the real Pramana SDK (ADR-0015 vendored-wheel bridge):
#   COPY vendor/aurvia_pramana-*.whl /tmp/
#   RUN pip install /tmp/aurvia_pramana-*.whl && rm -f /tmp/*.whl

# Alembic migrations and config (run explicitly on-prem; ADR-0017).
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

USER kavach

EXPOSE 8000

# Default command runs the API; the worker service overrides this.
CMD ["uvicorn", "kavach.server:app", "--host", "0.0.0.0", "--port", "8000"]
