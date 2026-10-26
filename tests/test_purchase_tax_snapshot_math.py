from decimal import Decimal

from erp.workflows.commercial.calculation_service import total_from_tax_snapshot


def test_purchase_total_uses_snapshot_direction_and_inclusive_flag():
    total = total_from_tax_snapshot(
        Decimal("110.0000"),
        [
            {"amount": "10.0000", "included_in_rate": True, "add_deduct": "ADD"},
            {"amount": "5.0000", "included_in_rate": False, "add_deduct": "ADD"},
            {"amount": "2.0000", "included_in_rate": False, "add_deduct": "DEDUCT"},
        ],
    )
    assert total == Decimal("113.0000")


def test_purchase_total_without_tax_rows_is_taxable_base():
    assert total_from_tax_snapshot(Decimal("75.2500"), None) == Decimal("75.2500")
