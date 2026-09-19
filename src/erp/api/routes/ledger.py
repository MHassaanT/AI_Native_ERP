"""Ledger Engine API Endpoints."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.db.models.ledger import Account, GeneralLedgerEntry
from erp.ledger.engine import LedgerCommitResult, TransactionProposal, ledger_engine
from erp.ledger.exceptions import (
    AccountNotFoundError,
    AutonomyCeilingExceeded,
    CostCenterNotFoundError,
    LedgerError,
    PeriodLockedError,
    SingleSidedViolation,
    ZeroSumViolation,
)
from erp.ledger.invariants import LedgerLineProposal

router = APIRouter(prefix="/ledger", tags=["Deterministic Ledger Engine"])


class StageTransactionRequest(BaseModel):
    posting_date: date
    currency: str = Field(default="USD", max_length=3)
    source_document_type: str = Field(..., max_length=64)
    source_document_id: uuid.UUID
    entries: list[LedgerLineProposal]
    human_in_the_loop_approved: bool = False
    approved_by_user_id: uuid.UUID | None = None
    verification_context: dict = Field(default_factory=dict)
    agent_id: str = "API_REQUEST"


class GLEntryResponse(BaseModel):
    entry_id: uuid.UUID
    transaction_id: uuid.UUID
    posting_date: date
    account_code: str
    cost_center: str
    debit_amount: Decimal
    credit_amount: Decimal
    currency: str
    source_document_type: str
    source_document_id: uuid.UUID


@router.post(
    "/stage",
    response_model=LedgerCommitResult,
    status_code=status.HTTP_201_CREATED,
    summary="Stage and atomically validate/commit a ledger transaction",
)
async def stage_transaction(
    req: StageTransactionRequest,
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Processes a transaction proposal through the Deterministic Ledger Engine."""
    proposal = TransactionProposal(
        tenant_id=tenant_id,
        posting_date=req.posting_date,
        currency=req.currency,
        source_document_type=req.source_document_type,
        source_document_id=req.source_document_id,
        entries=req.entries,
        human_in_the_loop_approved=req.human_in_the_loop_approved,
        approved_by_user_id=req.approved_by_user_id,
        verification_context=req.verification_context,
        agent_id=req.agent_id,
    )

    try:
        result = await ledger_engine.commit_transaction(session=db, proposal=proposal)
        return result
    except (ZeroSumViolation, SingleSidedViolation) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except PeriodLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except (AccountNotFoundError, CostCenterNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except AutonomyCeilingExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except LedgerError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/entries",
    response_model=list[GLEntryResponse],
    summary="Query general ledger entries for tenant",
)
async def list_gl_entries(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Returns general ledger entries filtered strictly by tenant isolation."""
    stmt = (
        select(GeneralLedgerEntry)
        .where(GeneralLedgerEntry.tenant_id == tenant_id)
        .order_by(GeneralLedgerEntry.posting_date.desc(), GeneralLedgerEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()
    return entries


@router.get(
    "/accounts",
    summary="List chart of accounts for tenant",
)
async def list_accounts(
    tenant_id: TenantIdDep,
    db: DbSessionDep,
):
    """Returns all accounts configured in the tenant's Chart of Accounts."""
    stmt = select(Account).where(Account.tenant_id == tenant_id).order_by(Account.account_code)
    result = await db.execute(stmt)
    accounts = result.scalars().all()
    return accounts
