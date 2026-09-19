"""SQLAlchemy engine configuration for async and sync operations."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from erp.config import settings

# Async Engine for core application runtime
async_engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG and settings.ENVIRONMENT == "development",
    future=True,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# Sync Engine for Alembic and migration scripts
sync_engine: Engine = create_engine(
    settings.sync_database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)
