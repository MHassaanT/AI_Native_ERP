"""SQLAlchemy database models for Autonomous AI Workforce, HITL Governance, and Communications."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from erp.db.models.base import Base


class AutonomyLevel(str, Enum):
    AUTONOMOUS = "AUTONOMOUS"          # Fully autonomous execution of low & medium risk tasks
    HITL_REQUIRED = "HITL_REQUIRED"    # Requires human approval for all mutations
    DISABLED = "DISABLED"              # Agent paused / disabled


class AgentDomain(str, Enum):
    PROCUREMENT = "PROCUREMENT"
    SALES = "SALES"
    INVENTORY = "INVENTORY"
    HR_PAYROLL = "HR_PAYROLL"
    MANUFACTURING = "MANUFACTURING"
    FINANCE = "FINANCE"
    SUPPORT_QUALITY = "SUPPORT_QUALITY"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    EXPIRED = "EXPIRED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChannelType(str, Enum):
    WHATSAPP = "WHATSAPP"
    GMAIL = "GMAIL"
    INTERNAL = "INTERNAL"


class AgentDefinition(Base):
    __tablename__ = "agent_definitions"

    agent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(64), nullable=False)
    domain = Column(SQLEnum(AgentDomain), nullable=False)
    description = Column(Text, nullable=False)
    autonomy_level = Column(SQLEnum(AutonomyLevel), nullable=False, default=AutonomyLevel.AUTONOMOUS)
    trigger_type = Column(String(32), nullable=False, default="SCHEDULED")  # SCHEDULED, EVENT_DRIVEN, MANUAL
    cron_expression = Column(String(64), nullable=True)
    interval_seconds = Column(Integer, nullable=True, default=300)
    system_prompt = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    config = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    runs = relationship("AgentExecutionRun", back_populates="agent", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_agent_tenant_slug", "tenant_id", "slug", unique=True),
    )


class AgentExecutionRun(Base):
    __tablename__ = "agent_execution_runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_definitions.agent_id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(128), nullable=False)
    trigger_type = Column(String(32), nullable=False)  # MANUAL, SCHEDULED, EVENT
    trigger_context = Column(JSONB, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="RUNNING")  # RUNNING, COMPLETED, FAILED, AWAITING_APPROVAL
    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    execution_metrics = Column(JSONB, nullable=False, default=dict)  # tokens, cost, duration_ms, tool_calls_count
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("AgentDefinition", back_populates="runs")
    step_logs = relationship("AgentStepLog", back_populates="run", cascade="all, delete-orphan")
    approvals = relationship("AgentApproval", back_populates="run", cascade="all, delete-orphan")


class AgentStepLog(Base):
    __tablename__ = "agent_step_logs"

    step_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_execution_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False, default=1)
    node_name = Column(String(64), nullable=False)
    reasoning_thought = Column(Text, nullable=True)
    tool_name = Column(String(64), nullable=True)
    tool_arguments = Column(JSONB, nullable=True)
    tool_output = Column(JSONB, nullable=True)
    status = Column(String(32), nullable=False, default="COMPLETED")  # COMPLETED, FAILED, SKIPPED
    duration_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("AgentExecutionRun", back_populates="step_logs")


class AgentApproval(Base):
    __tablename__ = "agent_approvals"

    approval_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_execution_runs.run_id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), nullable=True)
    agent_name = Column(String(128), nullable=False)
    domain = Column(SQLEnum(AgentDomain), nullable=False)
    action_type = Column(String(64), nullable=False)  # CREATE_PURCHASE_ORDER, POST_GL_JOURNAL, DISBURSE_PAYROLL, etc.
    action_payload = Column(JSONB, nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False, default=RiskLevel.HIGH)
    required_role = Column(String(32), nullable=False, default="Admin")  # Admin, Finance, HR, Operations
    ai_rationale = Column(Text, nullable=False)
    status = Column(SQLEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING, index=True)
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    modified_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    run = relationship("AgentExecutionRun", back_populates="approvals")


class AgentCommunication(Base):
    __tablename__ = "agent_communications"

    comm_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    run_id = Column(UUID(as_uuid=True), nullable=True)
    agent_name = Column(String(128), nullable=False)
    channel = Column(SQLEnum(ChannelType), nullable=False)
    recipient = Column(String(256), nullable=False)  # phone number or email
    subject = Column(String(256), nullable=True)
    body = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="SENT")  # SENT, DELIVERED, FAILED, QUEUED
    external_message_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
