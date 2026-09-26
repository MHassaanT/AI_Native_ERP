"""Tenant and Organization Entity Models."""

import uuid

from datetime import date, datetime
from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    """Tenant organization master record for multi-tenant isolation."""

    __tablename__ = "tenants"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    fiscal_year_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    fiscal_year_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(32), nullable=True)
    setup_completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    enabled_modules: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    plan_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="ENTERPRISE")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    users: Mapped[list["User"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="tenant", cascade="all, delete-orphan"
    )
    oauth_connections: Mapped[list["TenantOAuthConnection"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    settings: Mapped["TenantSettings | None"] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_tenant_slug", "tenant_slug", unique=True),)


class TenantOAuthConnection(Base, TimestampMixin):
    """Persisted third-party OAuth connection state (Gmail, Slack, etc.) per tenant."""

    __tablename__ = "tenant_oauth_connections"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="google_gmail")
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    connected_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String(32), nullable=False, default="Bearer")
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    synced_messages_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tenant: Mapped["Tenant"] = relationship(back_populates="oauth_connections")

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_tenant_provider"),
        Index("idx_tenant_oauth_provider", "tenant_id", "provider"),
    )

