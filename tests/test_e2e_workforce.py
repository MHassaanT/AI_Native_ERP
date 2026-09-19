"""End-to-End Test Suite for HR Workforce & Shift Swapping.

Verifies:
1. Employee Roster and Shift Schedule Persistence in PostgreSQL
2. Statutory 48-Hour Weekly Overtime Rejection based on Real DB Shifts
3. Compliant Shift Trade Approval & True Database Shift Reassignment
"""

from datetime import date, datetime, time, timedelta, timezone
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from erp.api.app import app
from erp.db.engine import async_engine
from erp.db.session import async_session_factory
from erp.db.models.hr import Employee, ShiftSchedule


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await async_engine.dispose()


@pytest.mark.asyncio
async def test_workforce_shift_trade_lifecycle():
    slug = f"hr-{uuid.uuid4().hex[:6]}"
    email = f"hr-director@{slug}.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 0: Register Tenant
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "company_name": "Precision Aero Workforce Corp",
                "tenant_slug": slug,
                "email": email,
                "password": "PasswordHR123!",
                "full_name": "HR Director",
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        tenant_id = uuid.UUID(reg_res.json()["user"]["tenant_id"])
        headers = {"Authorization": f"Bearer {token}"}

        # Step 1: Create Employees
        emp_a_res = await client.post(
            "/api/v1/workforce/employees",
            json={
                "employee_code": "EMP-ALICE",
                "first_name": "Alice",
                "last_name": "Vance",
                "email": "alice@aero.com",
                "department": "MANUFACTURING",
                "certifications": ["CNC_LEVEL_3", "SAFETY_FIRST_AID"],
                "max_weekly_hours": 48,
            },
            headers=headers,
        )
        assert emp_a_res.status_code == 201, emp_a_res.text
        alice_id = uuid.UUID(emp_a_res.json()["employee_id"])

        emp_b_res = await client.post(
            "/api/v1/workforce/employees",
            json={
                "employee_code": "EMP-BOB",
                "first_name": "Bob",
                "last_name": "Stone",
                "email": "bob@aero.com",
                "department": "MANUFACTURING",
                "certifications": ["CNC_LEVEL_3"],
                "max_weekly_hours": 48,
            },
            headers=headers,
        )
        assert emp_b_res.status_code == 201, emp_b_res.text
        bob_id = uuid.UUID(emp_b_res.json()["employee_id"])

        emp_c_res = await client.post(
            "/api/v1/workforce/employees",
            json={
                "employee_code": "EMP-CHARLIE",
                "first_name": "Charlie",
                "last_name": "Day",
                "email": "charlie@aero.com",
                "department": "MANUFACTURING",
                "certifications": ["CNC_LEVEL_3"],
                "max_weekly_hours": 48,
            },
            headers=headers,
        )
        assert emp_c_res.status_code == 201, emp_c_res.text
        charlie_id = uuid.UUID(emp_c_res.json()["employee_id"])

        # Base reference date: Monday of current week
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        # Step 2: Populate Roster in DB
        # Bob already has 42 hours scheduled across Monday-Thursday (two 10h shifts, two 11h shifts)
        # Shift 1 (Mon): 10h
        # Shift 2 (Tue): 10h
        # Shift 3 (Wed): 11h
        # Shift 4 (Thu): 11h -> Total 42h
        bob_shifts = [
            ("SHIFT-BOB-01", monday, 8, 18),        # 10h
            ("SHIFT-BOB-02", monday + timedelta(days=1), 8, 18),  # 10h
            ("SHIFT-BOB-03", monday + timedelta(days=2), 7, 18),  # 11h
            ("SHIFT-BOB-04", monday + timedelta(days=3), 7, 18),  # 11h
        ]
        for sc, sdate, shour, ehour in bob_shifts:
            start_dt = datetime.combine(sdate, time(shour, 0), tzinfo=timezone.utc)
            end_dt = datetime.combine(sdate, time(ehour, 0), tzinfo=timezone.utc)
            s_res = await client.post(
                "/api/v1/workforce/shifts",
                json={
                    "shift_code": sc,
                    "employee_code": "EMP-BOB",
                    "shift_date": sdate.isoformat(),
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat(),
                    "status": "SCHEDULED",
                },
                headers=headers,
            )
            assert s_res.status_code == 201, s_res.text

        # Charlie only has 16 hours scheduled (Monday & Tuesday 8h each)
        charlie_shifts = [
            ("SHIFT-CHARLIE-01", monday, 8, 16),
            ("SHIFT-CHARLIE-02", monday + timedelta(days=1), 8, 16),
        ]
        for sc, sdate, shour, ehour in charlie_shifts:
            start_dt = datetime.combine(sdate, time(shour, 0), tzinfo=timezone.utc)
            end_dt = datetime.combine(sdate, time(ehour, 0), tzinfo=timezone.utc)
            s_res = await client.post(
                "/api/v1/workforce/shifts",
                json={
                    "shift_code": sc,
                    "employee_code": "EMP-CHARLIE",
                    "shift_date": sdate.isoformat(),
                    "start_time": start_dt.isoformat(),
                    "end_time": end_dt.isoformat(),
                    "status": "SCHEDULED",
                },
                headers=headers,
            )
            assert s_res.status_code == 201, s_res.text

        # Alice has an 8h Friday shift to trade (08:00 to 16:00)
        friday = monday + timedelta(days=4)
        alice_shift_start = datetime.combine(friday, time(8, 0), tzinfo=timezone.utc)
        alice_shift_end = datetime.combine(friday, time(16, 0), tzinfo=timezone.utc)
        alice_s_res = await client.post(
            "/api/v1/workforce/shifts",
            json={
                "shift_code": "SHIFT-ALICE-FRI",
                "employee_code": "EMP-ALICE",
                "shift_date": friday.isoformat(),
                "start_time": alice_shift_start.isoformat(),
                "end_time": alice_shift_end.isoformat(),
                "status": "SCHEDULED",
            },
            headers=headers,
        )
        assert alice_s_res.status_code == 201, alice_s_res.text
        alice_shift_id = uuid.UUID(alice_s_res.json()["shift_id"])

        # Step 3: Negative Test - Attempt Trade with Bob (42h + 8h = 50h > 48h limit)
        # Should be REJECTED with STATUTORY_OVERTIME_VIOLATION
        trade_bob_res = await client.post(
            "/api/v1/workforce/shift-trade/evaluate",
            json={
                "requesting_employee": "EMP-ALICE",
                "target_employee": "EMP-BOB",
                "shift_id": str(alice_shift_id),
                "shift_role": "CNC_OPERATOR",
            },
            headers=headers,
        )
        assert trade_bob_res.status_code == 200, trade_bob_res.text
        trade_bob_data = trade_bob_res.json()
        assert trade_bob_data["is_approved"] is False, "Overtime trade should NOT be approved"
        assert trade_bob_data["is_hours_compliant"] is False
        assert any("STATUTORY_OVERTIME_VIOLATION" in r for r in trade_bob_data["rejection_reasons"])
        assert trade_bob_data["projected_weekly_hours"] == 50.0

        # Verify DB: Alice's shift was NOT reassigned
        async with async_session_factory() as session:
            shift_unchanged = (
                await session.execute(
                    select(ShiftSchedule).where(
                        ShiftSchedule.tenant_id == tenant_id,
                        ShiftSchedule.shift_id == alice_shift_id,
                    )
                )
            ).scalar_one()
            assert shift_unchanged.employee_id == alice_id
            assert shift_unchanged.status == "SCHEDULED"

        # Step 4: Positive Test - Trade with Charlie (16h + 8h = 24h <= 48h, Rest > 11h)
        # Should be APPROVED and persisted to DB
        trade_charlie_res = await client.post(
            "/api/v1/workforce/shift-trade/evaluate",
            json={
                "requesting_employee": "EMP-ALICE",
                "target_employee": "EMP-CHARLIE",
                "shift_id": str(alice_shift_id),
                "shift_role": "CNC_OPERATOR",
            },
            headers=headers,
        )
        assert trade_charlie_res.status_code == 200, trade_charlie_res.text
        trade_charlie_data = trade_charlie_res.json()
        assert trade_charlie_data["is_approved"] is True
        assert trade_charlie_data["is_hours_compliant"] is True
        assert trade_charlie_data["is_rest_compliant"] is True
        assert trade_charlie_data["projected_weekly_hours"] == 24.0

        # Verify DB: Alice's shift was truly reassigned to Charlie in PostgreSQL!
        async with async_session_factory() as session:
            shift_transferred = (
                await session.execute(
                    select(ShiftSchedule).where(
                        ShiftSchedule.tenant_id == tenant_id,
                        ShiftSchedule.shift_id == alice_shift_id,
                    )
                )
            ).scalar_one()
            assert shift_transferred.employee_id == charlie_id, "Shift must be reassigned to Charlie in DB"
            assert shift_transferred.status == "TRANSFERRED"
