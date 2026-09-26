"""Setup Wizard API Endpoints for First-Time Organization Configuration."""

import logging
import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import CurrentUserDep, DbSessionDep
from erp.auth.chart_of_accounts_loader import get_available_charts_for_country
from erp.auth.fiscal_years import COUNTRY_LOCALIZATIONS, get_country_info
from erp.auth.industry_modules import ALL_MODULES, INDUSTRY_BLUEPRINTS
from erp.auth.provisioning import SetupConfig, provision_tenant_blueprint
from erp.auth.security import create_access_token
from erp.db.models.tenant import Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup", tags=["Setup Wizard"])


class SetupStatusResponse(BaseModel):
    tenant_id: uuid.UUID
    company_name: str
    is_complete: bool
    setup_completed_at: datetime | None = None
    country: str | None = None
    industry: str | None = None
    currency: str | None = None
    enabled_modules: list[str] = []


class CompleteSetupRequest(BaseModel):
    country: str = Field(..., min_length=2, max_length=64)
    industry: str = Field(..., min_length=2, max_length=64)
    currency: str = Field(..., min_length=3, max_length=3)
    timezone: str = Field(default="UTC", max_length=64)
    fiscal_year_start: date | None = None
    fiscal_year_end: date | None = None
    company_size: str = Field(default="11-50", max_length=32)
    chart_of_accounts: str = Field(default="Standard GAAP", max_length=128)
    enabled_modules: list[str] = Field(default_factory=list)
    generate_demo_data: bool = False


class CompleteSetupResponse(BaseModel):
    success: bool
    message: str
    access_token: str
    token_type: str = "bearer"
    provisioned_summary: dict


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status(
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> SetupStatusResponse:
    """Returns the setup wizard completion status for the authenticated user's organization."""
    tenant = (
        await db.execute(select(Tenant).where(Tenant.tenant_id == current_user.tenant_id))
    ).scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

    return SetupStatusResponse(
        tenant_id=tenant.tenant_id,
        company_name=tenant.company_name,
        is_complete=tenant.setup_completed_at is not None,
        setup_completed_at=tenant.setup_completed_at,
        country=tenant.country,
        industry=tenant.industry,
        currency=tenant.currency,
        enabled_modules=tenant.enabled_modules or [],
    )


@router.get("/countries")
async def list_supported_countries() -> list[dict]:
    """Returns all supported countries with pre-configured fiscal calendars, currencies, and timezones."""
    return list(COUNTRY_LOCALIZATIONS.values())


@router.get("/industries")
async def list_industries() -> dict:
    """Returns industry verticals, default module assignments, and the master module catalog."""
    industries_list = [
        {
            "name": k,
            "default_modules": v["default_modules"],
            "cost_centers_count": len(v["cost_centers"]),
            "warehouses_count": len(v["warehouses"]),
            "valuation_method": v["valuation_method"],
        }
        for k, v in INDUSTRY_BLUEPRINTS.items()
    ]
    return {
        "industries": industries_list,
        "all_modules": ALL_MODULES,
    }


@router.get("/charts")
async def list_charts_for_country(
    country: str = Query(..., description="Country name to fetch localized Chart of Accounts templates for"),
) -> list[str]:
    """Returns all verified Chart of Accounts templates applicable to the specified country."""
    return get_available_charts_for_country(country)


@router.post("/complete", response_model=CompleteSetupResponse)
async def complete_setup(
    req: CompleteSetupRequest,
    current_user: CurrentUserDep,
    db: DbSessionDep,
) -> CompleteSetupResponse:
    """Executes the complete setup wizard: provisions Chart of Accounts, warehouses,

    cost centers, fiscal calendar, settings, and seeds module onboarding steps.
    """
    tenant = (
        await db.execute(select(Tenant).where(Tenant.tenant_id == current_user.tenant_id))
    ).scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found.")

    # Guard: prevent duplicate re-initialization if already completed
    if tenant.setup_completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup wizard has already been completed for this organization.",
        )

    # 1. Update Tenant record
    now_utc = datetime.now(UTC)
    tenant.country = req.country
    tenant.industry = req.industry
    tenant.currency = req.currency.upper()
    tenant.timezone = req.timezone
    tenant.fiscal_year_start = req.fiscal_year_start
    tenant.fiscal_year_end = req.fiscal_year_end
    tenant.company_size = req.company_size
    tenant.enabled_modules = req.enabled_modules or [
        "accounting",
        "inventory",
        "production",
        "commercial",
        "accounts_payable",
    ]
    tenant.setup_completed_at = now_utc

    # 2. Execute Dynamic Blueprint Provisioning
    setup_config = SetupConfig(
        country=req.country,
        industry=req.industry,
        currency=req.currency.upper(),
        timezone=req.timezone,
        fiscal_year_start=req.fiscal_year_start,
        fiscal_year_end=req.fiscal_year_end,
        company_size=req.company_size,
        chart_of_accounts_template=req.chart_of_accounts,
        enabled_modules=tenant.enabled_modules,
        generate_demo_data=req.generate_demo_data,
    )

    summary = await provision_tenant_blueprint(
        session=db,
        tenant_id=tenant.tenant_id,
        company_name=tenant.company_name,
        config=setup_config,
    )

    await db.commit()
    logger.info("Setup wizard completed for tenant '%s' (%s).", tenant.company_name, tenant.tenant_id)

    # 3. Issue refreshed JWT with setup_complete: True claim
    token_data = {
        "sub": str(current_user.user_id),
        "tenant_id": str(tenant.tenant_id),
        "email": current_user.email,
        "role": current_user.role,
        "company_name": tenant.company_name,
        "tenant_slug": tenant.tenant_slug,
        "setup_complete": True,
    }
    new_token = create_access_token(token_data)

    return CompleteSetupResponse(
        success=True,
        message=f"Organization '{tenant.company_name}' successfully provisioned with {summary['accounts_count']} accounts and {summary['cost_centers_count']} cost centers.",
        access_token=new_token,
        token_type="bearer",
        provisioned_summary=summary,
    )
