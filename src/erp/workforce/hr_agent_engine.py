"""Autonomous HR & Recruitment Agent Engine.

Continuously polls connected Gmail accounts for job applications & project status updates,
autonomously classifies them, ingests applications, dispatches AI acknowledgments,
manages the talent pool, monitors project pacing, and sends reminder emails with 24h guardrails.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from email.utils import parseaddr
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.ai.hr_screening import (
    classify_hr_and_project_email,
    evaluate_candidate,
    generate_acknowledgment_email,
    generate_project_pacing_reminder,
)
from erp.db.models.events import InboundEmailRecord
from erp.db.models.hr import Employee
from erp.db.models.projects import Project, ProjectTask, ProjectUpdate
from erp.db.models.recruitment import (
    CandidateApplication,
    CandidateTalentPoolProspect,
    HREmailPollingState,
    RecruitmentEmailReview,
    RecruitmentRole,
)
from erp.db.models.tenant import TenantOAuthConnection
from erp.db.session import async_session_factory
from erp.events.gmail_integration import gmail_service

logger = logging.getLogger(__name__)

HR_POLLING_INTERVAL_SECONDS = 60
PACING_CHECK_INTERVAL = 3  # Run project pacing check every 3 cycles


class HRAgentEngineState:
    """In-memory telemetry and status for the autonomous HR agent."""

    def __init__(self):
        self.is_running = False
        self.cycle_count = 0
        self.last_cycle_at: datetime | None = None
        self.last_error: str | None = None
        self.total_emails_processed = 0
        self.total_applications_ingested = 0
        self.total_prospects_pooled = 0
        self.total_pacing_reminders_sent = 0
        self.total_acks_sent = 0
        self.total_project_updates_recorded = 0


engine_state = HRAgentEngineState()


def _extract_name_and_email(sender: str) -> tuple[str, str]:
    """Cleanly extracts display name and email address from RFC 822 sender."""
    name, email = parseaddr(sender)
    name = name.strip().strip('"')
    email = email.strip().lower()
    if not name and email:
        name = email.split("@")[0].replace(".", " ").title()
    return name or "Applicant", email


async def get_tenants_with_gmail(session: AsyncSession) -> list[uuid.UUID]:
    """Returns list of tenant IDs that have an active connected Gmail OAuth integration."""
    stmt = select(TenantOAuthConnection.tenant_id).where(
        TenantOAuthConnection.provider == "google_gmail",
        TenantOAuthConnection.is_connected.is_(True),
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def _get_or_create_polling_state(
    session: AsyncSession, tenant_id: uuid.UUID
) -> HREmailPollingState:
    """Retrieves or provisions message deduplication state for a tenant."""
    stmt = (
        select(HREmailPollingState)
        .where(HREmailPollingState.tenant_id == tenant_id)
        .with_for_update()
    )
    state = (await session.execute(stmt)).scalar_one_or_none()
    if state is None:
        state = HREmailPollingState(
            tenant_id=tenant_id,
            last_processed_message_ids=[],
            last_checked_at=datetime.now(UTC),
        )
        session.add(state)
        await session.flush()
    return state


async def poll_tenant_hr_mailbox(
    tenant_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, int]:
    """Scans mailbox for applications and updates, classifies them, and takes autonomous actions."""
    metrics = {
        "new_messages": 0,
        "applications_created": 0,
        "prospects_pooled": 0,
        "project_updates": 0,
        "acks_sent": 0,
    }

    # 1. Ensure tenant has valid Gmail token
    conn = await gmail_service.ensure_valid_token(str(tenant_id), session)
    if not conn.is_connected or not conn.access_token:
        return metrics

    # 2. Fetch active roles and active projects for this tenant
    roles_stmt = select(RecruitmentRole).where(
        RecruitmentRole.tenant_id == tenant_id,
        RecruitmentRole.status == "OPEN",
    )
    roles = list((await session.execute(roles_stmt)).scalars().all())
    roles_payload = [
        {"role_id": str(r.role_id), "title": r.title, "description": r.description, "requirements": r.requirements}
        for r in roles
    ]

    proj_stmt = select(Project).where(
        Project.tenant_id == tenant_id,
        Project.status == "IN_PROGRESS",
    )
    projects = list((await session.execute(proj_stmt)).scalars().all())
    projects_payload = [
        {"project_id": str(p.project_id), "project_name": p.project_name, "percent_complete": float(p.percent_complete)}
        for p in projects
    ]

    # Sync first because the Gmail service commits while it persists inbound records.
    await gmail_service.sync_inbox(str(tenant_id), session)

    # Serialize polling across API workers after Gmail sync's internal commit.
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(str(tenant_id), 0)))
    )
    polling_state = await _get_or_create_polling_state(session, tenant_id)
    processed_ids = list(polling_state.last_processed_message_ids or [])
    processed_id_set = set(processed_ids)

    pending_stmt = (
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
        .order_by(InboundEmailRecord.received_at.asc())
        .limit(50)
    )
    inbound_messages = list((await session.execute(pending_stmt)).scalars().all())

    user_email = (conn.connected_email or "").strip().lower()

    for email_msg in inbound_messages:
        msg_id = email_msg.message_id
        if msg_id in processed_id_set:
            continue

        metrics["new_messages"] += 1
        sender_name, sender_email = _extract_name_and_email(email_msg.sender)

        # Skip self-sent emails to prevent echo loops
        if user_email and sender_email == user_email:
            processed_ids.append(msg_id)
            processed_id_set.add(msg_id)
            continue

        # The Gmail integration exposes attachment names only; email text remains the source.
        resume_text = email_msg.body_text or ""
        attachment_names = [att.filename for att in email_msg.attachments]
        resume_filename = attachment_names[0] if attachment_names else "email-application.txt"

        # Classify email using multi-intent LLM classifier.
        classification = await classify_hr_and_project_email(
            subject=email_msg.subject,
            sender=email_msg.sender,
            body_text=email_msg.body_text,
            resume_text=resume_text,
            roles=roles_payload,
            projects=projects_payload,
        )

        email_type = classification.email_type
        matched_role = next(
            (
                role
                for role in roles
                if str(role.role_id) == classification.matched_role_id
            ),
            None,
        )
        matched_project = next(
            (
                project
                for project in projects
                if str(project.project_id) == classification.matched_project_id
            ),
            None,
        )
        review_status = {
            "job_application": "APPLICATION_CREATED" if matched_role else "ADDED_TO_POOL",
            "project_update": "PROJECT_UPDATE_RECORDED" if matched_project else "NOT_APPLICATION",
            "other": "NOT_APPLICATION",
        }[email_type]
        review = RecruitmentEmailReview(
            tenant_id=tenant_id,
            inbound_message_id=msg_id,
            applicant_name=classification.applicant_name or sender_name,
            applicant_email=sender_email or None,
            desired_role=classification.desired_role,
            suggested_role_id=matched_role.role_id if matched_role else None,
            confidence=classification.confidence,
            summary=classification.reasoning or classification.notes or "Classified by the HR Agent.",
            evidence=[],
            resume_text=f"Subject: {email_msg.subject}\n\n{resume_text}",
            status=review_status,
        )
        session.add(review)
        await session.flush()

        # --- A. JOB APPLICATION BRANCH ---
        if email_type == "job_application":
            applicant_name = classification.applicant_name or sender_name

            if matched_role is not None:
                # 1. Create candidate application record
                app = CandidateApplication(
                    tenant_id=tenant_id,
                    role_id=matched_role.role_id,
                    applicant_name=applicant_name,
                    applicant_email=sender_email,
                    resume_filename=resume_filename,
                    resume_content_type="message/rfc822",
                    resume_text=resume_text,
                    status="READY",
                    source_review_id=review.review_id,
                )
                session.add(app)
                await session.flush()
                metrics["applications_created"] += 1
                engine_state.total_applications_ingested += 1

                # 2. Autonomous candidate screening & evaluation
                try:
                    eval_result = await evaluate_candidate(
                        role_title=matched_role.title,
                        role_description=matched_role.description,
                        role_requirements=matched_role.requirements,
                        resume_text=resume_text,
                    )
                    app.screening_score = Decimal(str(eval_result.score))
                    app.screening_summary = eval_result.summary
                    app.matched_requirements = eval_result.matched_requirements
                    app.evidence = [e.model_dump(mode="json") for e in eval_result.evidence]
                    app.status = "EVALUATED"
                    app.evaluation_completed_at = datetime.now(UTC)
                    await session.flush()
                except Exception as eval_err:
                    logger.warning("[HR Agent] Automated candidate evaluation failed: %s", eval_err)

                # 3. Autonomous personalized acknowledgment email dispatch
                if sender_email:
                    try:
                        ack_draft = await generate_acknowledgment_email(
                            applicant_name=applicant_name,
                            role_title=matched_role.title,
                            matched=True,
                        )
                        await gmail_service.send_email_via_gmail(
                            tenant_id=str(tenant_id),
                            recipient=sender_email,
                            subject=ack_draft.subject,
                            body=ack_draft.body,
                            session=session,
                        )
                        app.ack_email_sent = True
                        app.ack_email_sent_at = datetime.now(UTC)
                        metrics["acks_sent"] += 1
                        engine_state.total_acks_sent += 1
                        logger.info(
                            "[HR Agent] Auto-ack dispatched to %s for role '%s'",
                            sender_email,
                            matched_role.title,
                        )
                    except Exception:
                        logger.exception(
                            "[HR Agent] Failed to send candidate auto-ack to %s", sender_email
                        )

            else:
                # Unmatched job application: store in Talent Pool ("Future Prospects")
                prospect = CandidateTalentPoolProspect(
                    tenant_id=tenant_id,
                    source_review_id=review.review_id,
                    applicant_name=applicant_name,
                    applicant_email=sender_email,
                    desired_role=classification.desired_role or email_msg.subject,
                    profile_text=resume_text,
                    status="POOLED",
                )
                session.add(prospect)
                await session.flush()
                metrics["prospects_pooled"] += 1
                engine_state.total_prospects_pooled += 1

                # Dispatch future prospects acknowledgment email
                if sender_email:
                    try:
                        ack_draft = await generate_acknowledgment_email(
                            applicant_name=applicant_name,
                            role_title=classification.desired_role,
                            matched=False,
                        )
                        await gmail_service.send_email_via_gmail(
                            tenant_id=str(tenant_id),
                            recipient=sender_email,
                            subject=ack_draft.subject,
                            body=ack_draft.body,
                            session=session,
                        )
                        prospect.notification_sent = True
                        prospect.notification_sent_at = datetime.now(UTC)
                        metrics["acks_sent"] += 1
                        engine_state.total_acks_sent += 1
                        logger.info(
                            "[HR Agent] Future-prospects auto-ack dispatched to %s", sender_email
                        )
                    except Exception:
                        logger.exception(
                            "[HR Agent] Failed to send future-prospects auto-ack to %s",
                            sender_email,
                        )

        # --- B. PROJECT STATUS UPDATE BRANCH ---
        elif email_type == "project_update":
            if matched_project is not None:
                new_pct = classification.progress_pct
                if new_pct is not None:
                    matched_project.percent_complete = Decimal(str(new_pct))
                    if new_pct >= 100:
                        matched_project.status = "COMPLETED"

                update_note = classification.notes or email_msg.body_text[:500]
                matched_project.last_update_summary = update_note

                # Create historical project update record
                proj_update = ProjectUpdate(
                    tenant_id=tenant_id,
                    project_id=matched_project.project_id,
                    sender_email=sender_email,
                    progress_pct=new_pct,
                    notes=update_note,
                    blockers=classification.blockers,
                )
                session.add(proj_update)
                await session.flush()
                metrics["project_updates"] += 1
                engine_state.total_project_updates_recorded += 1

                # Dispatch automated confirmation receipt email
                pct_str = f" to {new_pct}%" if new_pct is not None else ""
                ack_body = (
                    f"Hello {sender_name},\n\n"
                    f"Thank you for your update regarding '{matched_project.project_name}'. Your progress update{pct_str} "
                    f"has been successfully logged into the ERP system.\n\n"
                    f"Summary recorded:\n{update_note}\n\n"
                    f"Best regards,\n"
                    f"AI Operations & Project Assistant"
                )
                if sender_email:
                    try:
                        await gmail_service.send_email_via_gmail(
                            tenant_id=str(tenant_id),
                            recipient=sender_email,
                            subject=f"Re: {email_msg.subject or 'Project Progress Update Recorded'}",
                            body=ack_body,
                            session=session,
                        )
                        logger.info(
                            "[HR Agent] Project update receipt sent to %s for '%s'",
                            sender_email,
                            matched_project.project_name,
                        )
                    except Exception:
                        logger.exception(
                            "[HR Agent] Failed to send project update receipt to %s", sender_email
                        )

        processed_ids.append(msg_id)
        processed_id_set.add(msg_id)

    engine_state.total_emails_processed += metrics["new_messages"]
    polling_state.last_processed_message_ids = processed_ids[-1000:]
    polling_state.last_checked_at = datetime.now(UTC)
    await session.commit()

    return metrics


async def check_tenant_project_pacing(
    tenant_id: uuid.UUID,
    session: AsyncSession,
) -> int:
    """Calculates expected project completion vs actual progress and sends reminders to leads."""
    reminders_sent = 0

    stmt = select(Project).where(
        Project.tenant_id == tenant_id,
        Project.status == "IN_PROGRESS",
    )
    projects = list((await session.execute(stmt)).scalars().all())

    today = date.today()
    now_dt = datetime.now(UTC)

    for project in projects:
        if not project.end_date:
            continue

        start_d = project.start_date or today
        end_d = project.end_date

        total_days = max(1, (end_d - start_d).days)
        elapsed_days = max(0, (today - start_d).days)
        expected_progress = min(100, max(0, int((elapsed_days / total_days) * 100)))
        current_progress = int(project.percent_complete)

        pacing_delta = current_progress - expected_progress

        # Alert if project is behind by > 15%
        if pacing_delta < -15:
            # 24-hour rate limit guardrail per project
            if project.last_reminder_sent_at:
                hours_since = (now_dt - project.last_reminder_sent_at).total_seconds() / 3600.0
                if hours_since < 24.0:
                    continue

            # Identify team lead or assigned employee
            task_stmt = select(ProjectTask).where(
                ProjectTask.project_id == project.project_id,
                ProjectTask.assigned_to_id.is_not(None),
            )
            tasks = list((await session.execute(task_stmt)).scalars().all())

            lead_email = None
            lead_name = "Team Lead"

            for t in tasks:
                if t.assigned_to_id:
                    emp = (await session.execute(
                        select(Employee).where(Employee.employee_id == t.assigned_to_id)
                    )).scalar_one_or_none()
                    if emp and emp.email:
                        lead_email = emp.email
                        lead_name = f"{emp.first_name} {emp.last_name}"
                        break

            if not lead_email:
                logger.warning(
                    "[HR Agent] No assigned employee with an email for behind-schedule project %s",
                    project.project_id,
                )
                continue

            # Draft reminder email
            reminder = await generate_project_pacing_reminder(
                project_name=project.project_name,
                current_progress=current_progress,
                expected_progress=expected_progress,
                deadline=str(project.end_date),
                lead_name=lead_name,
                last_update=project.last_update_summary,
            )

            await gmail_service.send_email_via_gmail(
                tenant_id=str(tenant_id),
                recipient=lead_email,
                subject=reminder.subject,
                body=reminder.body,
                session=session,
            )
            project.last_reminder_sent_at = now_dt
            await session.flush()
            reminders_sent += 1
            engine_state.total_pacing_reminders_sent += 1
            logger.info(
                "[HR Agent] Project pacing alert sent to %s for '%s' (Gap: %d%%)",
                lead_email,
                project.project_name,
                pacing_delta,
            )

    return reminders_sent


async def scan_tenant_talent_pool(
    tenant_id: uuid.UUID,
    session: AsyncSession,
    *,
    force: bool = False,
) -> int:
    """Auto-transfer strong pool matches for each open role at most every three minutes."""
    polling_state = await _get_or_create_polling_state(session, tenant_id)
    now = datetime.now(UTC)
    if (
        not force
        and polling_state.last_talent_pool_scan_at
        and (now - polling_state.last_talent_pool_scan_at).total_seconds()
        < HR_POLLING_INTERVAL_SECONDS * PACING_CHECK_INTERVAL
    ):
        return 0

    from erp.workflows.hr.recruitment_service import recruitment_service

    roles_stmt = select(RecruitmentRole).where(
        RecruitmentRole.tenant_id == tenant_id,
        RecruitmentRole.status == "OPEN",
    )
    roles = list((await session.execute(roles_stmt)).scalars().all())
    transferred_count = 0
    for role in roles:
        transferred = await recruitment_service.scan_and_auto_transfer_prospects(
            session, tenant_id, role.role_id, score_threshold=50
        )
        transferred_count += len(transferred)

    polling_state.last_talent_pool_scan_at = now
    await session.flush()
    return transferred_count


async def run_autonomous_cycle(tenant_id: uuid.UUID | str) -> dict[str, Any]:
    """Executes a single immediate autonomous intake and pacing pass for a tenant."""
    tenant_uuid = uuid.UUID(str(tenant_id))
    async with async_session_factory() as session:
        poll_metrics = await poll_tenant_hr_mailbox(tenant_uuid, session)
        transfers = await scan_tenant_talent_pool(tenant_uuid, session, force=True)
        reminders = await check_tenant_project_pacing(tenant_uuid, session)
        await session.commit()
        return {
            **poll_metrics,
            "talent_pool_transfers": transfers,
            "pacing_reminders_sent": reminders,
        }


async def start_hr_autonomous_engine(stop_event: asyncio.Event) -> None:
    """Infinite background loop running every 60s for all tenants with connected Gmail."""
    logger.info("[HR Agent] Autonomous engine initialized. Polling every %ds.", HR_POLLING_INTERVAL_SECONDS)
    engine_state.is_running = True

    await asyncio.sleep(5)  # Initial grace window after boot

    while not stop_event.is_set():
        try:
            engine_state.cycle_count += 1
            engine_state.last_cycle_at = datetime.now(UTC)

            async with async_session_factory() as session:
                tenants = await get_tenants_with_gmail(session)

            for tenant_id in tenants:
                if stop_event.is_set():
                    break
                try:
                    async with async_session_factory() as session:
                        await poll_tenant_hr_mailbox(tenant_id, session)
                        await scan_tenant_talent_pool(tenant_id, session)
                        if engine_state.cycle_count % PACING_CHECK_INTERVAL == 0:
                            await check_tenant_project_pacing(tenant_id, session)
                        await session.commit()
                    engine_state.last_error = None
                except Exception:
                    engine_state.last_error = f"HR cycle failed for tenant {tenant_id}"
                    logger.exception("[HR Agent] Tenant cycle failed for %s", tenant_id)
        except Exception as exc:
            engine_state.last_error = str(exc)
            logger.error("[HR Agent] Unexpected error in polling cycle: %s\n%s", exc, traceback.format_exc())

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HR_POLLING_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass

    engine_state.is_running = False
    logger.info("[HR Agent] Autonomous engine stopped.")


def get_engine_status(tenant_id: uuid.UUID | str | None = None) -> dict[str, Any]:
    """Returns engine telemetry and running status."""
    return {
        "running": engine_state.is_running,
        "cycle_count": engine_state.cycle_count,
        "last_cycle_at": engine_state.last_cycle_at.isoformat() if engine_state.last_cycle_at else None,
        "total_emails_processed": engine_state.total_emails_processed,
        "total_applications_created": engine_state.total_applications_ingested,
        "total_prospects_created": engine_state.total_prospects_pooled,
        "total_interview_emails_sent": engine_state.total_acks_sent,
        "total_project_updates_recorded": engine_state.total_project_updates_recorded,
        "total_pacing_reminders_sent": engine_state.total_pacing_reminders_sent,
        "last_error": engine_state.last_error,
        "errors": [engine_state.last_error] if engine_state.last_error else [],
    }
