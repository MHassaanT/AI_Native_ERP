"""Operator Certification Persistent Domain Models."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class OperatorCertificationRecord(Base, TenantMixin, TimestampMixin):
    """Persistent machine operator certification records."""

    __tablename__ = "operator_certifications"

    cert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=True
    )
    employee_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    certification_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    certification_name: Mapped[str] = mapped_column(String(128), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "idx_cert_tenant_emp_code",
            "tenant_id",
            "employee_code",
            "certification_code",
            unique=True,
        ),
    )
