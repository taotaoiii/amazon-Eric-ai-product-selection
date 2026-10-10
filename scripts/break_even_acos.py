#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Break-even ACoS 与单 SKU 利润测算
================================
亚马逊选品 Stage 6（经济测算）的财务核验工具。

用法：
  python break_even_acos.py --price 25 --non-ad-costs 17
  python break_even_acos.py --price 39.99 --non-ad-costs 24.5 --ad-cost 3 --fixed-cost 1.2
  python break_even_acos.py --price 25 --non-ad-costs 17 --scenario
  python break_even_acos.py --price 25 --non-ad-costs 17 --cash-plan \
      --first-order-qty 500 --landed-unit-cost 6 --mold-fee 20000 --first-ad-budget 8000 --reorder-qty 300

注意：本脚本不含任何业务阈值，阈值一律来自 config/anchors.yaml。
"""

import argparse
import json
import sys

# 三情景对广告成本的扰动系数
SCENARIO_FACTORS = [("保守", 1.5), ("基准", 1.0), ("乐观", 0.5)]


def calc(price: float, non_ad_costs: float, ad_cost: float = 0.0,
         fixed_cost: float = 0.0) -> dict:
    """计算单 SKU 的利润结构与 Break-even ACoS。

    price          售价（美元）
    non_ad_costs   除广告外的全部成本合计（采购/包装/报关/头程/关税/佣金/FBA/仓储/退货等）
    ad_cost        每件分摊广告成本
    fixed_cost     固定费用摊销（如开模费摊到单件）
    """
    if price <= 0:
        raise ValueError("price 必须大于 0")
    if non_ad_costs < 0 or ad_cost < 0 or fixed_cost < 0:
        raise ValueError("成本项不能为负")

    pre_ad_profit = price - non_ad_costs
    post_ad_profit = pre_ad_profit - ad_cost
    final_profit = post_ad_profit - fixed_cost

    break_even_acos = pre_ad_profit / price
    current_acos_ratio = ad_cost / price
    margin = break_even_acos - current_acos_ratio

    if margin > 0:
        verdict = "安全"
    elif margin < 0:
        verdict = "亏损"
    else:
        verdict = "临界"

    return {
        "price": round(price, 2),
        "non_ad_costs": round(non_ad_costs, 2),
        "ad_cost_per_unit": round(ad_cost, 2),
        "fixed_cost_per_unit": round(fixed_cost, 2),
        "pre_ad_profit": round(pre_ad_profit, 2),
        "post_ad_profit": round(post_ad_profit, 2),
        "final_profit": round(final_profit, 2),
        "break_even_acos": round(break_even_acos, 4),
        "break_even_acos_pct": f"{break_even_acos * 100:.1f}%",
        "current_acos_pct": f"{current_acos_ratio * 100:.1f}%",
        "acos_margin_pct": f"{margin * 100:.1f}%",
        "verdict": verdict,
        # 缺失项不填零，而是显式列出，供报告层声明
        "unaccounted_costs": [
            "长期仓储费", "移除订单费", "退货处理费", "促销/优惠券", "次品损耗",
        ],
    }


def scenario_view(price: float, non_ad_costs: float, ad_cost: float,
                  fixed_cost: float) -> list:
    """三情景：对广告成本做 ±50% 扰动。"""
    return [
        {"scenario": name, **calc(price, non_ad_costs, ad_cost * factor, fixed_cost)}
        for name, factor in SCENARIO_FACTORS
    ]


def cash_plan(first_order_qty: int, landed_unit_cost: float, mold_fee: float,
              sample_fee: float, first_ad_budget: float, reorder_qty: int) -> dict:
    """资金计划：首批资金峰值 与 补货资金需求。

    首批资金峰值 = 首单货款 + 模具费 + 打样费 + 首轮广告预算
    补货资金需求 = 补货数量 × 到岸单件成本
    """
    for name, value in (
        ("first_order_qty", first_order_qty), ("reorder_qty", reorder_qty),
    ):
        if value < 0:
            raise ValueError(f"{name} 不能为负")
    for name, value in (
        ("landed_unit_cost", landed_unit_cost), ("mold_fee", mold_fee),
        ("sample_fee", sample_fee), ("first_ad_budget", first_ad_budget),
    ):
        if value < 0:
            raise ValueError(f"{name} 不能为负")

    return {
        "first_batch_cash_peak": round(
            first_order_qty * landed_unit_cost + mold_fee + sample_fee + first_ad_budget, 2
        ),
        "reorder_cash_need": round(reorder_qty * landed_unit_cost, 2),
    }


def main():
    # Windows 下 stdout 走管道时默认继承本地编码（如 GBK），打印 ⚠️ 会抛
    # UnicodeEncodeError。统一锁定 UTF-8，保证 agent 通过管道捕获输出时可用。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="亚马逊单 SKU Break-even ACoS 测算")
    parser.add_argument("--price", type=float, required=True, help="售价（美元）")
    parser.add_argument("--non-ad-costs", type=float, required=True, help="除广告外全部成本（美元）")
    parser.add_argument("--ad-cost", type=float, default=0.0, help="每件分摊广告成本（美元）")
    parser.add_argument("--fixed-cost", type=float, default=0.0, help="固定费用摊销（美元/件）")
    parser.add_argument("--scenario", action="store_true", help="输出三情景对比")
    parser.add_argument("--cash-plan", action="store_true", help="输出资金计划（需配套参数）")
    parser.add_argument("--first-order-qty", type=int, default=0, help="首单数量")
    parser.add_argument("--landed-unit-cost", type=float, default=0.0, help="到岸单件成本（美元）")
    parser.add_argument("--mold-fee", type=float, default=0.0, help="模具费（美元）")
    parser.add_argument("--sample-fee", type=float, default=0.0, help="打样费（美元）")
    parser.add_argument("--first-ad-budget", type=float, default=0.0, help="首轮广告预算（美元）")
    parser.add_argument("--reorder-qty", type=int, default=0, help="补货数量")
    args = parser.parse_args()

    if args.cash_plan:
        result = cash_plan(
            args.first_order_qty, args.landed_unit_cost, args.mold_fee,
            args.sample_fee, args.first_ad_budget, args.reorder_qty,
        )
    elif args.scenario:
        result = scenario_view(args.price, args.non_ad_costs, args.ad_cost, args.fixed_cost)
    else:
        result = calc(args.price, args.non_ad_costs, args.ad_cost, args.fixed_cost)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
