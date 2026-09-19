"""Revenue and Commercial Quoting MCP Tool Bindings."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from erp.commercial.pdf_generator import QuotationData, QuoteLineItem, pdf_generator
from erp.commercial.pricing_engine import pricing_engine


async def tool_calculate_landed_margin_price(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for computing landed component costs and enforcing the 22% margin floor."""
    sku = arguments["sku"]
    bom_cost = Decimal(str(arguments["bom_material_cost"]))
    res = pricing_engine.calculate_margin_defended_price(
        sku=sku,
        bom_material_cost=bom_cost,
    )
    return res.model_dump(mode="json")


async def tool_generate_pdf_quote(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """MCP tool for compiling formal commercial sales quotation PDF documents."""
    quote_data = QuotationData(
        quote_number=arguments.get("quote_number", f"Q-AUTO-{uuid.uuid4().hex[:6].upper()}"),
        customer_name=arguments["customer_name"],
        customer_email=arguments.get("customer_email", "procurement@customer.com"),
        quote_date=date.today(),
        valid_until_date=date.today() + timedelta(days=30),
        promised_delivery_date=date.today() + timedelta(days=14),
        items=[
            QuoteLineItem(
                item_code=arguments.get("sku", "FG-ENCLOSURE-IP67"),
                description=arguments.get("description", "IP67 Industrial Enclosure Assembly"),
                quantity=Decimal(str(arguments.get("quantity", 500))),
                unit_price=Decimal(str(arguments.get("unit_price", 48.50))),
                line_total=Decimal(str(arguments.get("quantity", 500)))
                * Decimal(str(arguments.get("unit_price", 48.50))),
            )
        ],
        subtotal=Decimal(str(arguments.get("quantity", 500)))
        * Decimal(str(arguments.get("unit_price", 48.50))),
        total_amount=Decimal(str(arguments.get("quantity", 500)))
        * Decimal(str(arguments.get("unit_price", 48.50))),
    )
    pdf_bytes = pdf_generator.generate_pdf(quote_data)
    return {
        "quote_number": quote_data.quote_number,
        "total_amount": float(quote_data.total_amount),
        "pdf_size_bytes": len(pdf_bytes),
        "status": "COMPILED",
    }
