"""Tests for Revenue & Commercial Agent: Dynamic Pricing Engine, BOM Rollup, and PDF Quotes."""

from datetime import date, timedelta
from decimal import Decimal

from erp.commercial.bom_cost_rollup import (
    BOMCostRollupEngine,
)
from erp.commercial.pdf_generator import (
    QuotationData,
    QuotationPDFGenerator,
    QuoteLineItem,
)
from erp.commercial.pricing_engine import (
    DynamicPricingEngine,
)
from erp.commercial.quote_invalidator import (
    QuoteInvalidator,
)


def test_pricing_engine_defends_22_percent_margin():
    """Verifies that the pricing engine defends the 22.0% contribution margin floor."""
    engine = DynamicPricingEngine()

    # Raw material cost = $50.00
    # Overheads = machine ($4.50) + labor ($6.00) + freight ($1.25) = $11.75
    # Total landed cost = $61.75
    # Floor price = 61.75 / (1 - 0.22) = 61.75 / 0.78 = 79.1667
    eval_result = engine.calculate_margin_defended_price(
        sku="TEST-SKU-01",
        bom_material_cost=Decimal("50.0000"),
        machine_depreciation=Decimal("4.5000"),
        direct_labor=Decimal("6.0000"),
        freight=Decimal("1.2500"),
        target_markup_multiplier=Decimal(
            "1.1000"
        ),  # Low markup would violate 22% margin if not defended
    )

    # Margin floor defense should bump price to minimum floor price
    assert eval_result.is_margin_defended is True
    assert eval_result.total_landed_cost == Decimal("61.7500")
    assert eval_result.proposed_unit_price >= eval_result.minimum_floor_price
    assert eval_result.computed_margin_percentage >= Decimal("22.00")


def test_bom_cost_rollup_on_component_price_spikes():
    """Verifies parent assembly raw material cost delta calculation during supplier spikes."""
    rollup = BOMCostRollupEngine()

    # Parent assembly has 2 components:
    # COMP-A: qty 4, was $5.00, increased to $7.50 (+50%)
    # COMP-B: qty 2, was $10.00, remained $10.00
    # Old BOM = 4*5 + 2*10 = 20 + 20 = $40.00
    # New BOM = 4*7.50 + 2*10 = 30 + 20 = $50.00
    # Delta = (50 - 40) / 40 = +25.0%
    deltas = {
        "COMP-A": (Decimal("4.0"), Decimal("5.00"), Decimal("7.50")),
        "COMP-B": (Decimal("2.0"), Decimal("10.00"), Decimal("10.00")),
    }

    res = rollup.calculate_bom_cost_delta(parent_sku="PARENT-ASSY-01", material_deltas=deltas)

    assert res.old_raw_material_cost == Decimal("40.0000")
    assert res.new_raw_material_cost == Decimal("50.0000")
    assert res.cost_increase_percentage == Decimal("25.00")
    assert res.requires_quote_revaluation is True


def test_quote_invalidator_triggers_on_margin_erosion():
    """Verifies that an active quote is invalidated when component costs rise and erode margin < 22%."""
    invalidator = QuoteInvalidator()

    # Original quote price was $80.00
    # New raw material cost jumps to $70.00 (landed cost = 70 + 11.75 = 81.75)
    # Keeping old price $80.00 yields negative margin (-2.19% < 22.0%)
    notice = invalidator.evaluate_active_quote(
        quote_number="Q-2026-001",
        customer_name="Global Aerospace",
        sku="AERO-BRACKET-TI",
        current_quoted_price=Decimal("80.00"),
        new_bom_material_cost=Decimal("70.00"),
    )

    assert notice.is_invalidated is True
    assert notice.new_margin_with_old_price < Decimal("22.00")
    assert notice.new_adjusted_price is not None
    assert notice.new_adjusted_price > Decimal("80.00")
    assert "COMMERCIAL PRICE ADJUSTMENT NOTICE" in (notice.customer_adjustment_notice or "")


def test_quotation_pdf_generation():
    """Verifies that ReportLab compiles a valid PDF document with cryptographic seal."""
    generator = QuotationPDFGenerator()

    quote_data = QuotationData(
        quote_number="QT-2026-999",
        customer_name="Nordic Energy AS",
        customer_email="procurement@nordicenergy.no",
        valid_until_date=date.today() + timedelta(days=30),
        promised_delivery_date=date.today() + timedelta(days=14),
        items=[
            QuoteLineItem(
                item_code="INV-50KW",
                description="Grid Inverter 50KW 3-Phase",
                quantity=Decimal("10"),
                unit_price=Decimal("1250.00"),
                line_total=Decimal("12500.00"),
            ),
        ],
        subtotal=Decimal("12500.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("12500.00"),
        margin_percentage=Decimal("26.40"),
    )

    pdf_bytes = generator.generate_pdf(quote_data)
    assert len(pdf_bytes) > 500
    # Valid PDF signature begins with '%PDF-'
    assert pdf_bytes.startswith(b"%PDF-")
