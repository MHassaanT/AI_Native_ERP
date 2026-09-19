"""Type definitions generated from BAML contracts."""

from decimal import Decimal

from pydantic import BaseModel, Field


class InvoiceLineExtraction(BaseModel):
    item_code: str = Field(..., description="Matched SKU or internal inventory identifier")
    description: str = Field(..., description="Line description from the invoice")
    quantity: Decimal = Field(..., description="Billed units")
    unit_price: Decimal = Field(..., description="Price per unit excluding taxes")
    line_total: Decimal = Field(..., description="Computed net total for the line")
    tax_rate: Decimal = Field(
        default=Decimal("0.0000"), description="Applicable tax rate as a decimal"
    )


class InvoiceDocumentExtraction(BaseModel):
    vendor_tax_id: str = Field(..., description="Vendor VAT, EIN, or corporate tax identifier")
    vendor_name: str = Field(..., description="Vendor company name")
    invoice_number: str = Field(..., description="Vendor-issued invoice reference number")
    invoice_date: str = Field(..., description="Document date formatted as ISO-8601 YYYY-MM-DD")
    currency: str = Field(default="USD", description="Standard 3-character ISO currency code")
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    payment_terms_days: int = Field(default=30)
    line_items: list[InvoiceLineExtraction] = Field(default_factory=list)
    extraction_confidence: float = Field(default=0.98, ge=0.0, le=1.0)


class ExpenseItemExtraction(BaseModel):
    merchant_name: str
    category: str = "MEALS"
    transaction_date: str
    currency: str = "USD"
    total_amount: Decimal
    tax_amount: Decimal = Decimal("0.0000")
    contains_alcohol: bool = False
    extraction_confidence: float = Field(default=0.96, ge=0.0, le=1.0)


class RFQLineItem(BaseModel):
    requested_sku: str
    quantity: Decimal
    uom: str = "Nos"
    target_unit_price: Decimal | None = None
    custom_specifications: str | None = None


class RFQExtraction(BaseModel):
    customer_name: str
    customer_email: str | None = None
    rfq_reference: str | None = None
    required_delivery_date: str | None = None
    line_items: list[RFQLineItem] = Field(default_factory=list)
    commercial_urgency: str = "STANDARD"
    extraction_confidence: float = Field(default=0.97, ge=0.0, le=1.0)


class BankTransactionExtraction(BaseModel):
    counterparty_name: str
    reference_code: str | None = None
    remittance_purpose: str = ""
    confidence_score: float = Field(default=0.95, ge=0.0, le=1.0)
