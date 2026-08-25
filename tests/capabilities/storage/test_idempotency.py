"""Tests for the idempotency store."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kavach.capabilities.storage import IdempotencyStore


async def test_get_miss_returns_none(
    session_factory: async_sessionmaker[AsyncSession], idempotency_store: IdempotencyStore
) -> None:
    async with session_factory() as session:
        assert await idempotency_store.get(session, "t1", "key-1") is None


async def test_put_then_get_roundtrip(
    session_factory: async_sessionmaker[AsyncSession], idempotency_store: IdempotencyStore
) -> None:
    async with session_factory() as session:
        await idempotency_store.put(session, "t1", "key-1", 201, {"id": "abc"})
        await session.commit()

    async with session_factory() as session:
        result = await idempotency_store.get(session, "t1", "key-1")

    assert result == (201, {"id": "abc"})


async def test_tenant_isolation(
    session_factory: async_sessionmaker[AsyncSession], idempotency_store: IdempotencyStore
) -> None:
    async with session_factory() as session:
        await idempotency_store.put(session, "t1", "shared", 200, {"who": "t1"})
        await session.commit()

    async with session_factory() as session:
        assert await idempotency_store.get(session, "t2", "shared") is None
