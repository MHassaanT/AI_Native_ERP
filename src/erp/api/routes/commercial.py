import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from erp.api.deps import DbSessionDep, TenantIdDep
from erp.commercial.bom_cost_rollup import (
    BOMCostRollupResult,
    bom_rollup_engine,
)
from erp.commercial.pdf_generator import (
    QuotationData,
    pdf_generator,
)
from erp.commercial.pricing_engine import (
    DynamicPricingEvaluation,
    pricing_engine,
)
from erp.commercial.quote_invalidator import (
    QuoteInvalidationNotice,
    quote_invalidator,
)
from erp.db.models.sales import Customer, SalesQuotation

router = APIRouter(prefix="/commercial", tags=["Commercial & Dynamic Pricing Agent"])


class CreateCustomerRequest(BaseModel):
    customer_code: str = Field(..., min_length=2, max_length=64)
    customer_name: str = Field(..., min_length=2, max_length=255)
    email: str | None = None
    credit_limit: Decimal = Decimal("50000.00")


class CreateSalesQuoteRequest(BaseModel):
    quotation_number: str = Field(..., min_length=2, max_length=64)
    customer_id: uuid.UUID
    quotation_date: date
    valid_until: date
    subtotal: Decimal
    tax_amount: Decimal = Decimal("0.00")
    contribution_margin_pct: Decimal = Decimal("25.00")


@router.get("/customers", summary="List customers")
async def list_customers(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns commercial customers for the tenant."""
    stmt = (
        select(Customer)
        .where(Customer.tenant_id == tenant_id)
        .order_by(Customer.customer_name.asc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/customers", status_code=status.HTTP_201_CREATED, summary="Create customer")
async def create_customer(req: CreateCustomerRequest, tenant_id: TenantIdDep, db: DbSessionDep):
    """Adds a new commercial customer account."""
    existing = (
        await db.execute(
            select(Customer).where(
                Customer.tenant_id == tenant_id, Customer.customer_code == req.customer_code
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Customer '{req.customer_code}' already exists.",
        )

    cust = Customer(
        tenant_id=tenant_id,
        customer_code=req.customer_code,
        customer_name=req.customer_name,
        email=req.email,
        credit_limit=req.credit_limit,
        lifetime_value=Decimal("0.0000"),
        is_active=True,
    )
    db.add(cust)
    await db.flush()
    return cust


@router.get("/quotes", summary="List sales quotations")
async def list_sales_quotes(tenant_id: TenantIdDep, db: DbSessionDep):
    """Returns dynamic commercial quotations for the tenant."""
    stmt = (
        select(SalesQuotation)
        .where(SalesQuotation.tenant_id == tenant_id)
        .order_by(SalesQuotation.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/quotes", status_code=status.HTTP_201_CREATED, summary="Create sales quotation")
async def create_sales_quote(
    req: CreateSalesQuoteRequest, tenant_id: TenantIdDep, db: DbSessionDep
):
    """Records a new evaluated commercial sales quotation."""
    total = req.subtotal + req.tax_amount
    quote = SalesQuotation(
        tenant_id=tenant_id,
        quotation_number=req.quotation_number,
        customer_id=req.customer_id,
        quotation_date=req.quotation_date,
        valid_until=req.valid_until,
        subtotal=req.subtotal,
        tax_amount=req.tax_amount,
        total_amount=total,
        contribution_margin_pct=req.contribution_margin_pct,
        status="OFFICIAL",
    )
    db.add(quote)
    await db.flush()
    return quote


class PricingCalculateRequest(BaseModel):
    sku: str
    bom_material_cost: Decimal
    machine_depreciation: Decimal = Decimal("4.5000")
    direct_labor: Decimal = Decimal("6.0000")
    freight: Decimal = Decimal("1.2500")
    target_markup_multiplier: Decimal = Decimal("1.3500")


class BOMRollupRequest(BaseModel):
    parent_sku: str
    material_deltas: dict[str, tuple[Decimal, Decimal, Decimal]] = Field(
        description="component_sku -> (unit_quantity, old_unit_price, new_unit_price)"
    )


class QuoteInvalidateRequest(BaseModel):
    quote_number: str
    customer_name: str
    sku: str
    current_quoted_price: Decimal
    new_bom_material_cost: Decimal


@router.post("/pricing/calculate", response_model=DynamicPricingEvaluation)
async def calculate_pricing(req: PricingCalculateRequest) -> DynamicPricingEvaluation:
    """Calculates landed cost and defends corporate 22.0% contribution margin floor."""
    try:
        return pricing_engine.calculate_margin_defended_price(
            sku=req.sku,
            bom_material_cost=req.bom_material_cost,
            machine_depreciation=req.machine_depreciation,
            direct_labor=req.direct_labor,
            freight=req.freight,
            target_markup_multiplier=req.target_markup_multiplier,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pricing calculation failed: {e!s}",
        ) from e


@router.post("/bom/rollup", response_model=BOMCostRollupResult)
async def calculate_bom_rollup(req: BOMRollupRequest) -> BOMCostRollupResult:
    """Calculates raw material cost growth across BOM components during supplier price spikes."""
    try:
        return bom_rollup_engine.calculate_bom_cost_delta(
            parent_sku=req.parent_sku,
            material_deltas=req.material_deltas,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"BOM rollup calculation failed: {e!s}",
        ) from e


@router.post("/quote/evaluate-invalidation", response_model=QuoteInvalidationNotice)
async def evaluate_quote_invalidation(req: QuoteInvalidateRequest) -> QuoteInvalidationNotice:
    """Evaluates whether raw material price inflation erodes quote margin below the 22% threshold."""
    try:
        return quote_invalidator.evaluate_active_quote(
            quote_number=req.quote_number,
            customer_name=req.customer_name,
            sku=req.sku,
            current_quoted_price=req.current_quoted_price,
            new_bom_material_cost=req.new_bom_material_cost,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quote invalidation evaluation failed: {e!s}",
        ) from e


@router.post("/quote/pdf")
async def generate_quote_pdf(quote: QuotationData):
    """Generates an official commercial PDF quotation document using ReportLab."""
    try:
        pdf_bytes = pdf_generator.generate_pdf(quote)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{quote.quote_number}.pdf"',
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {e!s}",
        ) from e
