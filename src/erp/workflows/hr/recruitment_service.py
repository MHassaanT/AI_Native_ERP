"""Persistence operations for tenant-scoped recruitment workflows."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.events import InboundEmailRecord
from erp.db.models.recruitment import (
    CandidateApplication,
    CandidateTalentPoolProspect,
    RecruitmentEmailReview,
    RecruitmentRole,
)


class RecruitmentService:
    """Creates and retrieves job openings and candidate applications."""

    async def create_role(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        title: str,
        description: str,
        requirements: str,
    ) -> RecruitmentRole:
        role = RecruitmentRole(
            tenant_id=tenant_id,
            title=title.strip(),
            description=description.strip(),
            requirements=requirements.strip(),
        )
        db.add(role)
        await db.flush()
        return role

    async def list_roles(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(RecruitmentRole).where(RecruitmentRole.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(RecruitmentRole.status == status)
        stmt = stmt.order_by(RecruitmentRole.created_at.desc())
        roles = list((await db.execute(stmt)).scalars().all())
        return [
            {
                "role_id": role.role_id,
                "title": role.title,
                "description": role.description,
                "requirements": role.requirements,
                "status": role.status,
                "created_at": role.created_at,
            }
            for role in roles
        ]

    async def get_role(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> RecruitmentRole | None:
        stmt = select(RecruitmentRole).where(
            RecruitmentRole.tenant_id == tenant_id,
            RecruitmentRole.role_id == role_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def close_role(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> RecruitmentRole | None:
        role = await self.get_role(db, tenant_id, role_id)
        if role:
            role.status = "CLOSED"
            await db.flush()
        return role

    async def create_application(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
        applicant_name: str | None,
        applicant_email: str | None,
        resume_filename: str,
        resume_content_type: str,
        resume_text: str,
        source_review_id: uuid.UUID | None = None,
    ) -> CandidateApplication:
        role = await self.get_role(db, tenant_id, role_id)
        if role is None:
            raise ValueError("Job opening not found.")
        if role.status != "OPEN":
            raise ValueError("Applications cannot be added to a closed job opening.")

        application = CandidateApplication(
            tenant_id=tenant_id,
            role_id=role_id,
            applicant_name=applicant_name.strip() if applicant_name else None,
            applicant_email=applicant_email.strip() if applicant_email else None,
            resume_filename=resume_filename,
            resume_content_type=resume_content_type,
            resume_text=resume_text,
            source_review_id=source_review_id,
        )
        db.add(application)
        await db.flush()
        return application

    async def list_applications(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID | None = None,
    ) -> list[CandidateApplication]:
        stmt = select(CandidateApplication).where(CandidateApplication.tenant_id == tenant_id)
        if role_id:
            stmt = stmt.where(CandidateApplication.role_id == role_id)
        stmt = stmt.order_by(
            CandidateApplication.screening_score.desc().nullslast(),
            CandidateApplication.created_at.desc(),
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_application(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> CandidateApplication | None:
        stmt = select(CandidateApplication).where(
            CandidateApplication.tenant_id == tenant_id,
            CandidateApplication.application_id == application_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def delete_application(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> bool:
        application = await self.get_application(db, tenant_id, application_id)
        if application is None:
            return False
        await db.delete(application)
        await db.flush()
        return True

    async def list_email_inbox(
        self, db: AsyncSession, tenant_id: uuid.UUID, limit: int = 50
    ) -> list[InboundEmailRecord]:
        stmt = (
            select(InboundEmailRecord)
            .outerjoin(
                RecruitmentEmailReview,
                (RecruitmentEmailReview.inbound_message_id == InboundEmailRecord.message_id)
                & (RecruitmentEmailReview.tenant_id == tenant_id),
            )
            .where(
                InboundEmailRecord.tenant_id == tenant_id,
                InboundEmailRecord.status.in_(
                    ("HUMAN_REVIEW_REQUIRED", "ACCEPTED_FOR_MANUAL_PROCESSING")
                ),
                RecruitmentEmailReview.review_id.is_(None),
            )
            .order_by(InboundEmailRecord.received_at.desc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_inbound_email(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        message_id: str,
        *,
        lock: bool = False,
    ) -> InboundEmailRecord | None:
        stmt = select(InboundEmailRecord).where(
            InboundEmailRecord.tenant_id == tenant_id,
            InboundEmailRecord.message_id == message_id,
            InboundEmailRecord.status.in_(
                ("HUMAN_REVIEW_REQUIRED", "ACCEPTED_FOR_MANUAL_PROCESSING")
            ),
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalar_one_or_none()

    async def get_email_review_by_message(
        self, db: AsyncSession, tenant_id: uuid.UUID, message_id: str
    ) -> RecruitmentEmailReview | None:
        stmt = select(RecruitmentEmailReview).where(
            RecruitmentEmailReview.tenant_id == tenant_id,
            RecruitmentEmailReview.inbound_message_id == message_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def create_email_review(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        message_id: str,
        *,
        applicant_name: str | None,
        applicant_email: str | None,
        desired_role: str | None,
        suggested_role_id: uuid.UUID | None,
        confidence: float,
        summary: str,
        evidence: list[dict[str, str]],
        resume_text: str,
        is_application: bool,
    ) -> RecruitmentEmailReview:
        review = RecruitmentEmailReview(
            tenant_id=tenant_id,
            inbound_message_id=message_id,
            applicant_name=applicant_name,
            applicant_email=applicant_email,
            desired_role=desired_role,
            suggested_role_id=suggested_role_id,
            confidence=confidence,
            summary=summary,
            evidence=evidence,
            resume_text=resume_text,
            status="REVIEW_REQUIRED" if is_application else "NOT_APPLICATION",
        )
        db.add(review)
        await db.flush()
        return review

    async def list_email_reviews(
        self, db: AsyncSession, tenant_id: uuid.UUID
    ) -> list[RecruitmentEmailReview]:
        stmt = (
            select(RecruitmentEmailReview)
            .where(
                RecruitmentEmailReview.tenant_id == tenant_id,
                RecruitmentEmailReview.status == "REVIEW_REQUIRED",
            )
            .order_by(RecruitmentEmailReview.created_at.desc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_email_review(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        review_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> RecruitmentEmailReview | None:
        stmt = select(RecruitmentEmailReview).where(
            RecruitmentEmailReview.review_id == review_id,
            RecruitmentEmailReview.tenant_id == tenant_id,
        )
        if lock:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalar_one_or_none()

    async def add_review_to_talent_pool(
        self, db: AsyncSession, tenant_id: uuid.UUID, review_id: uuid.UUID
    ) -> CandidateTalentPoolProspect:
        review = await self.get_email_review(db, tenant_id, review_id, lock=True)
        if review is None:
            raise ValueError("Email review not found.")
        if review.status != "REVIEW_REQUIRED":
            raise ValueError("Email review is no longer awaiting a recruiter decision.")
        prospect = CandidateTalentPoolProspect(
            tenant_id=tenant_id,
            source_review_id=review.review_id,
            applicant_name=review.applicant_name,
            applicant_email=review.applicant_email,
            desired_role=review.desired_role,
            profile_text=review.resume_text,
        )
        db.add(prospect)
        review.status = "ADDED_TO_POOL"
        await db.flush()
        return prospect

    async def list_talent_pool(
        self, db: AsyncSession, tenant_id: uuid.UUID
    ) -> list[CandidateTalentPoolProspect]:
        stmt = (
            select(CandidateTalentPoolProspect)
            .where(
                CandidateTalentPoolProspect.tenant_id == tenant_id,
                CandidateTalentPoolProspect.status == "POOLED",
            )
            .order_by(
                CandidateTalentPoolProspect.match_score.desc().nullslast(),
                CandidateTalentPoolProspect.created_at.desc(),
            )
        )
        return list((await db.execute(stmt)).scalars().all())

    async def save_talent_pool_match(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        prospect_id: uuid.UUID,
        role_id: uuid.UUID,
        *,
        score: int,
        summary: str,
        evidence: list[dict[str, str]],
    ) -> CandidateTalentPoolProspect | None:
        prospect = (
            await db.execute(
                select(CandidateTalentPoolProspect)
                .where(
                    CandidateTalentPoolProspect.prospect_id == prospect_id,
                    CandidateTalentPoolProspect.tenant_id == tenant_id,
                    CandidateTalentPoolProspect.status == "POOLED",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if prospect is None:
            return None
        prospect.matched_role_id = role_id
        prospect.match_score = score
        prospect.match_summary = summary
        prospect.match_evidence = evidence
        prospect.matched_at = datetime.now(UTC)
        await db.flush()
        return prospect

    async def transfer_talent_pool_prospect(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        prospect_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> CandidateApplication:
        prospect = (
            await db.execute(
                select(CandidateTalentPoolProspect)
                .where(
                    CandidateTalentPoolProspect.prospect_id == prospect_id,
                    CandidateTalentPoolProspect.tenant_id == tenant_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if prospect is None:
            raise ValueError("Talent-pool prospect not found.")
        if prospect.status != "POOLED":
            raise ValueError("Talent-pool prospect is no longer available.")
        application = await self.create_application(
            db,
            tenant_id,
            role_id,
            prospect.applicant_name,
            prospect.applicant_email,
            "email-application.txt",
            "message/rfc822",
            prospect.profile_text,
            source_review_id=prospect.source_review_id,
        )
        prospect.status = "TRANSFERRED"
        prospect.matched_role_id = role_id
        return application

    async def dismiss_email_review(
        self, db: AsyncSession, tenant_id: uuid.UUID, review_id: uuid.UUID
    ) -> RecruitmentEmailReview | None:
        review = await self.get_email_review(db, tenant_id, review_id, lock=True)
        if review is None or review.status != "REVIEW_REQUIRED":
            return None
        review.status = "DISMISSED"
        await db.flush()
        return review

    async def dismiss_talent_pool_prospect(
        self, db: AsyncSession, tenant_id: uuid.UUID, prospect_id: uuid.UUID
    ) -> CandidateTalentPoolProspect | None:
        prospect = (
            await db.execute(
                select(CandidateTalentPoolProspect)
                .where(
                    CandidateTalentPoolProspect.prospect_id == prospect_id,
                    CandidateTalentPoolProspect.tenant_id == tenant_id,
                    CandidateTalentPoolProspect.status == "POOLED",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if prospect is None:
            return None
        prospect.status = "DISMISSED"
        await db.flush()
        return prospect


recruitment_service = RecruitmentService()
