"""Database Initialization and Schema Generation Utility."""

import asyncio
import logging

from erp.db.engine import async_engine
from erp.db.models import Base

logger = logging.getLogger(__name__)


async def init_database() -> None:
    """Creates all multi-tenant tables in PostgreSQL."""
    async with async_engine.begin() as conn:
        logger.info("Generating all tables via Base.metadata.create_all...")
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(init_database())
