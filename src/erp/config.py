"""Configuration settings for AI-Native Multi-Agent ERP."""

import uuid
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    APP_NAME: str = "AI-Native ERP"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "dev_secret_key_change_in_production_ai_native_erp_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Multi-Tenancy (Priority invariant)
    DEFAULT_TENANT_ID: uuid.UUID = Field(
        default_factory=lambda: uuid.UUID("00000000-0000-0000-0000-000000000001")
    )
    MULTI_TENANCY_ENABLED: bool = True

    # PostgreSQL Database
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ai_erp"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_erp"
    SYNC_DATABASE_URL: str | None = None
    PORT: int = 8000

    @property
    def async_database_url(self) -> str:
        """Returns an asyncpg-compatible PostgreSQL connection string."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Returns a psycopg2 / Alembic-compatible synchronous PostgreSQL connection string."""
        if self.SYNC_DATABASE_URL and ("localhost" in self.DATABASE_URL or "localhost" not in self.SYNC_DATABASE_URL):
            url = self.SYNC_DATABASE_URL
        else:
            url = self.DATABASE_URL

        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        elif "+asyncpg" in url:
            url = url.replace("+asyncpg", "", 1)
        return url

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Redpanda / Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CLIENT_ID: str = "erp-backend"
    KAFKA_SCHEMA_REGISTRY_URL: str | None = "http://localhost:8081"

    # Google Workspace / Gmail OAuth 2.0
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # Inbound SMTP Gateway (False by default in production web containers to prevent port conflict)
    ENABLE_SMTP_GATEWAY: bool = False

    # Deterministic Ledger Ceilings & Settings
    LEDGER_TIER1_CEILING: Decimal = Decimal("2500.0000")
    LEDGER_TIER2_CEILING: Decimal = Decimal("25000.0000")
    BASE_CURRENCY: str = "USD"
    CURRENCY_PRECISION: int = 4

    # OpenTelemetry
    OTEL_SERVICE_NAME: str = "ai-native-erp"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_TRACES_ENABLED: bool = False


settings = Settings()
