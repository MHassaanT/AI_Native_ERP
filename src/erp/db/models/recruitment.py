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
    text,
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
    source_review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    screening_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    screening_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_requirements: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
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
        ForeignKeyConstraint(
            ["source_review_id", "tenant_id"],
            ["recruitment_email_reviews.review_id", "recruitment_email_reviews.tenant_id"],
            ondelete="SET NULL (source_review_id)",
            name="fk_candidate_application_review_tenant",
        ),
        UniqueConstraint("source_review_id", name="uq_candidate_application_source_review"),
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


class RecruitmentEmailReview(Base, TenantMixin, TimestampMixin):
    """AI-classified inbound email awaiting a recruiter decision."""

    __tablename__ = "recruitment_email_reviews"

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    inbound_message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    applicant_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    applicant_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    desired_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    suggested_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="REVIEW_REQUIRED", server_default="REVIEW_REQUIRED"
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "inbound_message_id", name="uq_recruitment_email_review_message"
        ),
        UniqueConstraint("review_id", "tenant_id", name="uq_recruitment_email_review_tenant"),
        ForeignKeyConstraint(
            ["inbound_message_id", "tenant_id"],
            ["inbound_email_records.message_id", "inbound_email_records.tenant_id"],
            ondelete="CASCADE",
            name="fk_recruitment_email_review_inbound_tenant",
        ),
        ForeignKeyConstraint(
            ["suggested_role_id", "tenant_id"],
            ["recruitment_roles.role_id", "recruitment_roles.tenant_id"],
            ondelete="SET NULL (suggested_role_id)",
            name="fk_recruitment_email_review_role_tenant",
        ),
        CheckConstraint(
            "status IN ('REVIEW_REQUIRED', 'APPLICATION_CREATED', 'ADDED_TO_POOL', 'NOT_APPLICATION', 'DISMISSED')",
            name="ck_recruitment_email_review_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_recruitment_email_review_confidence",
        ),
        Index("idx_recruitment_email_review_queue", "tenant_id", "status", "created_at"),
    )


class CandidateTalentPoolProspect(Base, TenantMixin, TimestampMixin):
    """Unassigned candidate lead retained for future recruiter-reviewed matching."""

    __tablename__ = "candidate_talent_pool_prospects"

    prospect_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    applicant_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    applicant_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    desired_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="POOLED", server_default="POOLED"
    )
    matched_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    match_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_evidence: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["source_review_id", "tenant_id"],
            ["recruitment_email_reviews.review_id", "recruitment_email_reviews.tenant_id"],
            ondelete="CASCADE",
            name="fk_talent_pool_review_tenant",
        ),
        UniqueConstraint("source_review_id", name="uq_talent_pool_source_review"),
        ForeignKeyConstraint(
            ["matched_role_id", "tenant_id"],
            ["recruitment_roles.role_id", "recruitment_roles.tenant_id"],
            ondelete="SET NULL (matched_role_id)",
            name="fk_talent_pool_role_tenant",
        ),
        CheckConstraint(
            "status IN ('POOLED', 'TRANSFERRED', 'DISMISSED')",
            name="ck_talent_pool_prospect_status",
        ),
        CheckConstraint(
            "match_score IS NULL OR (match_score >= 0 AND match_score <= 100)",
            name="ck_talent_pool_match_score",
        ),
        Index("idx_talent_pool_tenant_status", "tenant_id", "status", "created_at"),
    )
