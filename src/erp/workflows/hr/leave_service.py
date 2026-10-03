"""Leave Policies, Allocations, Applications, and Balance Tracking Domain Service."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.hr import LeaveAllocation, LeaveApplication, LeaveType


class LeaveService:
    """Manages leave entitlements, quota allocations, application validation, and approval workflows."""

    async def create_leave_type(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        type_name: str,
        max_days_allowed: int = 14,
        is_carry_forward: bool = False,
        is_lwp: bool = False,
    ) -> LeaveType:
        name_clean = type_name.strip()
        existing_stmt = select(LeaveType).where(
            LeaveType.tenant_id == tenant_id,
            LeaveType.type_name == name_clean,
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise ValueError(f"Leave type '{name_clean}' already exists.")

        lt = LeaveType(
            tenant_id=tenant_id,
            type_name=name_clean,
            max_days_allowed=max_days_allowed,
            is_carry_forward=is_carry_forward,
            is_lwp=is_lwp,
            is_active=True,
        )
        db.add(lt)
        await db.flush()
        return lt

    async def list_leave_types(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[LeaveType]:
        stmt = (
            select(LeaveType)
            .where(LeaveType.tenant_id == tenant_id)
            .order_by(LeaveType.type_name.asc())
        )
        existing = list((await db.execute(stmt)).scalars().all())
        if not existing:
            defaults = [
                ("Annual Privilege Leave", 14, True, False),
                ("Casual Leave", 10, False, False),
                ("Sick Leave", 10, False, False),
                ("Leave Without Pay (LWP)", 0, False, True),
            ]
            for name, max_d, cf, lwp in defaults:
                lt = LeaveType(
                    tenant_id=tenant_id,
                    type_name=name,
                    max_days_allowed=max_d,
                    is_carry_forward=cf,
                    is_lwp=lwp,
                    is_active=True,
                )
                db.add(lt)
            await db.flush()
            existing = list((await db.execute(stmt)).scalars().all())

        return existing

    async def allocate_leaves(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        fiscal_year: int,
        total_leaves_allocated: Decimal,
        carry_forward_leaves: Decimal = Decimal("0.00"),
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> LeaveAllocation:
        start_d = from_date or date(fiscal_year, 1, 1)
        end_d = to_date or date(fiscal_year, 12, 31)

        # Check existing allocation
        stmt = select(LeaveAllocation).where(
            LeaveAllocation.tenant_id == tenant_id,
            LeaveAllocation.employee_id == employee_id,
            LeaveAllocation.leave_type_id == leave_type_id,
            LeaveAllocation.fiscal_year == fiscal_year,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.total_leaves_allocated = total_leaves_allocated
            existing.carry_forward_leaves = carry_forward_leaves
            existing.from_date = start_d
            existing.to_date = end_d
            await db.flush()
            return existing

        alloc = LeaveAllocation(
            tenant_id=tenant_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            fiscal_year=fiscal_year,
            total_leaves_allocated=total_leaves_allocated,
            carry_forward_leaves=carry_forward_leaves,
            from_date=start_d,
            to_date=end_d,
        )
        db.add(alloc)
        await db.flush()
        return alloc

    async def get_leave_balance(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        fiscal_year: int | None = None,
    ) -> dict[str, Any]:
        year = fiscal_year or date.today().year

        # Get leave type
        lt_stmt = select(LeaveType).where(
            LeaveType.tenant_id == tenant_id,
            LeaveType.leave_type_id == leave_type_id,
        )
        leave_type = (await db.execute(lt_stmt)).scalar_one_or_none()
        if not leave_type:
            raise ValueError(f"LeaveType {leave_type_id} not found.")

        if leave_type.is_lwp:
            return {
                "leave_type_id": str(leave_type_id),
                "type_name": leave_type.type_name,
                "is_lwp": True,
                "allocated": Decimal("9999.00"),
                "used": Decimal("0.00"),
                "remaining": Decimal("9999.00"),
            }

        # Query allocation
        alloc_stmt = select(LeaveAllocation).where(
            LeaveAllocation.tenant_id == tenant_id,
            LeaveAllocation.employee_id == employee_id,
            LeaveAllocation.leave_type_id == leave_type_id,
            LeaveAllocation.fiscal_year == year,
        )
        alloc = (await db.execute(alloc_stmt)).scalar_one_or_none()
        allocated = (
            (alloc.total_leaves_allocated + alloc.carry_forward_leaves)
            if alloc
            else Decimal("0.00")
        )

        # Query approved leaves in year
        used_stmt = select(func.coalesce(func.sum(LeaveApplication.total_leave_days), Decimal("0.00"))).where(
            LeaveApplication.tenant_id == tenant_id,
            LeaveApplication.employee_id == employee_id,
            LeaveApplication.leave_type_id == leave_type_id,
            LeaveApplication.status == "APPROVED",
            LeaveApplication.from_date >= date(year, 1, 1),
            LeaveApplication.from_date <= date(year, 12, 31),
        )
        used = Decimal(str((await db.execute(used_stmt)).scalar() or "0.00"))

        return {
            "leave_type_id": str(leave_type_id),
            "type_name": leave_type.type_name,
            "is_lwp": False,
            "allocated": allocated,
            "used": used,
            "remaining": max(Decimal("0.00"), allocated - used),
        }

    async def submit_leave_application(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        from_date: date,
        to_date: date,
        total_leave_days: Decimal,
        is_half_day: bool = False,
        reason: str = "Personal Leave",
    ) -> LeaveApplication:
        # Check leave balance if not LWP
        balance_info = await self.get_leave_balance(
            db, tenant_id, employee_id, leave_type_id, from_date.year
        )
        if not balance_info["is_lwp"] and total_leave_days > balance_info["remaining"]:
            raise ValueError(
                f"Insufficient leave balance for {balance_info['type_name']}. "
                f"Requested: {total_leave_days} days, Available: {balance_info['remaining']} days."
            )

        app_num = f"LA-{date.today().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        app = LeaveApplication(
            tenant_id=tenant_id,
            application_number=app_num,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            from_date=from_date,
            to_date=to_date,
            total_leave_days=total_leave_days,
            is_half_day=is_half_day,
            reason=reason,
            status="SUBMITTED",
        )
        db.add(app)
        await db.flush()
        return app

    async def approve_leave_application(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        approved_by_id: uuid.UUID | None = None,
    ) -> LeaveApplication:
        stmt = select(LeaveApplication).where(
            LeaveApplication.tenant_id == tenant_id,
            LeaveApplication.application_id == application_id,
        )
        app = (await db.execute(stmt)).scalar_one_or_none()
        if not app:
            raise ValueError(f"LeaveApplication {application_id} not found.")

        app.status = "APPROVED"
        app.approved_by_id = approved_by_id
        await db.flush()
        return app

    async def reject_leave_application(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        application_id: uuid.UUID,
        reason: str | None = None,
    ) -> LeaveApplication:
        stmt = select(LeaveApplication).where(
            LeaveApplication.tenant_id == tenant_id,
            LeaveApplication.application_id == application_id,
        )
        app = (await db.execute(stmt)).scalar_one_or_none()
        if not app:
            raise ValueError(f"LeaveApplication {application_id} not found.")

        app.status = "REJECTED"
        if reason:
            app.reason = f"{app.reason} (Rejected: {reason})"
        await db.flush()
        return app

    async def list_leave_applications(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[LeaveApplication]:
        stmt = select(LeaveApplication).where(LeaveApplication.tenant_id == tenant_id)
        if employee_id:
            stmt = stmt.where(LeaveApplication.employee_id == employee_id)
        if status:
            stmt = stmt.where(LeaveApplication.status == status)
        stmt = stmt.order_by(LeaveApplication.created_at.desc())
        return list((await db.execute(stmt)).scalars().all())


leave_service = LeaveService()
