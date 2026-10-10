"""端到端验收：对应 Spec 第十节的验收标准。"""
import inspect
import json
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from pool import rank_cards, validate_card  # noqa: E402
from score import load_anchors, score_candidate  # noqa: E402

V2_ROOT = pathlib.Path(__file__).resolve().parents[1]
ANCHORS = load_anchors(str(V2_ROOT / "config" / "anchors.yaml"))

# 同一批候选的两套数据：完整版（模拟有 MCP）与部分缺失版（模拟人工录入拿不全）
FULL_CANDIDATES = {
    "A-磁性刀架": {
        "monthly_search_volume": 12000, "monthly_sales_units": 900,
        "top10_avg_reviews": 400, "category_avg_rating": 4.3, "fba_seller_count": 8,
        "break_even_acos": 0.35, "net_margin_after_ad": 0.18,
        "moq": 800, "lead_time_days": 30,
        "mandatory_cert_count": 1, "ip_red_flag_count": 0,
    },
    "B-硅胶铲": {
        "monthly_search_volume": 30000, "monthly_sales_units": 2500,
        "top10_avg_reviews": 1800, "category_avg_rating": 4.5, "fba_seller_count": 14,
        "break_even_acos": 0.26, "net_margin_after_ad": 0.11,
        "moq": 3000, "lead_time_days": 45,
        "mandatory_cert_count": 2, "ip_red_flag_count": 0,
    },
}

# 判读 API 不得暴露任何暗示「模式/数据源」的参数——结论依赖模式，应先在这个签名上暴露出来
MODE_LIKE_PARAMS = {"mode", "backend", "source", "source_mode", "data_mode", "manual", "mcp"}


def make_card(cid, name, metrics, source="商机探测器"):
    """构造一张机会卡；source 用于区分数据来源（MCP 采集 / 人工导出）。"""
    return {
        "id": cid, "name": name, "track": "niche", "stage": "priority",
        "evidence": [{"kind": "support", "content": "类目月销成立",
                      "source": source, "period": "2026-09"}],
        "gaps": [{"missing": "退货率", "next_action": "要报表", "owner": "我"}],
        "hard_filter_hits": [], "pain_tags": {}, "metrics": metrics,
    }


class TestDualModeConsistency(unittest.TestCase):
    """Spec 验收标准 #4：同一批候选，两种模式的判读结论必须一致。"""

    def test_reasoning_api_exposes_no_mode_or_source_parameter(self):
        """结构性保证：判读 API 不接收任何「模式/数据源」参数，结论无从依赖模式。"""
        for func in (score_candidate, rank_cards):
            params = set(inspect.signature(func).parameters)
            leaked = params & MODE_LIKE_PARAMS
            self.assertEqual(
                leaked, set(),
                f"{func.__name__} 暴露了模式/数据源参数 {leaked}；"
                f"判读结论不得依赖采集方式。"
            )

    def test_two_pools_differing_only_in_source_rank_identically(self):
        """两池 metrics 完全相同，仅 evidence[].source 不同（MCP 采集 vs 人工导出）。
        排序与总分必须逐字一致——判读绝不能键在数据源上。"""
        mcp_pool = [
            make_card("001", "磁性刀架", FULL_CANDIDATES["A-磁性刀架"], source="Sorftime MCP"),
            make_card("002", "硅胶铲", FULL_CANDIDATES["B-硅胶铲"], source="Sorftime MCP"),
        ]
        manual_pool = [
            make_card("001", "磁性刀架", FULL_CANDIDATES["A-磁性刀架"], source="卖家精灵导出"),
            make_card("002", "硅胶铲", FULL_CANDIDATES["B-硅胶铲"], source="卖家精灵导出"),
        ]

        mcp_ranked = rank_cards(mcp_pool, ANCHORS)
        manual_ranked = rank_cards(manual_pool, ANCHORS)

        mcp_order = [entry["card"]["id"] for entry in mcp_ranked]
        manual_order = [entry["card"]["id"] for entry in manual_ranked]
        self.assertEqual(mcp_order, manual_order)

        mcp_totals = {entry["card"]["id"]: entry["score"]["total"] for entry in mcp_ranked}
        manual_totals = {entry["card"]["id"]: entry["score"]["total"] for entry in manual_ranked}
        self.assertEqual(mcp_totals, manual_totals)

        # 确保这是两个「有分」的池，而不是两边都拒绝出分的空壳——否则相等没有意义
        self.assertTrue(
            all(total is not None for total in mcp_totals.values()),
            f"两池都有卡未出分，双模式对照失去意义：{mcp_totals}",
        )

    def test_partial_data_declares_fewer_dimensions_than_full(self):
        """数据精度不同时，必须如实声明维度数——声明要随数据变，不能装作满维。"""
        partial = {"monthly_search_volume": 12000, "top10_avg_reviews": 400}
        result = score_candidate(partial, ANCHORS)
        full = score_candidate(FULL_CANDIDATES["A-磁性刀架"], ANCHORS)
        self.assertNotEqual(result["declaration"], full["declaration"])
        self.assertIn("本评分基于", result["declaration"])


