"""Currency Exchange Rates and Automated Revaluation Domain Models."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class CurrencyExchangeRate(Base, TenantMixin, TimestampMixin):
    """Currency pair spot / conversion exchange rates."""

    __tablename__ = "currency_exchange_rates"

    rate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    __table_args__ = (
        Index("idx_cer_tenant_pair_date", "tenant_id", "from_currency", "to_currency", "effective_date"),
    )


class ExchangeRateRevaluation(Base, TenantMixin, TimestampMixin):
    """Log of periodic foreign exchange gain/loss balance sheet revaluation entries."""

    __tablename__ = "exchange_rate_revaluations"

    revaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    revaluation_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    total_gain_loss: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    journal_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_err_tenant_num", "tenant_id", "revaluation_number", unique=True),
    )
