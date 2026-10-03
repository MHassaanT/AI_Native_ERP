"""Manufacturing and Shop-Floor Execution (MES) Domain Models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class Workstation(Base, TenantMixin, TimestampMixin):
    """Factory machine or assembly station registry."""

    __tablename__ = "workstations"

    workstation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workstation_code: Mapped[str] = mapped_column(String(64), nullable=False)
    workstation_name: Mapped[str] = mapped_column(String(128), nullable=False)
    workstation_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="GENERAL"  # CNC, LATHE, WELDING, ASSEMBLY, QC, PACKAGING
    )
    production_capacity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("1.0000"), doc="Capacity units/hour"
    )
    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("45.0000")
    )
    electricity_cost_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    consumable_cost_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    rent_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="OPERATIONAL",  # OPERATIONAL, IN_USE, MAINTENANCE, FAULT, IDLE
    )
    iot_device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    health_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("100.00")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_ws_tenant_code", "tenant_id", "workstation_code", unique=True),
        Index("idx_ws_status", "tenant_id", "status"),
    )


class Operation(Base, TenantMixin, TimestampMixin):
    """Standard operation master catalog (e.g. Cutting, CNC Machining, Assembly)."""

    __tablename__ = "operations"

    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    operation_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_workstation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstations.workstation_id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    default_workstation: Mapped["Workstation | None"] = relationship()

    __table_args__ = (
        Index("idx_op_tenant_name", "tenant_id", "operation_name", unique=True),
    )


class Routing(Base, TenantMixin, TimestampMixin):
    """Sequence of operations required to manufacture a product."""

    __tablename__ = "routings"

    routing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    routing_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    operations: Mapped[list["RoutingOperation"]] = relationship(
        back_populates="routing", cascade="all, delete-orphan", order_by="RoutingOperation.sequence_id"
    )

    __table_args__ = (
        Index("idx_routing_tenant_name", "tenant_id", "routing_name", unique=True),
    )


class RoutingOperation(Base, TenantMixin, TimestampMixin):
    """Individual operational step within a production routing."""

    __tablename__ = "routing_operations"

    routing_operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    routing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routings.routing_id"), nullable=False
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operations.operation_id"), nullable=False
    )
    workstation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstations.workstation_id"), nullable=True
    )
    sequence_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    time_in_mins: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("15.0000")
    )
    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    batch_size: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("1.0000")
    )

    routing: Mapped["Routing"] = relationship(back_populates="operations")
    operation: Mapped["Operation"] = relationship()
    workstation: Mapped["Workstation | None"] = relationship()


class BOM(Base, TenantMixin, TimestampMixin):
    """Bill of Materials specifying multi-level component formulas and routings."""

    __tablename__ = "boms"

    bom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bom_number: Mapped[str] = mapped_column(String(64), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    routing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routings.routing_id"), nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("1.0000")
    )
    raw_material_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    operating_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    scrap_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    with_operations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    items: Mapped[list["BOMItem"]] = relationship(
        back_populates="bom", cascade="all, delete-orphan", foreign_keys="[BOMItem.bom_id]"
    )
    operations: Mapped[list["BOMOperation"]] = relationship(
        back_populates="bom", cascade="all, delete-orphan", order_by="BOMOperation.sequence_id"
    )
    scrap_items: Mapped[list["BOMScrapItem"]] = relationship(
        back_populates="bom", cascade="all, delete-orphan"
    )
    routing: Mapped["Routing | None"] = relationship()

    __table_args__ = (
        Index("idx_bom_tenant_number", "tenant_id", "bom_number", unique=True),
        Index("idx_bom_item_default", "tenant_id", "item_id", "is_default"),
    )


class BOMItem(Base, TenantMixin, TimestampMixin):
    """Component line in Bill of Materials, supporting sub-assemblies and scrap."""

    __tablename__ = "bom_items"

    bom_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boms.bom_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    bom_sub_assembly_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boms.bom_id"), nullable=True, doc="Sub-assembly BOM for multi-level hierarchy"
    )
    operation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operations.operation_id"), nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    scrap_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )

    bom: Mapped["BOM"] = relationship(back_populates="items", foreign_keys=[bom_id])
    operation: Mapped["Operation | None"] = relationship()


class BOMOperation(Base, TenantMixin, TimestampMixin):
    """Operational step attached to a Bill of Materials."""

    __tablename__ = "bom_operations"

    bom_op_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boms.bom_id"), nullable=False
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operations.operation_id"), nullable=False
    )
    workstation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstations.workstation_id"), nullable=True
    )
    sequence_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    time_in_mins: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("15.0000")
    )
    hourly_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    operating_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    batch_size: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("1.0000")
    )

    bom: Mapped["BOM"] = relationship(back_populates="operations")
    operation: Mapped["Operation"] = relationship()
    workstation: Mapped["Workstation | None"] = relationship()


class BOMScrapItem(Base, TenantMixin, TimestampMixin):
    """Byproduct or waste scrap item recovered from production."""

    __tablename__ = "bom_scrap_items"

    scrap_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boms.bom_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    stock_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=Decimal("0.0000"))

    bom: Mapped["BOM"] = relationship(back_populates="scrap_items")


class ProductionPlan(Base, TenantMixin, TimestampMixin):
    """Material Requirements Planning (MRP) and Production Planning header."""

    __tablename__ = "production_plans"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_number: Mapped[str] = mapped_column(String(64), nullable=False)
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"  # DRAFT, SUBMITTED, IN_PROCESS, COMPLETED, CANCELLED
    )
    total_planned_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    items: Mapped[list["ProductionPlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_pplan_tenant_num", "tenant_id", "plan_number", unique=True),
        Index("idx_pplan_status", "tenant_id", "status"),
    )


class ProductionPlanItem(Base, TenantMixin, TimestampMixin):
    """Target item requirement inside a Production Plan."""

    __tablename__ = "production_plan_items"

    plan_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("production_plans.plan_id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    bom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boms.bom_id"), nullable=True
    )
    sales_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    planned_qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    produced_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    plan: Mapped["ProductionPlan"] = relationship(back_populates="items")


class WorkOrder(Base, TenantMixin, TimestampMixin):
    """Production Work Order tracking shop floor staging, WIP, and completion."""

    __tablename__ = "work_orders"

    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    work_order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    production_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("production_plans.plan_id"), nullable=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.item_id"), nullable=False
    )
    bom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boms.bom_id"), nullable=True
    )
    workstation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstations.workstation_id"), nullable=True
    )
    source_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True, doc="Stores / Raw Materials"
    )
    wip_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True, doc="Work In Progress"
    )
    fg_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True, doc="Target Finished Goods"
    )
    scrap_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.warehouse_id"), nullable=True
    )
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    produced_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    planned_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    planned_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lead_time_mins: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    material_transferred_for_mfg: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="DRAFT",  # DRAFT, SCHEDULED, IN_PROCESS, COMPLETED, STOPPED, CANCELLED
    )

    job_cards: Mapped[list["JobCard"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan", order_by="JobCard.sequence_id"
    )

    __table_args__ = (
        Index("idx_wo_tenant_number", "tenant_id", "work_order_number", unique=True),
        Index("idx_wo_status", "tenant_id", "status"),
    )


class JobCard(Base, TenantMixin, TimestampMixin):
    """Operation traveler dispatched to machine and operator on the plant floor (MES)."""

    __tablename__ = "job_cards"

    job_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_card_number: Mapped[str] = mapped_column(String(64), nullable=False)
    work_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_orders.work_order_id"), nullable=False
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operations.operation_id"), nullable=False
    )
    workstation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstations.workstation_id"), nullable=True
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=True, doc="Assigned operator"
    )
    sequence_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    for_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    total_completed_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    total_scrap_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PENDING",  # PENDING, WORK_IN_PROGRESS, PAUSED, COMPLETED, CANCELLED
    )
    started_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_timer_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Timestamp when current session started"
    )
    total_time_in_mins: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    work_order: Mapped["WorkOrder"] = relationship(back_populates="job_cards")
    operation: Mapped["Operation"] = relationship()
    workstation: Mapped["Workstation | None"] = relationship()
    time_logs: Mapped[list["JobCardTimeLog"]] = relationship(
        back_populates="job_card", cascade="all, delete-orphan", order_by="JobCardTimeLog.from_time.desc()"
    )

    __table_args__ = (
        Index("idx_jc_tenant_number", "tenant_id", "job_card_number", unique=True),
        Index("idx_jc_wo_seq", "tenant_id", "work_order_id", "sequence_id"),
        Index("idx_jc_status", "tenant_id", "status"),
    )


class JobCardTimeLog(Base, TenantMixin, TimestampMixin):
    """Detailed start/stop punch clock log for operator sessions on a Job Card."""

    __tablename__ = "job_card_time_logs"

    time_log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_cards.job_card_id"), nullable=False
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=True
    )
    from_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_in_mins: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    completed_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    scrap_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )

    job_card: Mapped["JobCard"] = relationship(back_populates="time_logs")


class DowntimeEntry(Base, TenantMixin, TimestampMixin):
    """Machine downtime event recording breakdowns, tool wear, and maintenance stops."""

    __tablename__ = "downtime_entries"

    downtime_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    downtime_number: Mapped[str] = mapped_column(String(64), nullable=False)
    workstation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstations.workstation_id"), nullable=False
    )
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.employee_id"), nullable=True
    )
    from_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_mins: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000")
    )
    reason: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="MECHANICAL_BREAKDOWN",  # MECHANICAL_BREAKDOWN, ELECTRICAL_FAULT, TOOL_WEAR, SETUP_CHANGEOVER, MATERIAL_STARVATION, OPERATOR_UNAVAILABLE, OTHER
    )
    fault_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"  # OPEN, RESOLVED
    )

    workstation: Mapped["Workstation"] = relationship()

    __table_args__ = (
        Index("idx_downtime_tenant_num", "tenant_id", "downtime_number", unique=True),
        Index("idx_downtime_ws_status", "tenant_id", "workstation_id", "status"),
    )


class MaintenanceTicket(Base, TenantMixin, TimestampMixin):
    """Predictive or corrective equipment maintenance ticket."""

    __tablename__ = "maintenance_tickets"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_number: Mapped[str] = mapped_column(String(64), nullable=False)
    workstation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workstations.workstation_id"), nullable=False
    )
    trigger_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PREDICTIVE_ANOMALY",  # PREDICTIVE_ANOMALY, MANUAL, SCHEDULED
    )
    fault_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="MEDIUM",  # LOW, MEDIUM, HIGH, CRITICAL
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="OPEN",  # OPEN, IN_PROGRESS, RESOLVED, CLOSED
    )

    workstation: Mapped["Workstation"] = relationship()

    __table_args__ = (
        Index("idx_maint_tenant_number", "tenant_id", "ticket_number", unique=True),
    )
