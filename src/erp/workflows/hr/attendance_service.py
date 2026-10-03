"""Shift Management and Attendance Tracking Domain Service."""

import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.db.models.hr import Attendance, ShiftAssignment, ShiftType


class AttendanceService:
    """Manages shifts, shift rosters, punch logs, late/early flags, and daily attendance records."""

    async def create_shift_type(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        shift_name: str,
        start_time: str,  # e.g. "09:00:00"
        end_time: str,    # e.g. "17:00:00"
        grace_period_mins: int = 15,
        half_day_threshold_hours: Decimal = Decimal("4.00"),
        late_mark_after_mins: int = 15,
    ) -> ShiftType:
        st = ShiftType(
            tenant_id=tenant_id,
            shift_name=shift_name,
            start_time=start_time,
            end_time=end_time,
            grace_period_mins=grace_period_mins,
            half_day_threshold_hours=half_day_threshold_hours,
            late_mark_after_mins=late_mark_after_mins,
            is_active=True,
        )
        db.add(st)
        await db.flush()
        return st

    async def list_shift_types(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[ShiftType]:
        stmt = (
            select(ShiftType)
            .where(ShiftType.tenant_id == tenant_id)
            .order_by(ShiftType.shift_name.asc())
        )
        return list((await db.execute(stmt)).scalars().all())

    async def assign_shift(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        shift_type_id: uuid.UUID,
        start_date: date,
        end_date: date | None = None,
    ) -> ShiftAssignment:
        assignment = ShiftAssignment(
            tenant_id=tenant_id,
            employee_id=employee_id,
            shift_type_id=shift_type_id,
            start_date=start_date,
            end_date=end_date,
            status="ACTIVE",
        )
        db.add(assignment)
        await db.flush()
        return assignment

    async def mark_attendance(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
        status: str = "PRESENT",  # PRESENT, ABSENT, ON_LEAVE, HALF_DAY
        in_time: datetime | None = None,
        out_time: datetime | None = None,
        remarks: str | None = None,
    ) -> Attendance:
        # Check if record already exists for date
        stmt = select(Attendance).where(
            Attendance.tenant_id == tenant_id,
            Attendance.employee_id == employee_id,
            Attendance.attendance_date == attendance_date,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        late_entry = False
        early_exit = False
        working_hours = Decimal("0.00")

        if in_time and out_time:
            diff_seconds = (out_time - in_time).total_seconds()
            if diff_seconds > 0:
                working_hours = Decimal(str(round(diff_seconds / 3600.0, 2)))

        # Find active shift to compute late and early flags
        shift_stmt = (
            select(ShiftType)
            .join(ShiftAssignment, ShiftAssignment.shift_type_id == ShiftType.shift_type_id)
            .where(
                ShiftAssignment.tenant_id == tenant_id,
                ShiftAssignment.employee_id == employee_id,
                ShiftAssignment.start_date <= attendance_date,
                ShiftAssignment.status == "ACTIVE",
            )
            .order_by(ShiftAssignment.start_date.desc())
        )
        shift = (await db.execute(shift_stmt)).scalars().first()

        if shift and in_time:
            # Parse shift start time e.g. "09:00:00"
            s_parts = [int(p) for p in shift.start_time.split(":")[:2]]
            shift_start_mins = s_parts[0] * 60 + s_parts[1]
            in_mins = in_time.hour * 60 + in_time.minute
            if in_mins > (shift_start_mins + shift.late_mark_after_mins):
                late_entry = True

        if shift and out_time:
            e_parts = [int(p) for p in shift.end_time.split(":")[:2]]
            shift_end_mins = e_parts[0] * 60 + e_parts[1]
            out_mins = out_time.hour * 60 + out_time.minute
            if out_mins < shift_end_mins:
                early_exit = True

        if shift and working_hours > 0 and working_hours < shift.half_day_threshold_hours and status == "PRESENT":
            status = "HALF_DAY"

        if existing:
            existing.status = status
            existing.in_time = in_time or existing.in_time
            existing.out_time = out_time or existing.out_time
            existing.late_entry = late_entry
            existing.early_exit = early_exit
            existing.working_hours = working_hours if working_hours > 0 else existing.working_hours
            existing.remarks = remarks or existing.remarks
            await db.flush()
            return existing

        att = Attendance(
            tenant_id=tenant_id,
            employee_id=employee_id,
            attendance_date=attendance_date,
            status=status,
            in_time=in_time,
            out_time=out_time,
            late_entry=late_entry,
            early_exit=early_exit,
            working_hours=working_hours,
            remarks=remarks,
        )
        db.add(att)
        await db.flush()
        return att

    async def list_attendances(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        employee_id: uuid.UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Attendance]:
        stmt = select(Attendance).where(Attendance.tenant_id == tenant_id)
        if employee_id:
            stmt = stmt.where(Attendance.employee_id == employee_id)
        if from_date:
            stmt = stmt.where(Attendance.attendance_date >= from_date)
        if to_date:
            stmt = stmt.where(Attendance.attendance_date <= to_date)
        stmt = stmt.order_by(Attendance.attendance_date.desc())
        return list((await db.execute(stmt)).scalars().all())


attendance_service = AttendanceService()
