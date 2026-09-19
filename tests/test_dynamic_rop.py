"""Unit Tests for Dynamic Reorder Point (ROP), EOQ, and Supplier Scorecards."""

from decimal import Decimal

from erp.supply_chain.eoq_calculator import eoq_calculator
from erp.supply_chain.rop_engine import Z_99_PERCENT, rop_engine
from erp.supply_chain.supplier_scorecard import supplier_scorecard


class TestDynamicROPAndReplenishment:
    """Tests stochastic inventory replenishment formulas."""

    def test_z_score_equals_99_percent_availability(self):
        assert Z_99_PERCENT == Decimal("2.33")

    def test_rop_calculation_stochastic_math(self):
        """Validates: ROP = (mu_D * mu_L) + 2.33 * sqrt(mu_L * sigma_D^2 + mu_D^2 * sigma_L^2).

        Given:
          mu_D = 100, sigma_D = 20
          mu_L = 9, sigma_L = 2
          lead_time_demand = 100 * 9 = 900
          variance = 9 * (20^2) + (100^2) * (2^2) = 9 * 400 + 10000 * 4 = 3600 + 40000 = 43600
          std_dev_ltd = sqrt(43600) ≈ 208.80613
          safety_stock = 2.33 * 208.80613 ≈ 486.5183
          rop = 900 + 486.5183 = 1386.5183
        """
        eval_res = rop_engine.calculate_rop(
            item_code="RAW-RESIN-HDPE",
            mu_d=Decimal("100.0000"),
            sigma_d=Decimal("20.0000"),
            mu_l=Decimal("9.0000"),
            sigma_l=Decimal("2.0000"),
        )

        assert eval_res.lead_time_demand == Decimal("900.0000")
        assert Decimal("486.50") <= eval_res.safety_stock <= Decimal("486.55")
        assert Decimal("1386.50") <= eval_res.reorder_point <= Decimal("1386.55")

    def test_eoq_calculation_formula(self):
        """Validates: EOQ = sqrt( (2 * D * S) / H ).

        Given:
          Annual Demand D = 36,500 units
          Order Cost S = $150.00
          Holding Cost H = $0.85/unit/year
          EOQ = sqrt( (2 * 36500 * 150) / 0.85 ) = sqrt( 10,950,000 / 0.85 ) ≈ sqrt(12,882,352.94) ≈ 3589.19
          Rounded to 100-unit multiple = 3600 units
        """
        eoq_res = eoq_calculator.calculate_eoq(
            item_code="RAW-RESIN-HDPE",
            annual_demand=Decimal("36500.0000"),
            order_cost=Decimal("150.00"),
            holding_cost_per_unit=Decimal("0.85"),
            batch_multiple=Decimal("100.00"),
        )

        assert Decimal("3589.00") <= eoq_res.economic_order_quantity <= Decimal("3590.00")
        assert eoq_res.recommended_order_quantity == Decimal("3600.00")

    def test_supplier_lead_time_drift_expands_buffer(self):
        # Baseline variance: 4.0 days^2, Current variance: 5.0 days^2 -> 25% increase (> 15%)
        eval_res = supplier_scorecard.evaluate_lead_time_drift(
            supplier_code="SUP-POLYMERS",
            baseline_variance=Decimal("4.00"),
            current_variance=Decimal("5.00"),
        )

        assert eval_res.triggers_buffer_expansion is True
        assert eval_res.variance_growth_percentage == Decimal("25.00")
        assert eval_res.safety_stock_expansion_multiplier == Decimal("1.2500")

    def test_supplier_stable_lead_time_does_not_expand(self):
        # Baseline variance: 4.0 days^2, Current variance: 4.4 days^2 -> 10% increase (<= 15%)
        eval_res = supplier_scorecard.evaluate_lead_time_drift(
            supplier_code="SUP-POLYMERS",
            baseline_variance=Decimal("4.00"),
            current_variance=Decimal("4.40"),
        )

        assert eval_res.triggers_buffer_expansion is False
        assert eval_res.safety_stock_expansion_multiplier == Decimal("1.0000")
