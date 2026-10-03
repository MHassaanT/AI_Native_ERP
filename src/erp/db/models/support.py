"""SQLAlchemy Models for Phase 6 Support & Helpdesk Domain."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class ServiceLevelAgreement(Base, TenantMixin, TimestampMixin):
    """SLA rules for customer service response and resolution."""

    __tablename__ = "service_level_agreements"

    sla_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sla_name: Mapped[str] = mapped_column(String(128), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, default="ISSUE")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    entity_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ALL"
    )  # ALL, CUSTOMER, CUSTOMER_GROUP
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    priorities: Mapped[list[ServiceLevelPriority]] = relationship(
        "ServiceLevelPriority", back_populates="sla", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_sla_tenant_name", "tenant_id", "sla_name"),)


class ServiceLevelPriority(Base, TenantMixin, TimestampMixin):
    """Response and resolution deadline metrics per priority tier."""

    __tablename__ = "service_level_priorities"

    priority_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sla_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_level_agreements.sla_id"),
        nullable=False,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # URGENT, HIGH, MEDIUM, LOW
    response_time_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("4.00")
    )
    resolution_time_hours: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("24.00")
    )

    sla: Mapped[ServiceLevelAgreement] = relationship("ServiceLevelAgreement", back_populates="priorities")


class Issue(Base, TenantMixin, TimestampMixin):
    """Support ticket opened by customer or agent."""

    __tablename__ = "issues"

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_number: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=True, index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.lead_id"), nullable=True
    )
    raised_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raised_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"
    )  # OPEN, REPLIED, ON_HOLD, RESOLVED, CLOSED
    priority: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MEDIUM"
    )  # LOW, MEDIUM, HIGH, URGENT
    issue_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="TECHNICAL"
    )  # TECHNICAL, BILLING, HARDWARE, FEATURE_REQUEST, BUG
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sla_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_level_agreements.sla_id"), nullable=True
    )
    response_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_responded_on: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    sla_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="WITHIN_SLA"
    )  # WITHIN_SLA, RESPONSE_BREACHED, RESOLUTION_BREACHED, FULFILLED

    customer = relationship("Customer")
    lead = relationship("Lead")
    sla = relationship("ServiceLevelAgreement")
    communications: Mapped[list[IssueCommunication]] = relationship(
        "IssueCommunication", back_populates="issue", cascade="all, delete-orphan", order_by="IssueCommunication.created_at.asc()"
    )

    __table_args__ = (
        Index("idx_issue_tenant_num", "tenant_id", "issue_number", unique=True),
        Index("idx_issue_tenant_status", "tenant_id", "status"),
    )


class IssueCommunication(Base, TenantMixin, TimestampMixin):
    """Threaded conversation message or internal staff note on an issue."""

    __tablename__ = "issue_communications"

    comm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.issue_id"), nullable=False, index=True
    )
    sender_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="AGENT"
    )  # AGENT, CUSTOMER, SYSTEM
    sender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal_note: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    issue: Mapped[Issue] = relationship("Issue", back_populates="communications")


class WarrantyClaim(Base, TenantMixin, TimestampMixin):
    """Customer warranty claim linked to serial numbers and delivery records."""

    __tablename__ = "warranty_claims"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_number: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    serial_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("serial_numbers.serial_id"), nullable=True
    )
    serial_number: Mapped[str] = mapped_column(String(128), nullable=False)
    claim_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"
    )  # OPEN, IN_REVIEW, APPROVED, REPLACED, REPAIRED, REJECTED, CLOSED
    complaint_description: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="REPAIR"
    )  # REPAIR, REPLACE_FREE, REPLACE_CHARGED, REJECT
    warranty_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="IN_WARRANTY"
    )  # IN_WARRANTY, OUT_OF_WARRANTY, NO_WARRANTY
    warranty_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolution_details: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer = relationship("Customer")
    item = relationship("Item")
    serial = relationship("SerialNo")

    __table_args__ = (
        Index("idx_war_tenant_num", "tenant_id", "claim_number", unique=True),
        Index("idx_war_tenant_serial", "tenant_id", "serial_number"),
    )
