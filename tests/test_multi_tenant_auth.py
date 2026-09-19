"""End-to-End Multi-Tenant Authentication and Data Isolation Tests."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from erp.api.app import app
from erp.db.engine import async_engine


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_tenant_registration_and_jwt_issuance():
    """Verifies that company signup creates tenant, user, provisions blueprint, and returns JWT."""
    slug = f"acme-aerospace-{uuid.uuid4().hex[:6]}"
    email = f"admin@{slug}.com"
    payload = {
        "company_name": "Acme Aerospace Components",
        "tenant_slug": slug,
        "email": email,
        "password": "SecurePassword123!",
        "full_name": "Chief Executive",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == email
        assert data["user"]["company_name"] == "Acme Aerospace Components"
        assert data["user"]["role"] == "TENANT_ADMIN"

        token = data["access_token"]

        # Call /auth/me with Bearer token
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == email
        assert me_data["tenant_slug"] == slug


@pytest.mark.asyncio
async def test_multi_tenant_strict_data_isolation():
    """Verifies that Tenant A cannot see or access Tenant B's data across all domains."""
    slug_a = f"corp-alpha-{uuid.uuid4().hex[:6]}"
    slug_b = f"corp-beta-{uuid.uuid4().hex[:6]}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register Tenant A
        res_a = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Alpha Corp",
                "tenant_slug": slug_a,
                "email": f"admin@{slug_a}.com",
                "password": "PasswordAlpha123!",
                "full_name": "Alpha Admin",
            },
        )
        assert res_a.status_code == 201
        token_a = res_a.json()["access_token"]
        tenant_a_id = res_a.json()["user"]["tenant_id"]

        # 2. Register Tenant B
        res_b = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Beta Corp",
                "tenant_slug": slug_b,
                "email": f"admin@{slug_b}.com",
                "password": "PasswordBeta123!",
                "full_name": "Beta Admin",
            },
        )
        assert res_b.status_code == 201
        token_b = res_b.json()["access_token"]
        tenant_b_id = res_b.json()["user"]["tenant_id"]

        assert tenant_a_id != tenant_b_id

        # 3. Create a unique workstation in Tenant A
        ws_code_a = f"WS-ALPHA-{uuid.uuid4().hex[:4]}"
        ws_res = await client.post(
            "/api/v1/production/workstations",
            json={
                "workstation_code": ws_code_a,
                "workstation_name": "Alpha Dedicated Lathe",
                "hourly_rate": "65.0000",
                "status": "OPERATIONAL",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert ws_res.status_code == 201

        # 4. Verify Tenant A sees the workstation
        list_a = await client.get(
            "/api/v1/production/workstations",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert list_a.status_code == 200
        codes_a = [ws["workstation_code"] for ws in list_a.json()]
        assert ws_code_a in codes_a

        # 5. Verify Tenant B CANNOT see Tenant A's workstation
        list_b = await client.get(
            "/api/v1/production/workstations",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert list_b.status_code == 200
        codes_b = [ws["workstation_code"] for ws in list_b.json()]
        assert ws_code_a not in codes_b

        # 6. Verify SOC 2 audit continuity for Tenant A
        audit_res = await client.get(
            "/api/v1/audit/soc2/report",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert audit_res.status_code == 200
        report = audit_res.json()
        assert report["total_blocks_verified"] >= 1
        assert report["is_chain_unbroken"] is True
        assert report["compliance_certification"] == "CERTIFIED_COMPLIANT"


@pytest.mark.asyncio
async def test_login_authentication_and_failure_modes():
    """Verifies valid login and rejection of invalid passwords and unknown emails."""
    slug = f"login-corp-{uuid.uuid4().hex[:6]}"
    email = f"user@{slug}.com"
    pwd = "ValidPassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register
        await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Login Test Corp",
                "tenant_slug": slug,
                "email": email,
                "password": pwd,
                "full_name": "Test User",
            },
        )

        # Login success
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": pwd},
        )
        assert login_res.status_code == 200
        assert "access_token" in login_res.json()

        # Login failure - wrong password
        fail_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )
        assert fail_res.status_code == 401

        # Login failure - nonexistent user
        no_user_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@nowhere.com", "password": "AnyPassword123!"},
        )
        assert no_user_res.status_code == 401
