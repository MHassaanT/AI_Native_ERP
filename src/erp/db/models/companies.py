"""Multi-Company Group Consolidation and Inter-Company Transaction Models."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Company(Base, TenantMixin, TimestampMixin):
    """Company entity within a multi-company holding or enterprise group."""

    __tablename__ = "companies"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_name: Mapped[str] = mapped_column(String(128), nullable=False)
    company_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    parent_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.company_id"), nullable=True
    )
    is_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tax_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent_company: Mapped[Optional["Company"]] = relationship(
        "Company", remote_side=[company_id], back_populates="subsidiaries"
    )
    subsidiaries: Mapped[List["Company"]] = relationship(
        "Company", back_populates="parent_company"
    )

    __table_args__ = (
        Index("idx_comp_tenant_code", "tenant_id", "company_code", unique=True),
    )


class InterCompanyTransaction(Base, TenantMixin, TimestampMixin):
    """Inter-company transaction log for automated elimination in consolidated statements."""

    __tablename__ = "inter_company_transactions"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    from_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.company_id"), nullable=False
    )
    to_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.company_id"), nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    transaction_type: Mapped[str] = mapped_column(
        String(64), nullable=False  # INVOICE, LOAN, TRANSFER, CHARGE
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    reference_voucher_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reference_voucher_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    is_eliminated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    elimination_journal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    from_company: Mapped["Company"] = relationship("Company", foreign_keys=[from_company_id])
    to_company: Mapped["Company"] = relationship("Company", foreign_keys=[to_company_id])
