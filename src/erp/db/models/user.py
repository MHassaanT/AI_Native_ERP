"""User and Authentication Domain Models."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class User(Base, TenantMixin, TimestampMixin):
    """User account entity belonging to a specific tenant."""

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="TENANT_ADMIN",  # TENANT_ADMIN, CONTROLLER, PLANT_MANAGER, OPERATOR, AUDITOR
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tenant: Mapped["Tenant"] = relationship(  # type: ignore[name-defined] # noqa: F821
        back_populates="users"
    )

    __table_args__ = (Index("idx_user_tenant_email", "tenant_id", "email", unique=True),)
