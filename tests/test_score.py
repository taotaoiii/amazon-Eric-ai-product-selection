"""评分规则层的单元测试：归一化、缺失数据规则、熔断、未校准标记。"""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from score import load_anchors, normalize, score_candidate  # noqa: E402

ANCHORS_PATH = pathlib.Path(__file__).resolve().parents[1] / "config" / "anchors.yaml"
ANCHORS = load_anchors(str(ANCHORS_PATH))


class TestNormalize(unittest.TestCase):

    def test_higher_is_better_at_upper_anchor_scores_one(self):
        self.assertAlmostEqual(normalize(100, 0, 100, "none", "higher"), 1.0)

    def test_higher_is_better_at_lower_anchor_scores_zero(self):
        self.assertAlmostEqual(normalize(0, 0, 100, "none", "higher"), 0.0)

    def test_lower_is_better_at_lower_anchor_scores_one(self):
        """MOQ 越低越好：区间下界应得满分。"""
        self.assertAlmostEqual(normalize(100, 100, 5000, "none", "lower"), 1.0)

    def test_lower_is_better_at_upper_anchor_scores_zero(self):
        self.assertAlmostEqual(normalize(5000, 100, 5000, "none", "lower"), 0.0)

    def test_out_of_range_is_clamped(self):
        self.assertAlmostEqual(normalize(999999, 0, 100, "none", "higher"), 1.0)
        self.assertAlmostEqual(normalize(-5, 0, 100, "none", "higher"), 0.0)

    def test_log_transform_compresses_large_values(self):
        """log 变换下，100→1000 与 1000→10000 的得分增量应接近。"""
        first = normalize(1000, 100, 10000, "log", "higher") - normalize(100, 100, 10000, "log", "higher")
        second = normalize(10000, 100, 10000, "log", "higher") - normalize(1000, 100, 10000, "log", "higher")
        self.assertAlmostEqual(first, second, places=6)

    def test_zero_value_with_log_transform_does_not_crash(self):
        self.assertIsInstance(normalize(0, 0, 100, "log", "higher"), float)

    def test_log_anchor_collapsing_after_transform_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize(0.5, 0.5, 1.0, "log", "higher")


