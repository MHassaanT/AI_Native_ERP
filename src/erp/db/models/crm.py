"""SQLAlchemy Models for Phase 6 CRM (Customer Relationship Management) Domain."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Lead(Base, TenantMixin, TimestampMixin):
    """Lead records prospect information and qualification scoring."""

    __tablename__ = "leads"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_name: Mapped[str] = mapped_column(String(255), nullable=False)
    salutation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    mobile_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    annual_revenue: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    no_of_employees: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    market_segment: Mapped[str | None] = mapped_column(String(128), nullable=True)
    territory: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(
        String(64), nullable=False, default="WEBSITE"
    )  # WALK_IN, WEBSITE, CAMPAIGN, COLD_CALL, REFERRAL
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="LEAD"
    )  # LEAD, OPEN, REPLIED, OPPORTUNITY, QUOTATION, INTERESTED, CONVERTED, DO_NOT_CONTACT
    lead_owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    qualification_status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UNQUALIFIED"
    )  # UNQUALIFIED, IN_PROCESS, QUALIFIED
    qualification_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.customer_id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer = relationship("Customer")

    __table_args__ = (
        Index("idx_lead_tenant_email", "tenant_id", "email_id"),
        Index("idx_lead_tenant_status", "tenant_id", "status"),
    )


class Opportunity(Base, TenantMixin, TimestampMixin):
    """Potential sales deal progressing through pipeline stages."""

    __tablename__ = "opportunities"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    opportunity_number: Mapped[str] = mapped_column(String(64), nullable=False)
    opportunity_from: Mapped[str] = mapped_column(
        String(32), nullable=False, default="LEAD"
    )  # LEAD, CUSTOMER
    party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    party_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="SALES"
    )  # SALES, SUPPORT, MAINTENANCE
    opportunity_owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sales_stage: Mapped[str] = mapped_column(
        String(64), nullable=False, default="PROSPECTING"
    )  # PROSPECTING, QUALIFICATION, PROPOSAL, NEGOTIATION, CLOSED_WON, CLOSED_LOST
    probability: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("10.00")
    )
    expected_closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    opportunity_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    order_lost_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list[OpportunityItem]] = relationship(
        "OpportunityItem", back_populates="opportunity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_opp_tenant_num", "tenant_id", "opportunity_number", unique=True),
        Index("idx_opp_tenant_stage", "tenant_id", "sales_stage"),
    )


class OpportunityItem(Base, TenantMixin, TimestampMixin):
    """Line item within a sales opportunity."""

    __tablename__ = "opportunity_items"

    opportunity_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.opportunity_id"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("1.0000")
    )
    rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    opportunity: Mapped[Opportunity] = relationship("Opportunity", back_populates="items")
    item = relationship("Item")


class Campaign(Base, TenantMixin, TimestampMixin):
    """Marketing campaign tracking reach and conversions."""

    __tablename__ = "campaigns"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="EMAIL"
    )  # EMAIL, WEB, TELEMARKETING, EVENT
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )  # DRAFT, ACTIVE, COMPLETED, CANCELLED
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    budget: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    actual_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    leads_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opportunities_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    email_steps: Mapped[list[EmailCampaign]] = relationship(
        "EmailCampaign", back_populates="campaign", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_camp_tenant_name", "tenant_id", "campaign_name"),)


class EmailCampaign(Base, TenantMixin, TimestampMixin):
    """Drip sequence email step tied to a campaign and lead."""

    __tablename__ = "email_campaigns"

    email_campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.campaign_id"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.lead_id"), nullable=True
    )
    sequence_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    template_body: Mapped[str] = mapped_column(Text, nullable=False)
    send_after_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING, SENT, OPENED, CLICKED, FAILED
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="email_steps")
    lead = relationship("Lead")


class Appointment(Base, TenantMixin, TimestampMixin):
    """Scheduled meeting/consultation with a lead or customer."""

    __tablename__ = "appointments"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appointment_with: Mapped[str] = mapped_column(
        String(32), nullable=False, default="LEAD"
    )  # LEAD, CUSTOMER
    party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    party_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_mins: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="SCHEDULED"
    )  # SCHEDULED, CONFIRMED, COMPLETED, CANCELLED
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (Index("idx_app_tenant_party", "tenant_id", "party_id"),)


class Contract(Base, TenantMixin, TimestampMixin):
    """Customer or vendor service agreement with fulfillment terms."""

    __tablename__ = "contracts"

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False)
    party_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="CUSTOMER"
    )  # CUSTOMER, SUPPLIER
    party_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    party_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )  # DRAFT, ACTIVE, EXPIRED, TERMINATED
    terms_and_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_contract_tenant_party", "tenant_id", "party_id"),)
