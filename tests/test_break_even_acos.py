"""单 SKU 利润测算的单元测试。"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from break_even_acos import calc, cash_plan, scenario_view  # noqa: E402


class TestCalc(unittest.TestCase):

    def test_break_even_acos_matches_spec_example(self):
        """Spec 示例：售价 25，除广告外成本 17 → 广告前利润 8 → 盈亏 ACoS 32%。"""
        result = calc(price=25.0, non_ad_costs=17.0)
        self.assertAlmostEqual(result["pre_ad_profit"], 8.0)
        self.assertEqual(result["break_even_acos_pct"], "32.0%")

    def test_ad_cost_reduces_post_ad_profit(self):
        result = calc(price=25.0, non_ad_costs=17.0, ad_cost=3.0)
        self.assertAlmostEqual(result["post_ad_profit"], 5.0)
        self.assertEqual(result["verdict"], "安全")

    def test_acos_above_break_even_is_loss(self):
        result = calc(price=25.0, non_ad_costs=17.0, ad_cost=9.0)
        self.assertEqual(result["verdict"], "亏损")

    def test_fixed_cost_is_deducted_after_ad(self):
        result = calc(price=25.0, non_ad_costs=17.0, ad_cost=3.0, fixed_cost=1.2)
        self.assertAlmostEqual(result["final_profit"], 3.8)

    def test_zero_price_is_rejected(self):
        with self.assertRaises(ValueError):
            calc(price=0.0, non_ad_costs=1.0)

    def test_negative_cost_is_rejected(self):
        with self.assertRaises(ValueError):
            calc(price=25.0, non_ad_costs=-1.0)


class TestScenarioView(unittest.TestCase):

    def test_returns_three_scenarios_in_order(self):
        rows = scenario_view(25.0, 17.0, 4.0, 0.0)
        self.assertEqual([r["scenario"] for r in rows], ["保守", "基准", "乐观"])

    def test_conservative_has_lower_profit_than_optimistic(self):
        rows = scenario_view(25.0, 17.0, 4.0, 0.0)
        conservative, _, optimistic = rows
        self.assertLess(conservative["post_ad_profit"], optimistic["post_ad_profit"])


class TestCashPlan(unittest.TestCase):

    def test_first_batch_peak_includes_one_off_costs(self):
        """首批资金峰值 = 首单货款 + 模具费 + 打样费 + 首轮广告预算。"""
        result = cash_plan(
            first_order_qty=500, landed_unit_cost=6.0,
            mold_fee=20000.0, sample_fee=2000.0, first_ad_budget=8000.0,
            reorder_qty=300,
        )
        self.assertAlmostEqual(result["first_batch_cash_peak"], 500 * 6.0 + 20000.0 + 2000.0 + 8000.0)

    def test_reorder_need_is_units_times_landed_cost(self):
        result = cash_plan(
            first_order_qty=500, landed_unit_cost=6.0,
            mold_fee=0.0, sample_fee=0.0, first_ad_budget=0.0,
            reorder_qty=300,
        )
        self.assertAlmostEqual(result["reorder_cash_need"], 300 * 6.0)


if __name__ == "__main__":
    unittest.main()
