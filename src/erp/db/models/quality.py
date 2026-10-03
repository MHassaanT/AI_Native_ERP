"""Quality Management and Inspection Domain Models (ERPNext Parity)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class QualityInspectionTemplate(Base, TenantMixin, TimestampMixin):
    """Reusable quality inspection template with standard tolerance parameters."""

    __tablename__ = "quality_inspection_templates"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    parameters: Mapped[List["QualityInspectionParameter"]] = relationship(
        "QualityInspectionParameter", back_populates="template", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_qi_template_tenant", "tenant_id", "template_name", unique=True),
    )


class QualityInspectionParameter(Base, TenantMixin, TimestampMixin):
    """Specification parameter with min/max acceptance boundaries."""

    __tablename__ = "quality_inspection_parameters"

    parameter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_inspection_templates.template_id"), nullable=False, index=True
    )
    parameter_name: Mapped[str] = mapped_column(String(128), nullable=False)
    specification: Mapped[str] = mapped_column(String(255), nullable=False)
    min_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    max_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), nullable=True)
    acceptance_tolerance: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    template: Mapped["QualityInspectionTemplate"] = relationship(
        "QualityInspectionTemplate", back_populates="parameters"
    )


class QualityInspection(Base, TenantMixin, TimestampMixin):
    """Physical or lab quality inspection record evaluating sample readings."""

    __tablename__ = "quality_inspections"

    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    inspection_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    inspection_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="INCOMING",  # INCOMING, IN_PROCESS, OUTGOING
    )
    reference_doc_type: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="PurchaseReceipt, JobCard, DeliveryNote, etc."
    )
    reference_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_size: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("1.0000"))
    inspected_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    inspection_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PASS"  # PASS, FAIL, REJECTED
    )
    readings: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True, doc="Recorded measurements vs spec: list of dicts"
    )
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    non_conformances: Mapped[List["NonConformance"]] = relationship(
        "NonConformance", back_populates="inspection", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_qi_tenant_num", "tenant_id", "inspection_number", unique=True),
        Index("idx_qi_tenant_status", "tenant_id", "status"),
    )


class NonConformance(Base, TenantMixin, TimestampMixin):
    """Formal Non-Conformance Report (NCR) for defective or out-of-spec goods/processes."""

    __tablename__ = "non_conformances"

    nc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nc_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="INSPECTION"  # INSPECTION, CUSTOMER_COMPLAINT, INTERNAL_AUDIT
    )
    inspection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_inspections.inspection_id"), nullable=True
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    item_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MAJOR"  # MINOR, MAJOR, CRITICAL
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    immediate_disposition: Mapped[str] = mapped_column(
        String(32), nullable=False, default="REWORK"  # REWORK, SCRAP, CONCESSION, RETURN_TO_SUPPLIER
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"  # OPEN, INVESTIGATING, CAPA_ASSIGNED, CLOSED
    )

    inspection: Mapped[Optional["QualityInspection"]] = relationship(
        "QualityInspection", back_populates="non_conformances"
    )
    actions: Mapped[List["QualityAction"]] = relationship(
        "QualityAction", back_populates="non_conformance", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_nc_tenant_num", "tenant_id", "nc_number", unique=True),
        Index("idx_nc_tenant_status", "tenant_id", "status"),
    )


class QualityAction(Base, TenantMixin, TimestampMixin):
    """Corrective and Preventive Action (CAPA) with 5-Whys root cause resolution."""

    __tablename__ = "quality_actions"

    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    capa_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    nc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("non_conformances.nc_id"), nullable=True, index=True
    )
    action_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="CORRECTIVE"  # CORRECTIVE, PREVENTIVE
    )
    root_cause_analysis: Mapped[str] = mapped_column(
        Text, nullable=False, doc="5-Whys or Ishikawa Fishbone breakdown notes"
    )
    action_plan: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    target_completion_date: Mapped[date] = mapped_column(Date, nullable=False)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"  # OPEN, IN_PROGRESS, IMPLEMENTED, VERIFIED_CLOSED
    )

    non_conformance: Mapped[Optional["NonConformance"]] = relationship(
        "NonConformance", back_populates="actions"
    )

    __table_args__ = (
        Index("idx_capa_tenant_num", "tenant_id", "capa_number", unique=True),
    )
