"""Persistence operations for tenant-scoped recruitment workflows."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.recruitment import CandidateApplication, RecruitmentRole


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


recruitment_service = RecruitmentService()
