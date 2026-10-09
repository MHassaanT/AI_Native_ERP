"""Configuration settings for AI-Native Multi-Agent ERP."""

import uuid
import warnings
from decimal import Decimal
from urllib.parse import unquote, urlsplit

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
    WEBHOOK_SIGNING_SECRET: str = "whsec_dev_ai_erp_2026"
    CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=list)
    ENABLE_OUTBOX_DISPATCHER: bool = False
    OUTBOX_DISPATCHER_POLL_SECONDS: int = Field(default=2, ge=1, le=300)

    # Multi-Tenancy (Priority invariant)
    DEFAULT_TENANT_ID: uuid.UUID = Field(
        default_factory=lambda: uuid.UUID("00000000-0000-0000-0000-000000000001")
    )
    MULTI_TENANCY_ENABLED: bool = True

    def model_post_init(self, __context):
        if self.ENVIRONMENT.lower() == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production environment.")
            if not self.SECRET_KEY or "dev_secret" in self.SECRET_KEY.lower():
                raise ValueError("Default development SECRET_KEY is forbidden in production.")
            if not self.WEBHOOK_SIGNING_SECRET or "dev" in self.WEBHOOK_SIGNING_SECRET.lower():
                raise ValueError("A production WEBHOOK_SIGNING_SECRET must be configured.")
            # Managed database providers (including Railway) expose credentials in
            # DATABASE_URL and do not necessarily expose POSTGRES_PASSWORD separately.
            database_password = unquote(urlsplit(self.DATABASE_URL).password or "")
            has_database_password = (
                database_password and database_password != "postgres"
            ) or (self.POSTGRES_PASSWORD and self.POSTGRES_PASSWORD != "postgres")
            if not has_database_password:
                raise ValueError(
                    "Configure a non-default database password in DATABASE_URL or POSTGRES_PASSWORD."
                )
            if database_password == "postgres":
                raise ValueError("DATABASE_URL must not use the default PostgreSQL password in production.")
            if "*" in self.CORS_ALLOWED_ORIGINS:
                raise ValueError("Production CORS_ALLOWED_ORIGINS must not contain a wildcard.")
            if not self.CORS_ALLOWED_ORIGINS:
                warnings.warn(
                    "CORS_ALLOWED_ORIGINS is empty; browser-based frontend requests will be blocked "
                    "until trusted frontend origins are configured.",
                    RuntimeWarning,
                    stacklevel=2,
                )
            if self.WHATSAPP_SERVICE_URL and (
                not self.WHATSAPP_INTERNAL_TOKEN
                or len(self.WHATSAPP_INTERNAL_TOKEN) < 32
                or "replace" in self.WHATSAPP_INTERNAL_TOKEN.lower()
            ):
                raise ValueError(
                    "Configure a unique WHATSAPP_INTERNAL_TOKEN of at least 32 characters."
                )


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
        if url.startswith("postgresql+psycopg://"):
            return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql+psycopg2://"):
            return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
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

    # Redpanda / Kafka (Optional: in-memory bus used if not configured)
    KAFKA_BOOTSTRAP_SERVERS: str | None = None
    KAFKA_CLIENT_ID: str = "erp-backend"
    KAFKA_SCHEMA_REGISTRY_URL: str | None = None

    # Google Workspace / Gmail OAuth 2.0
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # Google Gemini AI
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    LLM_PROVIDER: str = "openrouter"
    LLM_MODEL: str | None = None
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Baileys WhatsApp support channel
    WHATSAPP_SERVICE_URL: str | None = None
    WHATSAPP_INTERNAL_TOKEN: str | None = None

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
