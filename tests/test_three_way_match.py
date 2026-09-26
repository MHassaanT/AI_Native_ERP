"""Unit Tests for Accounts Payable 3-Way Matching and Dispute Generation."""

from decimal import Decimal

import pytest

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
        assert summary.quantity_variance_percentage > Decimal("0.0000")
        assert summary.price_variance_percentage == Decimal("0.0000")

    def test_missing_grn_zero_received_evaluates_correctly(self):
        # Invoiced 100 units @ $220, PO has 100 units @ $220, but GRN received is 0
        invoice_lines = [{"item_code": "RAW-TITANIUM", "quantity": 100, "unit_price": "220.0000"}]
        po_lines = [{"item_code": "RAW-TITANIUM", "quantity": 100, "unit_price": "220.0000"}]
        grn_lines = []

        summary = evaluate_three_way_tolerances(invoice_lines, po_lines, grn_lines)
        assert summary.is_fully_matched is False
        assert any("Quantity violation" in d for d in summary.discrepancies)
        assert summary.quantity_variance_percentage == Decimal("100.0000")
        assert summary.price_variance_percentage == Decimal("0.0000")

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
        assert notice.dispute_reason != ""
        assert notice.action_recommended != ""
        assert "exceeds allowable" in notice.dispute_reason


class TestThreeWayMatcherCeilingAndApproval:
    """Verifies that high-value invoices (> $25k Tier 3) are STAGED rather than crashing, and post when human approved."""

    @pytest.mark.asyncio
    async def test_high_value_invoice_staged_when_unapproved(self):
        import uuid
        from unittest.mock import AsyncMock, MagicMock, patch
        from erp.ledger.exceptions import AutonomyCeilingExceeded
        from erp.workflows.accounts_payable.three_way_matcher import three_way_matcher

        tenant_id = uuid.uuid4()
        invoice_id = uuid.uuid4()
        po_id = uuid.uuid4()
        grn_id = uuid.uuid4()
        supplier_id = uuid.uuid4()

        invoice = MagicMock()
        invoice.tenant_id = tenant_id
        invoice.invoice_id = invoice_id
        invoice.invoice_number = "INV-60K"
        invoice.matching_status = "PENDING"
        invoice.po_id = po_id
        invoice.grn_id = grn_id
        invoice.supplier_id = supplier_id
        invoice.total_amount = Decimal("60000.0000")
        invoice.currency = "USD"
        invoice.variance_percentage = Decimal("0.0000")
        invoice.dispute_reason = None

        supplier = MagicMock()
        supplier.supplier_code = "SUP-TITAN"
        supplier.supplier_name = "Titan Supply"

        po = MagicMock()
        po.po_number = "PO-2026-60K"

        po_item = MagicMock()
        po_item.quantity = Decimal("100.0000")
        po_item.unit_price = Decimal("600.0000")

        grn = MagicMock()
        grn.grn_number = "GRN-2026-60K"

        grn_item = MagicMock()
        grn_item.quantity_received = Decimal("100.0000")
        grn_item.unit_price = Decimal("600.0000")

        inv_item = MagicMock()
        inv_item.item_code = "RAW-TITANIUM"
        inv_item.quantity = Decimal("100.0000")
        inv_item.unit_price = Decimal("600.0000")

        session = AsyncMock()

        def mock_execute(stmt):
            res = MagicMock()
            res.scalar_one_or_none.return_value = invoice
            res.scalar_one.return_value = po
            res.all.return_value = [(po_item, "RAW-TITANIUM")]
            res_scalars = MagicMock()
            res_scalars.first.return_value = grn
            res_scalars.all.return_value = [inv_item]
            res.scalars.return_value = res_scalars
            return res

        session.execute = AsyncMock(side_effect=[
            # 1: invoice
            MagicMock(scalar_one_or_none=MagicMock(return_value=invoice)),
            # 2: supplier
            MagicMock(scalar_one_or_none=MagicMock(return_value=supplier)),
            # 3: PO
            MagicMock(scalar_one=MagicMock(return_value=po)),
            # 4: PO items
            MagicMock(all=MagicMock(return_value=[(po_item, "RAW-TITANIUM")])),
            # 5: GRN
            MagicMock(scalar_one=MagicMock(return_value=grn)),
            # 6: GRN items
            MagicMock(all=MagicMock(return_value=[(grn_item, "RAW-TITANIUM")])),
            # 7: Invoice items
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[inv_item])))),
        ])

        with patch("erp.workflows.accounts_payable.three_way_matcher.ledger_engine.commit_transaction") as mock_commit:
            mock_commit.side_effect = AutonomyCeilingExceeded(
                total_amount=Decimal("60000.0000"),
                ceiling_amount=Decimal("25000.0000"),
                tier="TIER_3",
            )

            result = await three_way_matcher.match_invoice(
                session=session,
                tenant_id=tenant_id,
                invoice_id=invoice_id,
                po_id=po_id,
                grn_id=grn_id,
                human_approved=False,
            )

            assert result.is_matched is True
            assert result.matching_status == "STAGED"
            assert invoice.matching_status == "STAGED"
            assert "Tier 3 Financial Ceiling Exceeded" in invoice.dispute_reason
            assert result.ledger_result is None

    @pytest.mark.asyncio
    async def test_high_value_invoice_commits_when_human_approved(self):
        import uuid
        from unittest.mock import AsyncMock, MagicMock, patch
        from erp.ledger.engine import LedgerCommitResult
        from erp.workflows.accounts_payable.three_way_matcher import three_way_matcher

        tenant_id = uuid.uuid4()
        invoice_id = uuid.uuid4()
        po_id = uuid.uuid4()
        grn_id = uuid.uuid4()
        supplier_id = uuid.uuid4()

        invoice = MagicMock()
        invoice.tenant_id = tenant_id
        invoice.invoice_id = invoice_id
        invoice.invoice_number = "INV-60K"
        invoice.matching_status = "STAGED"
        invoice.po_id = po_id
        invoice.grn_id = grn_id
        invoice.supplier_id = supplier_id
        invoice.total_amount = Decimal("60000.0000")
        invoice.currency = "USD"
        invoice.variance_percentage = Decimal("0.0000")
        invoice.dispute_reason = "Previously staged"

        supplier = MagicMock()
        supplier.supplier_code = "SUP-TITAN"
        supplier.supplier_name = "Titan Supply"

        po = MagicMock()
        po.po_number = "PO-2026-60K"

        po_item = MagicMock()
        po_item.quantity = Decimal("100.0000")
        po_item.unit_price = Decimal("600.0000")

        grn = MagicMock()
        grn.grn_number = "GRN-2026-60K"

        grn_item = MagicMock()
        grn_item.quantity_received = Decimal("100.0000")
        grn_item.unit_price = Decimal("600.0000")

        inv_item = MagicMock()
        inv_item.item_code = "RAW-TITANIUM"
        inv_item.quantity = Decimal("100.0000")
        inv_item.unit_price = Decimal("600.0000")

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=invoice)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=supplier)),
            MagicMock(scalar_one=MagicMock(return_value=po)),
            MagicMock(all=MagicMock(return_value=[(po_item, "RAW-TITANIUM")])),
            MagicMock(scalar_one=MagicMock(return_value=grn)),
            MagicMock(all=MagicMock(return_value=[(grn_item, "RAW-TITANIUM")])),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[inv_item])))),
        ])

        with patch("erp.workflows.accounts_payable.three_way_matcher.ledger_engine.commit_transaction") as mock_commit:
            from datetime import date
            from erp.ledger.ceilings import AutonomyTier, CeilingEvaluationResult

            mock_commit.return_value = LedgerCommitResult(
                transaction_id=uuid.uuid4(),
                tenant_id=tenant_id,
                posting_date=date.today(),
                total_volume=Decimal("60000.0000"),
                lines_committed=2,
                autonomy_evaluation=CeilingEvaluationResult(
                    tier=AutonomyTier.TIER_3,
                    total_amount=Decimal("60000.0000"),
                    requires_human_approval=True,
                    requires_notification=True,
                    is_approved=True,
                ),
                outbox_event_id=uuid.uuid4(),
            )

            result = await three_way_matcher.match_invoice(
                session=session,
                tenant_id=tenant_id,
                invoice_id=invoice_id,
                po_id=po_id,
                grn_id=grn_id,
                human_approved=True,
            )

            assert result.is_matched is True
            assert result.matching_status == "MATCHED"
            assert invoice.matching_status == "MATCHED"
            assert invoice.dispute_reason is None
            assert result.ledger_result is not None
            mock_commit.assert_called_once()
            call_proposal = mock_commit.call_args[1]["proposal"]
            assert call_proposal.human_in_the_loop_approved is True

