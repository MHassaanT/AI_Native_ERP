"""Tenant and Organization Entity Models."""

import uuid

from sqlalchemy import Boolean, Index, String
from sqlalchemy.dialects.postgresql import UUID
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
    plan_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="ENTERPRISE")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    users: Mapped[list["User"]] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="tenant", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_tenant_slug", "tenant_slug", unique=True),)
