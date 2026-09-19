"""Vendor Dispute Notice Generator (PRD §Accounts Payable)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel

from erp.workflows.accounts_payable.tolerance import ThreeWayToleranceSummary


class VendorDisputeNotice(BaseModel):
    dispute_id: str
    invoice_number: str
    supplier_code: str
    created_at: datetime
    overall_variance_percentage: Decimal
    discrepancy_details: list[str]
    resolution_instructions: str
    formatted_notice: str


class DisputeGenerator:
    """Generates structured vendor dispute artifacts and notices for non-compliant AP invoices."""

    @staticmethod
    def generate_notice(
        invoice_number: str,
        supplier_code: str,
        supplier_name: str,
        tolerance_summary: ThreeWayToleranceSummary,
    ) -> VendorDisputeNotice:
        dispute_id = f"disp_{uuid.uuid4().hex[:8]}"
        now = datetime.now(UTC)

        itemized_lines = "\n".join(f"- {d}" for d in tolerance_summary.discrepancies)

        formatted = (
            f"=================================================================\n"
            f"          ACCOUNTS PAYABLE AUTOMATED DISCREPANCY NOTICE          \n"
            f"=================================================================\n"
            f"Dispute ID: {dispute_id}\n"
            f"Notice Date: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Supplier: {supplier_name} ({supplier_code})\n"
            f"Invoice Reference: {invoice_number}\n"
            f"Overall Variance Detected: {tolerance_summary.overall_variance_percentage}%\n"
            f"Allowable Price Tolerance Floor: 1.00%\n"
            f"-----------------------------------------------------------------\n"
            f"ITEMIZED DISCREPANCIES IDENTIFIED:\n"
            f"{itemized_lines}\n"
            f"-----------------------------------------------------------------\n"
            f"ACTION REQUIRED:\n"
            f"Invoice '{invoice_number}' has been placed in 'DISPUTED' status and\n"
            f"will not be scheduled for ledger settlement until resolved.\n"
            f"Please submit a revised credit memo or corrected commercial invoice\n"
            f"directly via the Supplier Portal within 5 business days.\n"
            f"================================================================="
        )

        return VendorDisputeNotice(
            dispute_id=dispute_id,
            invoice_number=invoice_number,
            supplier_code=supplier_code,
            created_at=now,
            overall_variance_percentage=tolerance_summary.overall_variance_percentage,
            discrepancy_details=tolerance_summary.discrepancies,
            resolution_instructions="Submit credit memo or corrected invoice via portal within 5 business days.",
            formatted_notice=formatted,
        )


dispute_generator = DisputeGenerator()
