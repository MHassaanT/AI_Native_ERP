"""End-to-End Tests for the Three-Stage Onboarding and Setup Flow."""

import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from erp.api.app import app
from erp.db.engine import async_engine
from erp.db.models.inventory import Item, Warehouse
from erp.db.models.ledger import Account, FiscalPeriod
from erp.db.models.onboarding import OnboardingProgress, OnboardingStep, TenantSettings
from erp.db.session import async_session_factory


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_setup_metadata_endpoints():
    """Verifies that countries, industries, and localized chart templates are served correctly."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Countries
        resp = await client.get("/api/v1/setup/countries")
        assert resp.status_code == 200, resp.text
        countries = resp.json()
        assert len(countries) >= 15
        country_names = [c["country_name"] for c in countries]
        assert "Pakistan" in country_names
        assert "India" in country_names
        assert "United States" in country_names
        assert "United Arab Emirates" in country_names

        # Industries
        resp = await client.get("/api/v1/setup/industries")
        assert resp.status_code == 200, resp.text
        ind_data = resp.json()
        assert "industries" in ind_data
        assert "all_modules" in ind_data
        assert len(ind_data["industries"]) >= 5
        assert len(ind_data["all_modules"]) == 8

        # Localized Chart of Accounts
        resp = await client.get("/api/v1/setup/charts?country=India")
        assert resp.status_code == 200
        charts_in = resp.json()
        assert len(charts_in) > 0

        resp = await client.get("/api/v1/setup/charts?country=Pakistan")
        assert resp.status_code == 200
        charts_pk = resp.json()
        assert len(charts_pk) > 0


@pytest.mark.asyncio
async def test_full_three_stage_onboarding_lifecycle():
    """Tests the full three-stage lifecycle:

    1. Sign-Up: registers tenant without hardcoded provisioning; setup_complete is False.
    2. Setup Wizard: provisions localized CoA, 12 fiscal periods, warehouses, settings, demo data.
    3. In-App Onboarding: live verification of steps against underlying PostgreSQL records.
    """
    slug = f"aerospace-pk-{uuid.uuid4().hex[:6]}"
    email = f"director@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # ---------------------------------------------------------
        # STAGE 1: Self-Registration
        # ---------------------------------------------------------
        reg_payload = {
            "company_name": "Apex Precision Aerospace",
            "tenant_slug": slug,
            "email": email,
            "password": "MasterSecurePassword2026!",
            "full_name": "Tariq Mansoor",
        }
        reg_resp = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_resp.status_code == 201, reg_resp.text
        reg_data = reg_resp.json()

        assert "access_token" in reg_data
        token = reg_data["access_token"]
        assert reg_data["user"]["setup_complete"] is False
        tenant_id = uuid.UUID(reg_data["user"]["tenant_id"])

        headers = {"Authorization": f"Bearer {token}"}

        # Check status before wizard
        status_resp = await client.get("/api/v1/setup/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["is_complete"] is False

        # ---------------------------------------------------------
        # STAGE 2: Setup Wizard Completion (Configures Underlyings)
        # ---------------------------------------------------------
        setup_payload = {
            "country": "Pakistan",
            "industry": "Manufacturing",
            "currency": "PKR",
            "timezone": "Asia/Karachi",
            "fiscal_year_start": "2026-07-01",
            "fiscal_year_end": "2027-06-30",
            "company_size": "51-200",
            "chart_of_accounts": "Standard GAAP",
            "enabled_modules": ["accounting", "inventory", "production", "commercial", "accounts_payable"],
            "generate_demo_data": True,
        }
        setup_resp = await client.post("/api/v1/setup/complete", json=setup_payload, headers=headers)
        assert setup_resp.status_code == 200, setup_resp.text
        setup_data = setup_resp.json()
        assert setup_data["success"] is True
        summary = setup_data["provisioned_summary"]
        assert summary["accounts_count"] >= 14
        assert summary["cost_centers_count"] >= 4
        assert summary["warehouses_count"] >= 3
        assert summary["fiscal_periods_count"] == 12
        assert summary["demo_data_seeded"] is True

        new_token = setup_data["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}

        # Verify status is now complete
        status_resp2 = await client.get("/api/v1/setup/status", headers=new_headers)
        assert status_resp2.status_code == 200
        assert status_resp2.json()["is_complete"] is True
        assert status_resp2.json()["country"] == "Pakistan"
        assert status_resp2.json()["currency"] == "PKR"

        # Verify underlying database records directly
        async with async_session_factory() as db:
            # 1. 12 Monthly Fiscal Periods
            periods = (
                await db.execute(
                    select(FiscalPeriod).where(FiscalPeriod.tenant_id == tenant_id).order_by(FiscalPeriod.fiscal_period)
                )
            ).scalars().all()
            assert len(periods) == 12
            assert periods[0].start_date == date(2026, 7, 1)

            # 2. Warehouses (including quarantine)
            whs = (await db.execute(select(Warehouse).where(Warehouse.tenant_id == tenant_id))).scalars().all()
            assert len(whs) >= 3
            wh_codes = [w.warehouse_code for w in whs]
            assert "WH-RAW-MATERIALS" in wh_codes
            assert "WH-QUARANTINE" in wh_codes

            # 3. Tenant Settings
            settings = (
                await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))
            ).scalar_one_or_none()
            assert settings is not None
            assert settings.valuation_method == "FIFO"

            # 4. Chart of Accounts with PKR currency
            accounts = (await db.execute(select(Account).where(Account.tenant_id == tenant_id))).scalars().all()
            assert len(accounts) >= 14
            for acc in accounts:
                assert acc.currency == "PKR"

            # 5. Demo Data items seeded
            items = (await db.execute(select(Item).where(Item.tenant_id == tenant_id))).scalars().all()
            assert len(items) >= 3

        # ---------------------------------------------------------
        # STAGE 3: In-App Module Onboarding (Dynamic Database-Backed)
        # ---------------------------------------------------------
        onboarding_resp = await client.get("/api/v1/onboarding/progress", headers=new_headers)
        assert onboarding_resp.status_code == 200, onboarding_resp.text
        onboarding_data = onboarding_resp.json()

        assert "overall_progress_pct" in onboarding_data
        assert onboarding_data["total_steps"] > 0
        # Because demo data was seeded, several steps (item created, supplier created, PO created, etc.)
        # should already be auto-verified by the live database check!
        assert onboarding_data["completed_steps"] > 0
        assert onboarding_data["overall_progress_pct"] > 0

        modules = onboarding_data["modules"]
        assert len(modules) == 5

        # Test manual step completion
        # Find a VIEW_REPORT step
        first_mod = modules[0]
        view_step = next(s for s in first_mod["steps"] if s["action_type"] == "VIEW_REPORT")
        step_id = view_step["step_id"]

        complete_resp = await client.post(f"/api/v1/onboarding/steps/{step_id}/complete", headers=new_headers)
        assert complete_resp.status_code == 200
        assert complete_resp.json()["is_complete"] is True

        # Test module skip
        skip_resp = await client.post("/api/v1/onboarding/modules/inventory/skip", headers=new_headers)
        assert skip_resp.status_code == 200

        # Verify progress re-query shows inventory module is complete
        onboarding_resp2 = await client.get("/api/v1/onboarding/progress", headers=new_headers)
        inv_mod = next(m for m in onboarding_resp2.json()["modules"] if m["module_slug"] == "inventory")
        assert inv_mod["is_complete"] is True
        assert inv_mod["completed_steps"] == inv_mod["total_steps"]
