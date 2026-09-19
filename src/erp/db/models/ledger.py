"""General Ledger and Financial Substrate Models (PRD Schema 1)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class GeneralLedgerEntry(Base, TenantMixin):
    """Core General Ledger Entry table enforcing mathematical double-entry invariants."""

    __tablename__ = "general_ledger_entries"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="Grouping identifier linking all balanced debit/credit legs of a transaction",
    )
    posting_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_period: Mapped[int] = mapped_column(Integer, nullable=False)
    account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    cost_center: Mapped[str] = mapped_column(String(64), nullable=False)
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0.0000"),
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0.0000"),
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("1.000000"),
    )
    source_document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    period_closing_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.clock_timestamp(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("debit_amount >= 0", name="chk_positive_debit"),
        CheckConstraint("credit_amount >= 0", name="chk_positive_credit"),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="chk_single_sided_line",
        ),
        Index(
            "idx_gl_account_period",
            "tenant_id",
            "account_code",
            "fiscal_year",
            "fiscal_period",
        ),
        Index("idx_gl_transaction_id", "tenant_id", "transaction_id"),
    )


class Account(Base, TenantMixin, TimestampMixin):
    """Chart of Accounts catalog."""

    __tablename__ = "chart_of_accounts"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_code: Mapped[str] = mapped_column(String(32), nullable=False)
    account_name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE",
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    parent_account_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("idx_coa_tenant_code", "tenant_id", "account_code", unique=True),)


class CostCenter(Base, TenantMixin, TimestampMixin):
    """Cost Center catalog."""

    __tablename__ = "cost_centers"

    cost_center_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cost_center_code: Mapped[str] = mapped_column(String(64), nullable=False)
    cost_center_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("idx_cc_tenant_code", "tenant_id", "cost_center_code", unique=True),)


class FiscalPeriod(Base, TenantMixin, TimestampMixin):
    """Fiscal Year and Period Lock controller."""

    __tablename__ = "fiscal_periods"

    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_period: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index(
            "idx_fiscal_period_tenant_year_period",
            "tenant_id",
            "fiscal_year",
            "fiscal_period",
            unique=True,
        ),
    )