class TestRefusalBehaviour(unittest.TestCase):
    """Spec 验收标准 #5：缺失权重 >40% 时拒绝出总分。"""

    def test_sparse_candidate_is_refused(self):
        sparse = {"monthly_search_volume": 12000}
        result = score_candidate(sparse, ANCHORS)
        self.assertTrue(result["refused"])
        self.assertIsNone(result["total"])
        self.assertIn("基于", result["declaration"])


class TestUncalibratedFlagging(unittest.TestCase):
    """Spec 验收标准 #6：未校准锚点必须产生 ⚠️。"""

    def test_default_anchors_are_all_uncalibrated(self):
        result = score_candidate(FULL_CANDIDATES["A-磁性刀架"], ANCHORS)
        self.assertTrue(result["uncalibrated_anchors"])


class TestPoolWorkflow(unittest.TestCase):
    """Spec 验收标准 #3：能产出带证据/缺口的机会卡并横向排序。"""

    def _card(self, cid, name, metrics, gaps=None):
        return {
            "id": cid, "name": name, "track": "niche", "stage": "priority",
            "evidence": [{"kind": "support", "content": "类目月销成立",
                          "source": "商机探测器", "period": "2026-09"}],
            "gaps": gaps if gaps is not None else [
                {"missing": "退货率", "next_action": "要报表", "owner": "我"}
            ],
            "hard_filter_hits": [], "pain_tags": {}, "metrics": metrics,
        }

    def test_cards_validate_and_rank(self):
        cards = [
            self._card("001", "磁性刀架", FULL_CANDIDATES["A-磁性刀架"]),
            self._card("002", "硅胶铲", FULL_CANDIDATES["B-硅胶铲"]),
        ]
        for card in cards:
            self.assertEqual(validate_card(card), [])

        ranked = rank_cards(cards, ANCHORS)
        self.assertEqual(len(ranked), 2)
        for entry in ranked:
            self.assertIsNotNone(entry["score"]["total"])

    def test_card_without_gaps_is_rejected(self):
        card = self._card("003", "无缺口卡", {}, gaps=[])
        problems = validate_card(card)
        self.assertTrue(
            any("gaps" in message and "不能为空" in message for message in problems),
            f"空缺口卡应以「gaps 不能为空」被拒，实际问题清单：{problems}",
        )


class TestFixtures(unittest.TestCase):
    """tests/fixtures/ 下的示例候选必须始终是合法机会卡——防止 fixtures 与 schema 漂移。"""

    FIXTURE_DIR = V2_ROOT / "tests" / "fixtures"

    def test_every_fixture_is_a_valid_card(self):
        fixtures = sorted(self.FIXTURE_DIR.glob("*.json"))
        self.assertTrue(fixtures, "tests/fixtures/ 下应至少有一个示例候选")
        for path in fixtures:
            card = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(validate_card(card), [], f"{path.name} 不是合法机会卡")


class TestBreakEvenScriptRunsStandalone(unittest.TestCase):
    """Spec 验收标准 #7：脚本可独立运行。break_even_acos.py 的 CLI 冒烟。"""

    def test_cli_runs_and_reports_break_even_acos(self):
        proc = subprocess.run(
            [sys.executable, "scripts/break_even_acos.py",
             "--price", "25", "--non-ad-costs", "17"],
            cwd=str(V2_ROOT), capture_output=True,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"break_even_acos.py 无法独立运行：\n{proc.stderr.decode('utf-8', 'replace')}",
        )
        payload = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(payload["break_even_acos_pct"], "32.0%")
