"""Unit Tests for Accounts Payable 3-Way Matching and Dispute Generation."""

from decimal import Decimal

from erp.workflows.accounts_payable.dispute_generator import dispute_generator
from erp.workflows.accounts_payable.tolerance import (
    evaluate_three_way_tolerances,
)


class TestThreeWayMatchingTolerances:
    """Tests tolerance invariants across Invoice, PO, and GRN."""

    def test_exact_match_passes_invariants(self):
        invoice_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]
        po_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]
        grn_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]

        summary = evaluate_three_way_tolerances(invoice_lines, po_lines, grn_lines)
        assert summary.is_fully_matched is True
        assert summary.overall_variance_percentage == Decimal("0.0000")
        assert len(summary.discrepancies) == 0

    def test_acceptable_price_variance_under_one_percent_passes(self):
        # PO price $2.4500, Invoice price $2.4650 -> variance = 0.015 / 2.45 = 0.61% <= 1.0%
        invoice_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4650"}]
        po_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]
        grn_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]

        summary = evaluate_three_way_tolerances(invoice_lines, po_lines, grn_lines)
        assert summary.is_fully_matched is True
        assert summary.overall_variance_percentage < Decimal("1.0000")

    def test_price_variance_over_one_percent_fails_with_discrepancy(self):
        # PO price $2.4500, Invoice price $2.5500 -> variance = 0.10 / 2.45 = 4.08% > 1.0%
        invoice_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.5500"}]
        po_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]
        grn_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]

        summary = evaluate_three_way_tolerances(invoice_lines, po_lines, grn_lines)
        assert summary.is_fully_matched is False
        assert len(summary.discrepancies) == 1
        assert "exceeds allowable 1.00% tolerance" in summary.discrepancies[0]

    def test_quantity_overbilled_fails(self):
        # Invoiced 1,500 units, but warehouse received only 1,000 units on GRN
        invoice_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1500, "unit_price": "2.4500"}]
        po_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1500, "unit_price": "2.4500"}]
        grn_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]

        summary = evaluate_three_way_tolerances(invoice_lines, po_lines, grn_lines)
        assert summary.is_fully_matched is False
        assert any("Quantity violation" in d for d in summary.discrepancies)

    def test_sku_mismatch_fails(self):
        invoice_lines = [{"item_code": "UNKNOWN-SKU-99", "quantity": 100, "unit_price": "10.00"}]
        po_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 100, "unit_price": "10.00"}]
        grn_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 100, "unit_price": "10.00"}]

        summary = evaluate_three_way_tolerances(invoice_lines, po_lines, grn_lines)
        assert summary.is_fully_matched is False
        assert any("SKU mismatch" in d for d in summary.discrepancies)

    def test_dispute_notice_generation(self):
        invoice_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.8000"}]
        po_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]
        grn_lines = [{"item_code": "RAW-RESIN-HDPE", "quantity": 1000, "unit_price": "2.4500"}]

        summary = evaluate_three_way_tolerances(invoice_lines, po_lines, grn_lines)
        notice = dispute_generator.generate_notice(
            invoice_number="INV-2026-DISPUTE-01",
            supplier_code="SUP-POLYMERS",
            supplier_name="Global Polymers Inc.",
            tolerance_summary=summary,
        )

        assert notice.invoice_number == "INV-2026-DISPUTE-01"
        assert "DISCREPANCY NOTICE" in notice.formatted_notice
        assert "DISPUTED" in notice.formatted_notice
