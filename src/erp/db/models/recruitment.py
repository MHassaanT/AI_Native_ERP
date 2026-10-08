"""Tenant-scoped recruitment roles and candidate applications."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from erp.db.models.base import Base, TenantMixin, TimestampMixin


class RecruitmentRole(Base, TenantMixin, TimestampMixin):
    """A tenant's job opening and its screening criteria."""

    __tablename__ = "recruitment_roles"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN")

    __table_args__ = (
        UniqueConstraint("role_id", "tenant_id", name="uq_recruitment_role_tenant"),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_recruitment_role_status"),
        Index("idx_recruitment_roles_tenant_status", "tenant_id", "status", "created_at"),
    )


class CandidateApplication(Base, TenantMixin, TimestampMixin):
    """Extracted resume text and reviewable AI screening results for a role."""

    __tablename__ = "candidate_applications"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    applicant_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    applicant_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    resume_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    resume_content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="READY")
    screening_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    screening_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_requirements: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    interview_email_subject: Mapped[str | None] = mapped_column(String(998), nullable=True)
    interview_email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["role_id", "tenant_id"],
            ["recruitment_roles.role_id", "recruitment_roles.tenant_id"],
            ondelete="CASCADE",
            name="fk_candidate_application_role_tenant",
        ),
        CheckConstraint(
            "status IN ('READY', 'EVALUATED')",
            name="ck_candidate_application_status",
        ),
        CheckConstraint(
            "screening_score IS NULL OR (screening_score >= 0 AND screening_score <= 100)",
            name="ck_candidate_application_score",
        ),
        Index(
            "idx_candidate_applications_tenant_role",
            "tenant_id",
            "role_id",
            "created_at",
        ),
        Index(
            "idx_candidate_applications_tenant_score",
            "tenant_id",
            "screening_score",
        ),
    )
