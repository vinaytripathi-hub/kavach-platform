"""Async engine and session factory management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from kavach.capabilities.storage._internal.models import Base


def make_engine(url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine for the given database URL.

    Accepts e.g. ``postgresql+asyncpg://...`` for on-prem and
    ``sqlite+aiosqlite://`` for tests. In-memory SQLite is given a
    ``StaticPool`` so a single shared connection persists the schema
    across sessions (otherwise each connection gets a fresh empty DB).
    """
    if url.startswith("sqlite") and (":memory:" in url or url.endswith("://")):
        return create_async_engine(
            url,
            echo=echo,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_async_engine(url, echo=echo, future=True)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to ``engine``."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _register_all_tables() -> None:
    """Import every module that defines ORM tables on ``Base``.

    Tables are defined across capabilities (audit) and the query layer
    (projections); importing them attaches their metadata to ``Base``
    before ``create_all`` / Alembic autogenerate runs.
    """
    import kavach.capabilities.audit._internal.models
    import kavach.query.projections._tables  # noqa: F401


async def create_all(engine: AsyncEngine) -> None:
    """Create all substrate tables. Used by tests and the offline demo.

    On-prem deployments use Alembic migrations (ADR-0017) rather than
    ``create_all``.
    """
    _register_all_tables()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all(engine: AsyncEngine) -> None:
    """Drop all substrate tables (test teardown convenience)."""
    _register_all_tables()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Transactional session scope: commit on success, rollback on error."""
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