class TestScoreCandidate(unittest.TestCase):

    def _full_candidate(self):
        return {
            "monthly_search_volume": 12000,
            "monthly_sales_units": 900,
            "top10_avg_reviews": 400,
            "category_avg_rating": 4.3,
            "fba_seller_count": 8,
            "break_even_acos": 0.35,
            "net_margin_after_ad": 0.18,
            "moq": 800,
            "lead_time_days": 30,
            "mandatory_cert_count": 1,
            "ip_red_flag_count": 0,
        }

    def test_full_data_produces_total_and_full_declaration(self):
        result = score_candidate(self._full_candidate(), ANCHORS)
        self.assertFalse(result["refused"])
        self.assertIsNotNone(result["total"])
        self.assertEqual(result["declaration"], "本评分基于 5/5 维")
        self.assertAlmostEqual(result["missing_weight_pct"], 0.0)

    def test_total_is_between_zero_and_hundred(self):
        result = score_candidate(self._full_candidate(), ANCHORS)
        self.assertGreaterEqual(result["total"], 0.0)
        self.assertLessEqual(result["total"], 100.0)

    def test_low_moq_scores_higher_than_high_moq_on_supply(self):
        """Review Focus #2：越小越好的指标不能算反。"""
        low = score_candidate({**self._full_candidate(), "moq": 100}, ANCHORS)
        high = score_candidate({**self._full_candidate(), "moq": 5000}, ANCHORS)
        self.assertGreater(low["dimensions"]["supply"]["score"],
                           high["dimensions"]["supply"]["score"])

    def test_low_rating_scores_higher_than_high_rating_on_competition(self):
        """类目平均评分越低 = 差异化空间越大 = 竞争维度得分越高。"""
        low = score_candidate({**self._full_candidate(), "category_avg_rating": 4.0}, ANCHORS)
        high = score_candidate({**self._full_candidate(), "category_avg_rating": 4.6}, ANCHORS)
        self.assertGreater(low["dimensions"]["competition"]["score"],
                           high["dimensions"]["competition"]["score"])

    def test_missing_dimension_is_skipped_and_renormalized(self):
        """缺掉 compliance（权重 10%）→ 丢弃该维，分母重归一化，总分仍可出。"""
        candidate = self._full_candidate()
        del candidate["mandatory_cert_count"]
        del candidate["ip_red_flag_count"]
        result = score_candidate(candidate, ANCHORS)
        self.assertTrue(result["dimensions"]["compliance"]["skipped"])
        self.assertFalse(result["refused"])
        self.assertEqual(result["declaration"], "本评分基于 4/5 维")
        self.assertAlmostEqual(result["missing_weight_pct"], 0.10)

    def test_missing_dimension_renormalizes_denominator_pins_absolute_total(self):
        """钉死"分母只计实际算得出的维度"这条规则——用绝对总分，不靠排序或声明。

        手算推导（锚点见 config/anchors.yaml）：
        候选故意只给 demand / competition / supply / compliance 四维，
        profit 整维缺失（权重 20% ≤ 熔断线，仍出分）。
        每个给出的值都取其锚点端点，故单指标得分非 0 即 1：
          demand      : 搜索量=上界→1.0，销量=下界→0.0                 → 维分 (1.0+0.0)/2 = 0.5
          competition : 评论数=下界→1.0，评分=上界→0.0，FBA 卖家=下界→1.0 → 维分 2/3
          supply      : MOQ=下界→1.0，生产周期=下界→1.0               → 维分 1.0
          compliance  : 认证项数=下界→1.0，IP 红牌=下界→1.0            → 维分 1.0
        加权和 = 0.5*25 + (2/3)*25 + 1.0*20 + 1.0*10 = 59.1666667
        分母只计算得出的维度权重 = 25+25+20+10 = 80（不是全部五维的 100）
        总分 = 59.1666667 / 80 * 100 = 73.9583… → 取 1 位小数 = 74.0

        若把公式误写成 weighted_sum / total_weight * 100（分母用 100），
        结果会变成 59.1666667 / 100 * 100 = 59.2，本断言随即失败。
        """
        partial = {
            "monthly_search_volume": 50000, "monthly_sales_units": 300,   # demand
            "top10_avg_reviews": 100, "category_avg_rating": 4.6,          # competition
            "fba_seller_count": 3,
            "moq": 100, "lead_time_days": 15,                              # supply
            "mandatory_cert_count": 0, "ip_red_flag_count": 0,             # compliance
            # profit 整维缺失
        }
        result = score_candidate(partial, ANCHORS)
        self.assertFalse(result["refused"])
        self.assertEqual(result["declaration"], "本评分基于 4/5 维")
        self.assertAlmostEqual(result["missing_weight_pct"], 0.20)
        self.assertEqual(result["total"], 74.0)

    def test_missing_weight_exactly_40_percent_does_not_refuse(self):
        """Review Focus #3：边界值 40% 不熔断，只有严格大于才熔断。"""
        candidate = self._full_candidate()
        for key in ("moq", "lead_time_days",                       # supply 20%
                    "break_even_acos", "net_margin_after_ad"):      # profit 20%
            del candidate[key]
        result = score_candidate(candidate, ANCHORS)
        self.assertAlmostEqual(result["missing_weight_pct"], 0.40)
        self.assertFalse(result["refused"], "缺失权重恰好 40% 不应熔断")
        self.assertIsNotNone(result["total"])

    def test_missing_weight_above_40_percent_refuses_total(self):
        candidate = self._full_candidate()
        for key in ("moq", "lead_time_days",                       # supply 20%
                    "break_even_acos", "net_margin_after_ad",       # profit 20%
                    "mandatory_cert_count", "ip_red_flag_count"):   # compliance 10%
            del candidate[key]
        result = score_candidate(candidate, ANCHORS)
        self.assertGreater(result["missing_weight_pct"], 0.40)
        self.assertTrue(result["refused"])
        self.assertIsNone(result["total"])
        self.assertIn("缺失", result["refuse_reason"])

    def test_refused_result_still_reports_computable_dimensions(self):
        candidate = self._full_candidate()
        for key in ("moq", "lead_time_days", "break_even_acos",
                    "net_margin_after_ad", "mandatory_cert_count", "ip_red_flag_count"):
            del candidate[key]
        result = score_candidate(candidate, ANCHORS)
        self.assertIsNotNone(result["dimensions"]["demand"]["score"])
        self.assertIsNotNone(result["dimensions"]["competition"]["score"])

    def test_uncalibrated_anchors_are_reported(self):
        """Review Focus #5：未校准锚点必须被显式列出，供报告打 ⚠️ 标。"""
        result = score_candidate(self._full_candidate(), ANCHORS)
        self.assertTrue(result["uncalibrated_anchors"])
        self.assertTrue(all("." in path for path in result["uncalibrated_anchors"]))

    def test_no_uncalibrated_anchors_when_all_calibrated(self):
        import copy
        anchors = copy.deepcopy(ANCHORS)
        for dim in anchors["scoring"]["dimensions"].values():
            for metric in dim["metrics"].values():
                metric["calibrated"] = True
        anchors["scoring"]["refuse_total_above_missing_weight"]["calibrated"] = True
        result = score_candidate(self._full_candidate(), anchors)
        self.assertEqual(result["uncalibrated_anchors"], [])

    def test_empty_candidate_refuses_and_declares_zero_dimensions(self):
        result = score_candidate({}, ANCHORS)
        self.assertTrue(result["refused"])
        self.assertIsNone(result["total"])
        self.assertEqual(result["declaration"], "本评分基于 0/5 维")


class TestLoadAnchors(unittest.TestCase):

    def test_loads_from_path(self):
        data = load_anchors(str(ANCHORS_PATH))
        self.assertIn("scoring", data)

    def test_missing_file_raises_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            load_anchors("does/not/exist.yaml")


class TestCliStdoutEncoding(unittest.TestCase):
    """GBK 等非 UTF-8 环境下，stdout 走管道时打印 ⚠️ 不得崩溃。"""

    def test_warning_survives_non_utf8_piped_stdout(self):
        import json as _json
        import os
        import subprocess

        v2_root = pathlib.Path(__file__).resolve().parents[1]
        candidate = {
            "monthly_search_volume": 12000, "monthly_sales_units": 900,
            "top10_avg_reviews": 400, "category_avg_rating": 4.3, "fba_seller_count": 8,
            "break_even_acos": 0.35, "net_margin_after_ad": 0.18,
            "moq": 800, "lead_time_days": 30,
            "mandatory_cert_count": 1, "ip_red_flag_count": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            input_path = pathlib.Path(tmp) / "cand.json"
            input_path.write_text(_json.dumps(candidate), encoding="utf-8")
            env = {**os.environ, "PYTHONIOENCODING": "gbk"}
            proc = subprocess.run(
                [sys.executable, "scripts/score.py",
                 "--anchors", "config/anchors.yaml", "--input", str(input_path)],
                cwd=str(v2_root), capture_output=True, env=env,
            )
        self.assertEqual(
            proc.returncode, 0,
            f"score.py 在非 UTF-8 管道下崩溃：\n{proc.stderr.decode('utf-8', 'replace')}",
        )
        self.assertIn("⚠️", proc.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
