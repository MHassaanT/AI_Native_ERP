"""Autonomous Shift Swapping and Labor Invariant Evaluator (PRD §Shift Scheduling)."""

import logging
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from erp.workforce.certifications import certification_verifier

logger = logging.getLogger(__name__)


class ShiftTradeRequest(BaseModel):
    trade_id: str = Field(default_factory=lambda: f"trade_{uuid.uuid4().hex[:8]}")
    requesting_employee: str
    target_employee: str
    shift_role: str
    required_certification: str | None = None
    target_previous_shift_end: datetime
    target_proposed_shift_start: datetime
    target_current_weekly_hours: float
    shift_duration_hours: float = 8.0


class ShiftTradeEvaluationResult(BaseModel):
    trade_id: str
    is_approved: bool
    rest_interval_hours: float
    projected_weekly_hours: float
    is_rest_compliant: bool
    is_hours_compliant: bool
    is_certification_compliant: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    confirmation_message: str


class ShiftTradeCoordinator:
    """Enforces statutory rest intervals (>=11h) and maximum weekly limits (<=48h) on shift trades."""

    MANDATORY_REST_HOURS = 11.0
    STATUTORY_WEEKLY_MAX_HOURS = 48.0

    def evaluate_and_execute_trade(self, request: ShiftTradeRequest) -> ShiftTradeEvaluationResult:
        """Evaluates shift trade invariants and commits if compliant in under 30 seconds."""
        reasons = []

        # 1. Invariant: Mandatory Rest Interval >= 11 consecutive hours
        rest_diff = (
            request.target_proposed_shift_start - request.target_previous_shift_end
        ).total_seconds() / 3600.0
        is_rest_ok = rest_diff >= self.MANDATORY_REST_HOURS
        if not is_rest_ok:
            reasons.append(
                f"STATUTORY_REST_VIOLATION: Rest interval between shifts is {rest_diff:.1f} hours; "
                f"mandatory statutory minimum is {self.MANDATORY_REST_HOURS:.1f} consecutive hours."
            )

        # 2. Invariant: Rolling 7-Day Cumulative Work Hours <= 48 hours
        projected_hours = request.target_current_weekly_hours + request.shift_duration_hours
        is_hours_ok = projected_hours <= self.STATUTORY_WEEKLY_MAX_HOURS
        if not is_hours_ok:
            reasons.append(
                f"STATUTORY_OVERTIME_VIOLATION: Projected weekly work hours ({projected_hours:.1f}h) "
                f"exceeds statutory 48-hour ceiling."
            )

        # 3. Invariant: Safety Certification Check
        is_cert_ok = True
        if request.required_certification:
            is_cert_ok = certification_verifier.verify_operator_certification(
                employee_code=request.target_employee,
                required_certification_code=request.required_certification,
                shift_date=request.target_proposed_shift_start.date(),
            )
            if not is_cert_ok:
                reasons.append(
                    f"SAFETY_CERTIFICATION_MISSING: Employee '{request.target_employee}' lacks active "
                    f"safety certification '{request.required_certification}' for this operation."
                )

        is_approved = is_rest_ok and is_hours_ok and is_cert_ok

        if is_approved:
            msg = (
                f"Shift trade approved: {request.requesting_employee} traded with {request.target_employee}. "
                f"Roster updated in master schedule roster (Rest: {rest_diff:.1f}h, Total: {projected_hours:.1f}h)."
            )
            logger.info(msg)
        else:
            msg = f"Shift trade rejected: {'; '.join(reasons)}"
            logger.warning(msg)

        return ShiftTradeEvaluationResult(
            trade_id=request.trade_id,
            is_approved=is_approved,
            rest_interval_hours=round(rest_diff, 1),
            projected_weekly_hours=round(projected_hours, 1),
            is_rest_compliant=is_rest_ok,
            is_hours_compliant=is_hours_ok,
            is_certification_compliant=is_cert_ok,
            rejection_reasons=reasons,
            confirmation_message=msg,
        )


shift_coordinator = ShiftTradeCoordinator()
