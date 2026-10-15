"""Autonomous HR Recruitment Service.

Orchestrates the full recruitment pipeline:
1. Poll Gmail for new applications
2. Parse and classify emails
3. Match against open roles
4. Screen candidates with AI
5. Send acknowledgment and interview emails
6. Manage talent pool
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.recruitment import (
    RecruitmentRole,
    CandidateApplication,
    CandidateTalentPoolProspect,
    RecruitmentEmailReview,
)
from erp.db.models.hr import Employee
from erp.ai.hr_screening import (
    evaluate_candidate,
    analyze_application_email,
    match_talent_pool_candidate,
    ScreeningResult,
)

logger = logging.getLogger(__name__)


class HRRecruitmentService:
    """Autonomous recruitment orchestration service."""

    def __init__(self):
        self._running = False
        self._last_cycle_at: datetime | None = None
        self._stats = {
            "total_emails_processed": 0,
            "total_applications_created": 0,
            "total_prospects_created": 0,
            "total_interview_emails_sent": 0,
            "errors": [],
        }

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_cycle_at(self) -> datetime | None:
        return self._last_cycle_at

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            **self._stats,
        }

    async def run_autonomous_cycle(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Run one full autonomous recruitment cycle."""
        self._running = True
        cycle_results = {
            "emails_processed": 0,
            "applications_created": 0,
            "prospects_created": 0,
            "interviews_sent": 0,
            "errors": [],
        }

        try:
            # Step 1: Process pending email reviews
            email_results = await self._process_email_intake(db, tenant_id)
            cycle_results["emails_processed"] = email_results["processed"]
            cycle_results["applications_created"] += email_results["applications"]
            cycle_results["prospects_created"] += email_results["prospects"]

            # Step 2: Screen pending applications
            screening_results = await self._screen_pending_applications(db, tenant_id)
            cycle_results["applications_created"] += screening_results["screened"]

            # Step 3: Process talent pool matches
            pool_results = await self._process_talent_pool(db, tenant_id)
            cycle_results["prospects_created"] += pool_results["matched"]

            # Step 4: Send pending interview emails
            interview_results = await self._send_pending_interviews(db, tenant_id)
            cycle_results["interviews_sent"] = interview_results["sent"]

            self._last_cycle_at = datetime.now(timezone.utc)
            self._stats["total_emails_processed"] += cycle_results["emails_processed"]
            self._stats["total_applications_created"] += cycle_results["applications_created"]
            self._stats["total_prospects_created"] += cycle_results["prospects_created"]
            self._stats["total_interview_emails_sent"] += cycle_results["interviews_sent"]

        except Exception as e:
            error_msg = f"Autonomous cycle failed: {e!s}"
            logger.error(error_msg)
            cycle_results["errors"].append(error_msg)
            self._stats["errors"].append(error_msg)
        finally:
            self._running = False

        return cycle_results

    async def _process_email_intake(
        self, db: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, int]:
        """Process unprocessed email intake reviews."""
        results = {"processed": 0, "applications": 0, "prospects": 0}

        # Find reviews pending decision
        stmt = select(RecruitmentEmailReview).where(
            and_(
                RecruitmentEmailReview.tenant_id == tenant_id,
                RecruitmentEmailReview.status == "REVIEW_REQUIRED",
            )
        )
        reviews = (await db.execute(stmt)).scalars().all()

        for review in reviews:
            try:
                # Use the review's classification directly (already done when the review was created)
                if review.summary:  # If there's a summary, it's likely an application
                    # Find best matching open role
                    role = await self._find_best_role(
                        db, tenant_id, review.desired_role or ""
                    )

                    if role and review.confidence >= 0.7:
                        # Auto-create application
                        application = CandidateApplication(
                            tenant_id=tenant_id,
                            role_id=role.role_id,
                            applicant_name=review.applicant_name,
                            applicant_email=review.applicant_email,
                            resume_filename="email_resume.txt",
                            resume_content_type="text/plain",
                            resume_text=review.resume_text,
                            status="READY",
                            source_review_id=review.review_id,
                        )
                        db.add(application)
                        review.status = "APPLICATION_CREATED"
                        review.suggested_role_id = role.role_id
                        results["applications"] += 1
                    else:
                        # Add to talent pool for later
                        prospect = CandidateTalentPoolProspect(
                            tenant_id=tenant_id,
                            source_review_id=review.review_id,
                            status="PENDING_REVIEW",
                            applicant_name=review.applicant_name,
                            applicant_email=review.applicant_email,
                            desired_role=review.desired_role,
                            profile_text=review.resume_text,
                        )
                        db.add(prospect)
                        review.status = "ADDED_TO_POOL"
                        results["prospects"] += 1
                else:
                    review.status = "DISMISSED"

                results["processed"] += 1

            except Exception as e:
                logger.error(f"Failed to process review {review.review_id}: {e}")
                review.status = "DISMISSED"

        await db.flush()
        return results

    async def _screen_pending_applications(
        self, db: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, int]:
        """Screen applications that haven't been evaluated yet."""
        results = {"screened": 0}

        stmt = select(CandidateApplication).where(
            and_(
                CandidateApplication.tenant_id == tenant_id,
                CandidateApplication.status == "READY",
            )
        )
        applications = (await db.execute(stmt)).scalars().all()

        for app in applications:
            try:
                # Get the role requirements
                role_stmt = select(RecruitmentRole).where(
                    RecruitmentRole.role_id == app.role_id
                )
                role = (await db.execute(role_stmt)).scalar_one_or_none()

                if not role:
                    continue

                # Run AI screening
                screening: ScreeningResult = await evaluate_candidate(
                    role_title=role.title,
                    role_description=role.description,
                    role_requirements=role.requirements,
                    resume_text=app.resume_text or "",
                )

                app.screening_score = screening.score
                app.screening_summary = screening.summary
                app.matched_requirements = screening.matched_requirements
                app.evidence = [e.model_dump() for e in screening.evidence]
                app.status = "EVALUATED"

                # Auto-schedule interview if score >= 75 (not yet implemented)
                if screening.score >= 75 and app.applicant_email:
                    # TODO: Implement interview scheduling
                    pass

                results["screened"] += 1

            except Exception as e:
                logger.error(f"Failed to screen application {app.application_id}: {e}")

        await db.flush()
        return results

    async def _process_talent_pool(
        self, db: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, int]:
        """Match talent pool prospects against open roles."""
        results = {"matched": 0}

        # Get open roles
        roles_stmt = select(RecruitmentRole).where(
            and_(
                RecruitmentRole.tenant_id == tenant_id,
                RecruitmentRole.status == "OPEN",
            )
        )
        roles = (await db.execute(roles_stmt)).scalars().all()

        if not roles:
            return results

        # Get unmatched prospects
        prospects_stmt = select(CandidateTalentPoolProspect).where(
            and_(
                CandidateTalentPoolProspect.tenant_id == tenant_id,
                CandidateTalentPoolProspect.status == "POOLED",
                CandidateTalentPoolProspect.match_score.is_(None),
            )
        )
        prospects = (await db.execute(prospects_stmt)).scalars().all()

        for prospect in prospects:
            try:
                best_match = None
                best_score = 0

                for role in roles:
                    match_result = await match_talent_pool_candidate(
                        role_title=role.title,
                        role_description=role.description,
                        role_requirements=role.requirements,
                        profile_text=prospect.profile_text or "",
                    )

                    if match_result.score > best_score:
                        best_score = match_result.score
                        best_match = (role, match_result)

                if best_match and best_score >= 50:
                    role, match_result = best_match
                    prospect.matched_role_id = role.role_id
                    prospect.match_score = match_result.score
                    prospect.match_summary = match_result.summary
                    prospect.match_evidence = [
                        e.model_dump() for e in match_result.evidence
                    ]
                    results["matched"] += 1

            except Exception as e:
                logger.error(f"Failed to match prospect {prospect.prospect_id}: {e}")

        await db.flush()
        return results

    async def _send_pending_interviews(
        self, db: AsyncSession, tenant_id: uuid.UUID
    ) -> dict[str, int]:
        """Send scheduled interview emails."""
        # Interview scheduling not yet implemented - stub for now
        results = {"sent": 0}
        return results

    async def _find_best_role(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        desired_role: str,
    ) -> RecruitmentRole | None:
        """Find the best matching open role for a candidate."""
        stmt = select(RecruitmentRole).where(
            and_(
                RecruitmentRole.tenant_id == tenant_id,
                RecruitmentRole.status == "OPEN",
            )
        )
        roles = (await db.execute(stmt)).scalars().all()

        if not roles:
            return None

        # Exact match first
        for role in roles:
            if desired_role.lower() in role.title.lower():
                return role

        # Return first open role as fallback
        return roles[0]

    async def _send_gmail_email(
        self,
        to_email: str,
        subject: str,
        body: str,
    ) -> bool:
        """Send email via Gmail API. Returns True if sent successfully."""
        try:
            # Import here to avoid circular imports
            from erp.integrations.gmail_service import gmail_service

            return await gmail_service.send_email(
                to=to_email,
                subject=subject,
                body=body,
            )
        except ImportError:
            logger.warning("Gmail service not available, email not sent")
            return False
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    # ============================================================================
    # CRUD Methods for API Routes
    # ============================================================================

    async def create_role(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        title: str,
        description: str,
        requirements: str,
    ) -> RecruitmentRole:
        """Create a new recruitment role."""
        role = RecruitmentRole(
            tenant_id=tenant_id,
            title=title,
            description=description,
            requirements=requirements,
            status="OPEN",
        )
        db.add(role)
        await db.flush()
        return role

    async def list_roles(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        role_status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recruitment roles, optionally filtered by status."""
        stmt = select(RecruitmentRole).where(RecruitmentRole.tenant_id == tenant_id)
        if role_status:
            stmt = stmt.where(RecruitmentRole.status == role_status)
        stmt = stmt.order_by(desc(RecruitmentRole.created_at))
        roles = (await db.execute(stmt)).scalars().all()
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
        """Get a specific recruitment role."""
        stmt = select(RecruitmentRole).where(
            and_(
                RecruitmentRole.role_id == role_id,
                RecruitmentRole.tenant_id == tenant_id,
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def close_role(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> RecruitmentRole | None:
        """Close a recruitment role."""
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
        """Create a candidate application."""
        # Verify role exists
        role = await self.get_role(db, tenant_id, role_id)
        if not role:
            raise ValueError("Role not found")

        application = CandidateApplication(
            tenant_id=tenant_id,
            role_id=role_id,
            applicant_name=applicant_name or "Unknown",
            applicant_email=applicant_email,
            resume_filename=resume_filename,
            resume_content_type=resume_content_type,
            resume_text=resume_text,
            status="READY",
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
        """List candidate applications, optionally filtered by role."""
        stmt = select(CandidateApplication).where(CandidateApplication.tenant_id == tenant_id)
        if role_id:
            stmt = stmt.where(CandidateApplication.role_id == role_id)
        stmt = stmt.order_by(desc(CandidateApplication.created_at))
        return (await db.execute(stmt)).scalars().all()

    async def get_application(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> CandidateApplication | None:
        """Get a specific candidate application."""
        stmt = select(CandidateApplication).where(
            and_(
                CandidateApplication.application_id == application_id,
                CandidateApplication.tenant_id == tenant_id,
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def delete_application(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> bool:
        """Delete a candidate application."""
        application = await self.get_application(db, tenant_id, application_id)
        if application:
            await db.delete(application)
            await db.flush()
            return True
        return False

    async def list_email_inbox(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[Any]:
        """List inbound emails for recruitment review."""
        # This would query a Gmail sync table - stub for now
        # Return empty list since Gmail integration isn't fully set up
        return []

    async def get_inbound_email(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        message_id: str,
        lock: bool = False,
    ) -> Any | None:
        """Get a specific inbound email."""
        # Stub for Gmail integration
        return None

    async def get_email_review_by_message(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        message_id: str,
    ) -> RecruitmentEmailReview | None:
        """Get an email review by message ID."""
        stmt = select(RecruitmentEmailReview).where(
            and_(
                RecruitmentEmailReview.tenant_id == tenant_id,
                RecruitmentEmailReview.inbound_message_id == message_id,
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def create_email_review(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        message_id: str,
        applicant_name: str,
        applicant_email: str,
        desired_role: str,
        suggested_role_id: uuid.UUID | None,
        confidence: float,
        summary: str,
        evidence: list[dict[str, Any]],
        resume_text: str,
        is_application: bool,
    ) -> RecruitmentEmailReview:
        """Create an email review."""
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
            status="REVIEW_REQUIRED" if is_application else "DISMISSED",
        )
        db.add(review)
        await db.flush()
        return review

    async def list_email_reviews(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[RecruitmentEmailReview]:
        """List email reviews awaiting decision."""
        stmt = select(RecruitmentEmailReview).where(
            and_(
                RecruitmentEmailReview.tenant_id == tenant_id,
                RecruitmentEmailReview.status == "REVIEW_REQUIRED",
            )
        ).order_by(desc(RecruitmentEmailReview.created_at))
        return (await db.execute(stmt)).scalars().all()

    async def get_email_review(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        review_id: uuid.UUID,
        lock: bool = False,
    ) -> RecruitmentEmailReview | None:
        """Get a specific email review."""
        stmt = select(RecruitmentEmailReview).where(
            and_(
                RecruitmentEmailReview.review_id == review_id,
                RecruitmentEmailReview.tenant_id == tenant_id,
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def stage_email_review_in_talent_pool(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        review: RecruitmentEmailReview,
    ) -> CandidateTalentPoolProspect:
        """Stage an email review into the talent pool."""
        prospect = CandidateTalentPoolProspect(
            tenant_id=tenant_id,
            source_review_id=review.review_id,
            status="PENDING_REVIEW",
            applicant_name=review.applicant_name,
            applicant_email=review.applicant_email,
            desired_role=review.desired_role,
            profile_text=review.resume_text,
        )
        db.add(prospect)
        review.status = "ADDED_TO_POOL"
        await db.flush()
        return prospect

    async def add_review_to_talent_pool(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        review_id: uuid.UUID,
    ) -> CandidateTalentPoolProspect:
        """Add a reviewed email to the talent pool."""
        review = await self.get_email_review(db, tenant_id, review_id)
        if not review:
            raise ValueError("Email review not found")
        if review.status != "REVIEW_REQUIRED":
            raise ValueError("Email review is no longer pending")
        return await self.stage_email_review_in_talent_pool(db, tenant_id, review)

    async def dismiss_email_review(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        review_id: uuid.UUID,
    ) -> RecruitmentEmailReview | None:
        """Dismiss an email review."""
        review = await self.get_email_review(db, tenant_id, review_id)
        if review:
            review.status = "DISMISSED"
            await db.flush()
        return review

    async def list_talent_pool(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[CandidateTalentPoolProspect]:
        """List talent pool prospects."""
        stmt = select(CandidateTalentPoolProspect).where(
            CandidateTalentPoolProspect.tenant_id == tenant_id
        ).order_by(desc(CandidateTalentPoolProspect.created_at))
        return (await db.execute(stmt)).scalars().all()

    async def save_talent_pool_match(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        prospect: CandidateTalentPoolProspect,
        role_id: uuid.UUID,
        match_score: int,
        match_summary: str,
        match_evidence: list[dict[str, Any]],
    ) -> CandidateTalentPoolProspect:
        """Save a talent pool match result."""
        prospect.matched_role_id = role_id
        prospect.match_score = match_score
        prospect.match_summary = match_summary
        prospect.match_evidence = match_evidence
        prospect.matched_at = datetime.now(timezone.utc)
        await db.flush()
        return prospect

    async def transfer_talent_pool_prospect(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        prospect_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> CandidateApplication:
        """Transfer a talent pool prospect to a candidate application."""
        prospect_stmt = select(CandidateTalentPoolProspect).where(
            and_(
                CandidateTalentPoolProspect.prospect_id == prospect_id,
                CandidateTalentPoolProspect.tenant_id == tenant_id,
            )
        )
        prospect = (await db.execute(prospect_stmt)).scalar_one_or_none()
        if not prospect:
            raise ValueError("Prospect not found")

        # Verify role exists
        role = await self.get_role(db, tenant_id, role_id)
        if not role:
            raise ValueError("Role not found")

        # Create application from prospect
        application = CandidateApplication(
            tenant_id=tenant_id,
            role_id=role_id,
            applicant_name=prospect.applicant_name,
            applicant_email=prospect.applicant_email,
            resume_filename="talent_pool.txt",
            resume_content_type="text/plain",
            resume_text=prospect.profile_text,
            status="READY",
            source_review_id=prospect.source_review_id,
        )
        db.add(application)

        # Update prospect status
        prospect.status = "TRANSFERRED"
        await db.flush()
        return application

    async def dismiss_talent_pool_prospect(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        prospect_id: uuid.UUID,
    ) -> CandidateTalentPoolProspect | None:
        """Dismiss a talent pool prospect."""
        prospect_stmt = select(CandidateTalentPoolProspect).where(
            and_(
                CandidateTalentPoolProspect.prospect_id == prospect_id,
                CandidateTalentPoolProspect.tenant_id == tenant_id,
            )
        )
        prospect = (await db.execute(prospect_stmt)).scalar_one_or_none()
        if prospect:
            prospect.status = "DISMISSED"
            await db.flush()
        return prospect

    async def send_interview_invitation(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        interview_details: str,
    ) -> CandidateApplication:
        """Send an interview invitation email to a candidate."""
        application = await self.get_application(db, tenant_id, application_id)
        if not application:
            raise ValueError("Application not found")

        if not application.applicant_email:
            raise ValueError("Candidate has no email address")

        # Get role for email content
        role = await self.get_role(db, tenant_id, application.role_id)
        if not role:
            raise ValueError("Role not found")

        # Generate interview email draft
        from erp.ai.hr_screening import create_interview_draft
        draft = await create_interview_draft(
            candidate_name=application.applicant_name,
            role_title=role.title,
            interview_details=interview_details,
        )

        # Send email
        sent = await self._send_gmail_email(
            to_email=application.applicant_email,
            subject=draft.subject,
            body=draft.body,
        )

        if sent:
            application.interview_email_subject = draft.subject
            application.interview_email_body = draft.body
            application.interview_email_sent_at = datetime.now(timezone.utc)
            await db.flush()

        return application

    async def scan_and_auto_transfer_prospects(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> dict[str, int]:
        """Scan talent pool and auto-transfer high-score prospects to a role."""
        role = await self.get_role(db, tenant_id, role_id)
        if not role:
            raise ValueError("Role not found")

        # Get pooled prospects
        prospects_stmt = select(CandidateTalentPoolProspect).where(
            and_(
                CandidateTalentPoolProspect.tenant_id == tenant_id,
                CandidateTalentPoolProspect.status == "POOLED",
            )
        )
        prospects = (await db.execute(prospects_stmt)).scalars().all()

        results = {"scanned": len(prospects), "transferred": 0}

        for prospect in prospects:
            try:
                # Match prospect against role
                match_result = await match_talent_pool_candidate(
                    role_title=role.title,
                    role_description=role.description,
                    role_requirements=role.requirements,
                    profile_text=prospect.profile_text or "",
                )

                # Auto-transfer if score >= 70
                if match_result.score >= 70:
                    await self.transfer_talent_pool_prospect(
                        db, tenant_id, prospect.prospect_id, role_id
                    )
                    results["transferred"] += 1
                else:
                    # Save match result for manual review
                    await self.save_talent_pool_match(
                        db,
                        tenant_id,
                        prospect,
                        role_id,
                        match_result.score,
                        match_result.summary,
                        [e.model_dump() for e in match_result.evidence],
                    )

            except Exception as e:
                logger.error(f"Failed to scan prospect {prospect.prospect_id}: {e}")

        return results


# Singleton instance
hr_recruitment_service = HRRecruitmentService()

