"""Onboarding Checklist and Real-Time Verification API Endpoints."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from erp.api.deps import CurrentUserDep, DbSessionDep
from erp.auth.industry_modules import ALL_MODULES
from erp.auth.onboarding_steps import validate_step_completion
from erp.db.models.onboarding import OnboardingProgress, OnboardingStep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["In-App Module Onboarding"])


class StepItem(BaseModel):
    step_id: uuid.UUID
    step_key: str
    step_title: str
    step_description: str | None = None
    action_type: str
    reference_entity: str | None = None
    target_route: str | None = None
    is_complete: bool
    completed_at: datetime | None = None
    sort_order: int


class ModuleProgressItem(BaseModel):
    module_slug: str
    module_name: str
    module_description: str
    icon: str
    is_complete: bool
    total_steps: int
    completed_steps: int
    steps: list[StepItem]


class OnboardingOverviewResponse(BaseModel):
    overall_progress_pct: float
    total_steps: int
    completed_steps: int
    is_all_complete: bool
    modules: list[ModuleProgressItem]


class StepActionResponse(BaseModel):
    step_id: uuid.UUID
    step_key: str
    is_complete: bool
    message: str


@router.get("/progress", response_model=OnboardingOverviewResponse)
async def get_onboarding_progress(
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> OnboardingOverviewResponse:
    """Returns all onboarding modules and steps for the tenant, performing live

    verification against actual database tables to auto-complete finished steps.
    """
    tenant_id = current_user.tenant_id

    # 1. Fetch modules and steps
    modules_stmt = (
        select(OnboardingProgress)
        .where(OnboardingProgress.tenant_id == tenant_id)
        .order_by(OnboardingProgress.created_at.asc())
    )
    module_rows = (await db.execute(modules_stmt)).scalars().all()

    steps_stmt = (
        select(OnboardingStep)
        .where(OnboardingStep.tenant_id == tenant_id)
        .order_by(OnboardingStep.sort_order.asc(), OnboardingStep.created_at.asc())
    )
    step_rows = (await db.execute(steps_stmt)).scalars().all()

    # Index steps by module
    steps_by_module: dict[str, list[OnboardingStep]] = {}
    for st in step_rows:
        steps_by_module.setdefault(st.module_slug, []).append(st)

    # 2. Live verification of incomplete steps
    now_utc = datetime.now(UTC)
    state_mutated = False

    for st in step_rows:
        if not st.is_complete:
            is_valid = await validate_step_completion(db, tenant_id, st.step_key)
            if is_valid:
                st.is_complete = True
                st.completed_at = now_utc
                state_mutated = True

    # Check module completion
    for m in module_rows:
        m_steps = steps_by_module.get(m.module_slug, [])
        all_done = len(m_steps) > 0 and all(s.is_complete for s in m_steps)
        if all_done and not m.is_complete:
            m.is_complete = True
            m.completed_at = now_utc
            state_mutated = True

    if state_mutated:
        await db.commit()

    # 3. Assemble response
    module_catalog = {m["slug"]: m for m in ALL_MODULES}
    total_steps = len(step_rows)
    completed_steps = sum(1 for s in step_rows if s.is_complete)
    overall_pct = round((completed_steps / total_steps * 100), 1) if total_steps > 0 else 100.0

    modules_response: list[ModuleProgressItem] = []
    for m in module_rows:
        cat = module_catalog.get(
            m.module_slug,
            {"name": m.module_slug.title(), "description": "", "icon": "Layers"},
        )
        m_steps = steps_by_module.get(m.module_slug, [])
        m_comp = sum(1 for s in m_steps if s.is_complete)
        modules_response.append(
            ModuleProgressItem(
                module_slug=m.module_slug,
                module_name=cat["name"],
                module_description=cat.get("description", ""),
                icon=cat.get("icon", "Layers"),
                is_complete=m.is_complete,
                total_steps=len(m_steps),
                completed_steps=m_comp,
                steps=[
                    StepItem(
                        step_id=s.step_id,
                        step_key=s.step_key,
                        step_title=s.step_title,
                        step_description=s.step_description,
                        action_type=s.action_type,
                        reference_entity=s.reference_entity,
                        target_route=s.target_route,
                        is_complete=s.is_complete,
                        completed_at=s.completed_at,
                        sort_order=s.sort_order,
                    )
                    for s in m_steps
                ],
            )
        )

    return OnboardingOverviewResponse(
        overall_progress_pct=overall_pct,
        total_steps=total_steps,
        completed_steps=completed_steps,
        is_all_complete=total_steps > 0 and completed_steps == total_steps,
        modules=modules_response,
    )


@router.post("/steps/{step_id}/complete", response_model=StepActionResponse)
async def manually_complete_step(
    step_id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> StepActionResponse:
    """Manually marks an onboarding step complete (for view/settings review steps)."""
    step = (
        await db.execute(
            select(OnboardingStep).where(
                OnboardingStep.step_id == step_id,
                OnboardingStep.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()

    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found.")

    step.is_complete = True
    step.completed_at = datetime.now(UTC)

    # Check if parent module is now complete
    m_steps = (
        await db.execute(
            select(OnboardingStep).where(
                OnboardingStep.tenant_id == current_user.tenant_id,
                OnboardingStep.module_slug == step.module_slug,
            )
        )
    ).scalars().all()

    if all(s.is_complete for s in m_steps):
        mod = (
            await db.execute(
                select(OnboardingProgress).where(
                    OnboardingProgress.tenant_id == current_user.tenant_id,
                    OnboardingProgress.module_slug == step.module_slug,
                )
            )
        ).scalar_one_or_none()
        if mod:
            mod.is_complete = True
            mod.completed_at = datetime.now(UTC)

    await db.commit()

    return StepActionResponse(
        step_id=step.step_id,
        step_key=step.step_key,
        is_complete=True,
        message=f"Step '{step.step_title}' marked as completed.",
    )


@router.post("/steps/{step_id}/validate", response_model=StepActionResponse)
async def validate_step(
    step_id: uuid.UUID,
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> StepActionResponse:
    """Runs a live verification check against database records for a step."""
    step = (
        await db.execute(
            select(OnboardingStep).where(
                OnboardingStep.step_id == step_id,
                OnboardingStep.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()

    if not step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found.")

    is_valid = await validate_step_completion(db, current_user.tenant_id, step.step_key)
    if is_valid and not step.is_complete:
        step.is_complete = True
        step.completed_at = datetime.now(UTC)
        await db.commit()

    return StepActionResponse(
        step_id=step.step_id,
        step_key=step.step_key,
        is_complete=step.is_complete,
        message="Prerequisites verified in database."
        if is_valid
        else "Prerequisites not yet detected in database.",
    )


@router.post("/modules/{module_slug}/skip")
async def skip_module(
    module_slug: str,
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> dict:
    """Skips an entire module by marking all its checklist steps complete."""
    steps = (
        await db.execute(
            select(OnboardingStep).where(
                OnboardingStep.tenant_id == current_user.tenant_id,
                OnboardingStep.module_slug == module_slug,
            )
        )
    ).scalars().all()

    now_utc = datetime.now(UTC)
    for st in steps:
        st.is_complete = True
        st.completed_at = now_utc

    mod = (
        await db.execute(
            select(OnboardingProgress).where(
                OnboardingProgress.tenant_id == current_user.tenant_id,
                OnboardingProgress.module_slug == module_slug,
            )
        )
    ).scalar_one_or_none()
    if mod:
        mod.is_complete = True
        mod.completed_at = now_utc

    await db.commit()
    return {"message": f"Module '{module_slug}' skipped successfully.", "module_slug": module_slug}
