"""PostgreSQL transaction-scoped advisory locks for financial allocations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def advisory_lock_key(namespace: str, value: str) -> int:
    """Map an application identifier to PostgreSQL's signed 64-bit lock key."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{namespace}:{value}").int & ((1 << 63) - 1)


async def acquire_advisory_xact_lock(session: AsyncSession, namespace: str, value: str) -> None:
    """Serialize a financial operation until its surrounding transaction ends."""
    key = advisory_lock_key(namespace, value)
    await session.execute(select(func.pg_advisory_xact_lock(key)))
