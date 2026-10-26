from decimal import Decimal
from types import SimpleNamespace

from erp.workflows.accounts_payable.three_way_matcher import build_invoice_ledger_lines


def _totals(entries):
    return (
        sum((entry.debit_amount for entry in entries), Decimal("0")),
        sum((entry.credit_amount for entry in entries), Decimal("0")),
    )


def test_inclusive_recoverable_tax_is_split_from_inventory_and_balanced():
    invoice = SimpleNamespace(
        currency="USD", total_amount=Decimal("110.0000"),
        tax_snapshot=[{"account_head": "2200-INPUT-VAT", "amount": "10.0000", "included_in_rate": True, "add_deduct": "ADD", "consider_for_valuation": False}],
    )
    entries = build_invoice_ledger_lines(invoice)
    assert [(row.account_code, row.debit_amount, row.credit_amount) for row in entries] == [
        ("1300-RAW-MATERIALS", Decimal("100.0000"), Decimal("0.0000")),
        ("2200-INPUT-VAT", Decimal("10.0000"), Decimal("0")),
        ("2100-AP-VENDORS", Decimal("0.0000"), Decimal("110.0000")),
    ]
    assert _totals(entries) == (Decimal("110.0000"), Decimal("110.0000"))


def test_deducted_tax_posts_to_liability_without_reducing_expense():
    invoice = SimpleNamespace(
        currency="USD", total_amount=Decimal("90.0000"),
        tax_snapshot=[{"account_head": "2250-WITHHOLDING", "amount": "10.0000", "included_in_rate": False, "add_deduct": "DEDUCT", "consider_for_valuation": False}],
    )
    entries = build_invoice_ledger_lines(invoice)
    assert _totals(entries) == (Decimal("100.0000"), Decimal("100.0000"))
    assert entries[1].account_code == "2250-WITHHOLDING"
    assert entries[1].credit_amount == Decimal("10.0000")


def test_valuation_tax_is_capitalized_into_inventory():
    invoice = SimpleNamespace(
        currency="USD", total_amount=Decimal("110.0000"),
        tax_snapshot=[{"account_head": "2200-INPUT-VAT", "amount": "10.0000", "included_in_rate": False, "add_deduct": "ADD", "consider_for_valuation": True}],
    )
    entries = build_invoice_ledger_lines(invoice)
    assert len(entries) == 2
    assert entries[0].account_code == "1300-RAW-MATERIALS"
    assert entries[0].debit_amount == Decimal("110.0000")
    assert _totals(entries) == (Decimal("110.0000"), Decimal("110.0000"))
