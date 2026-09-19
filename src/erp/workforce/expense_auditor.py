"""Multi-Modal Expense Claim Auditor and Policy Validator (PRD §Expense Management)."""

import hashlib
import logging
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from erp.ledger.engine import LedgerCommitResult, TransactionProposal, ledger_engine
from erp.ledger.invariants import LedgerLineProposal

logger = logging.getLogger(__name__)


class ExpenseAuditRequest(BaseModel):
    claim_id: str = Field(default_factory=lambda: f"claim_{uuid.uuid4().hex[:8]}")
    employee_code: str
    expense_category: str  # MEALS, LODGING, TRANSPORT, SUPPLIES
    claim_date: date
    total_amount: Decimal
    contains_alcohol: bool = False
    receipt_text: str = ""
    receipt_image_hash: str | None = None


class ExpenseAuditResult(BaseModel):
    claim_id: str
    is_compliant: bool
    is_auto_approved: bool
    policy_violations: list[str] = Field(default_factory=list)
    ledger_commit: LedgerCommitResult | None = None
    audit_summary: str


class ExpenseAuditor:
    """Audits employee travel expense claims against corporate policy rules and daily limits."""

    DAILY_MEAL_CAP = Decimal("75.00")
    AUTO_APPROVAL_CEILING = Decimal("500.00")

    def __init__(self):
        # Set of seen receipt image hashes to detect duplicates
        self._processed_receipt_hashes: set[str] = set()

    async def audit_and_reimburse(
        self,
        session: AsyncSession | None,
        tenant_id: uuid.UUID,
        claim: ExpenseAuditRequest,
    ) -> ExpenseAuditResult:
        """Audits expense claim and commits AP reimbursement entry if compliant and under $500."""
        violations = []

        # 1. Receipt Deduplication
        img_hash = (
            claim.receipt_image_hash
            or hashlib.sha256(claim.receipt_text.encode("utf-8")).hexdigest()
        )
        if img_hash in self._processed_receipt_hashes:
            violations.append(
                "DUPLICATE_RECEIPT: This receipt image or text has already been submitted for reimbursement."
            )

        # 2. Meal Daily Cap Enforcement ($75.00/day)
        if claim.expense_category.upper() == "MEALS" and claim.total_amount > self.DAILY_MEAL_CAP:
            violations.append(
                f"MEAL_CAP_EXCEEDED: Claim amount ${claim.total_amount:.2f} exceeds corporate daily meal cap "
                f"of ${self.DAILY_MEAL_CAP:.2f}."
            )

        # 3. Alcohol Restriction
        if claim.contains_alcohol:
            violations.append(
                "POLICY_VIOLATION: Alcoholic beverages are strictly non-reimbursable under corporate travel policy."
            )

        is_compliant = len(violations) == 0
        auto_approved = is_compliant and claim.total_amount <= self.AUTO_APPROVAL_CEILING

        commit_res = None

        if is_compliant:
            self._processed_receipt_hashes.add(img_hash)

            # Auto-approve & stage ledger transaction if under $500
            if auto_approved and session is not None:
                # Debit: 5100-EXP-TRAVEL, Credit: 2110-AP-EMPLOYEES
                entries = [
                    LedgerLineProposal(
                        account_code="5100-EXP-TRAVEL",
                        cost_center="CORP-FINANCE",
                        debit_amount=claim.total_amount,
                        credit_amount=Decimal("0.0000"),
                        currency="USD",
                    ),
                    LedgerLineProposal(
                        account_code="2110-AP-EMPLOYEES",
                        cost_center="CORP-FINANCE",
                        debit_amount=Decimal("0.0000"),
                        credit_amount=claim.total_amount,
                        currency="USD",
                    ),
                ]

                proposal = TransactionProposal(
                    tenant_id=tenant_id,
                    posting_date=claim.claim_date,
                    currency="USD",
                    source_document_type="AUTONOMOUS_EXPENSE_REIMBURSEMENT",
                    source_document_id=uuid.uuid4(),
                    entries=entries,
                    human_in_the_loop_approved=False,
                    agent_id="WORKFORCE_EXPENSE",
                    verification_context={
                        "claim_id": claim.claim_id,
                        "employee_code": claim.employee_code,
                        "category": claim.expense_category,
                    },
                )
                commit_res = await ledger_engine.commit_transaction(
                    session=session, proposal=proposal
                )
                logger.info(
                    "Expense claim %s auto-approved. Ledger txn: %s",
                    claim.claim_id,
                    commit_res.transaction_id,
                )

        summary = (
            f"Claim auto-approved and queued for payout (${claim.total_amount:.2f})"
            if auto_approved
            else f"Claim flagged: {'; '.join(violations)}"
        )

        return ExpenseAuditResult(
            claim_id=claim.claim_id,
            is_compliant=is_compliant,
            is_auto_approved=auto_approved,
            policy_violations=violations,
            ledger_commit=commit_res,
            audit_summary=summary,
        )


expense_auditor = ExpenseAuditor()
