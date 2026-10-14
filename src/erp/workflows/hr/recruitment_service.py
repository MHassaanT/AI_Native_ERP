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
    TalentPoolProspect,
    EmailIntakeReview,
    InterviewSchedule,
)
from erp.db.models.hr import Employee
from erp.ai.hr_screening import hr_screening, ScreeningResult

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
        stmt = select(EmailIntakeReview).where(
            and_(
                EmailIntakeReview.tenant_id == tenant_id,
                EmailIntakeReview.review_status == "PENDING",
            )
        )
        reviews = (await db.execute(stmt)).scalars().all()

        for review in reviews:
            try:
                # Auto-classify with AI
                classification = await hr_screening.classify_email(
                    review.email_subject or "",
                    review.email_body or "",
                )

                if classification["is_application"]:
                    # Find best matching open role
                    role = await self._find_best_role(
                        db, tenant_id, classification.get("desired_role", "")
                    )

                    if role and classification["confidence"] >= 0.7:
                        # Auto-create application
                        application = CandidateApplication(
                            tenant_id=tenant_id,
                            role_id=role.role_id,
                            source="GMAIL",
                            applicant_name=classification.get("applicant_name"),
                            applicant_email=review.sender_email,
                            resume_filename=review.attachment_names[0] if review.attachment_names else "email_body.txt",
                            resume_text=review.email_body,
                            status="READY",
                        )
                        db.add(application)
                        review.review_status = "CONVERTED_TO_APPLICATION"
                        review.suggested_role_id = role.role_id
                        results["applications"] += 1
                    else:
                        # Add to talent pool for later
                        prospect = TalentPoolProspect(
                            tenant_id=tenant_id,
                            source_review_id=review.review_id,
                            status="PENDING_REVIEW",
                            applicant_name=classification.get("applicant_name"),
                            applicant_email=review.sender_email,
                            desired_role=classification.get("desired_role"),
                            profile_text=review.email_body,
                        )
                        db.add(prospect)
                        review.review_status = "STAGED_TO_POOL"
                        results["prospects"] += 1
                else:
                    review.review_status = "DISMISSED"

                results["processed"] += 1

            except Exception as e:
                logger.error(f"Failed to process review {review.review_id}: {e}")
                review.review_status = "ERROR"

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
                screening: ScreeningResult = await hr_screening.screen_candidate(
                    resume_text=app.resume_text or "",
                    job_requirements=role.requirements,
                    job_title=role.title,
                )

                app.screening_score = screening.score
                app.screening_summary = screening.summary
                app.matched_requirements = screening.matched_requirements
                app.evidence = [e.model_dump() for e in screening.evidence]
                app.status = "EVALUATED"

                # Auto-schedule interview if score >= 75
                if screening.score >= 75 and app.applicant_email:
                    await self._schedule_interview(db, tenant_id, app, role)

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
        prospects_stmt = select(TalentPoolProspect).where(
            and_(
                TalentPoolProspect.tenant_id == tenant_id,
                TalentPoolProspect.status == "POOLED",
                TalentPoolProspect.match_score.is_(None),
            )
        )
        prospects = (await db.execute(prospects_stmt)).scalars().all()

        for prospect in prospects:
            try:
                best_match = None
                best_score = 0

                for role in roles:
                    match_result = await hr_screening.match_talent_pool_prospect(
                        prospect_profile=prospect.profile_text or "",
                        role_requirements=role.requirements,
                        role_title=role.title,
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
        results = {"sent": 0}

        stmt = select(InterviewSchedule).where(
            and_(
                InterviewSchedule.tenant_id == tenant_id,
                InterviewSchedule.status == "SCHEDULED",
                InterviewSchedule.notification_sent == False,
            )
        )
        interviews = (await db.execute(stmt)).scalars().all()

        for interview in interviews:
            try:
                # Get application and role details
                app_stmt = select(CandidateApplication).where(
                    CandidateApplication.application_id == interview.application_id
                )
                app = (await db.execute(app_stmt)).scalar_one_or_none()

                if not app or not app.applicant_email:
                    continue

                # Generate interview email
                email_result = await hr_screening.draft_interview_email(
                    applicant_name=app.applicant_name or "Candidate",
                    job_title=interview.role_title or "Position",
                    interview_details=interview.interview_details or "",
                )

                # Send via Gmail service (if configured)
                sent = await self._send_gmail_email(
                    to_email=app.applicant_email,
                    subject=email_result.subject,
                    body=email_result.body,
                )

                if sent:
                    interview.notification_sent = True
                    interview.notification_sent_at = datetime.now(timezone.utc)
                    app.interview_email_sent_at = datetime.now(timezone.utc)
                    app.ack_email_sent = True
                    results["sent"] += 1

            except Exception as e:
                logger.error(f"Failed to send interview {interview.interview_id}: {e}")

        await db.flush()
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

    async def _schedule_interview(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        application: CandidateApplication,
        role: RecruitmentRole,
    ) -> None:
        """Schedule an interview for a high-scoring candidate."""
        interview = InterviewSchedule(
            tenant_id=tenant_id,
            application_id=application.application_id,
            role_id=role.role_id,
            role_title=role.title,
            interview_details=(
                f"Congratulations! Based on your resume, we'd like to invite you "
                f"for an interview for the {role.title} position. "
                f"Please reply to this email with your availability."
            ),
            scheduled_at=datetime.now(timezone.utc),
            status="SCHEDULED",
            notification_sent=False,
        )
        db.add(interview)

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


# Singleton instance
hr_recruitment_service = HRRecruitmentService()

