"""候选池管理的单元测试。"""
import copy
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from pool import STAGES, load_card, rank_cards, save_card, validate_card  # noqa: E402

VALID_METRICS = {
    "monthly_search_volume": 12000, "monthly_sales_units": 900,
    "top10_avg_reviews": 400, "category_avg_rating": 4.3, "fba_seller_count": 8,
    "break_even_acos": 0.35, "net_margin_after_ad": 0.18,
    "moq": 800, "lead_time_days": 30,
    "mandatory_cert_count": 1, "ip_red_flag_count": 0,
}


def make_card(**overrides):
    card = {
        "id": "007", "name": "磁性刀架", "track": "niche", "stage": "competition",
        "evidence": [{"kind": "support", "content": "类目月销 900", "source": "商机探测器", "period": "2026-09"}],
        "gaps": [{"missing": "退货率未拿到", "next_action": "找运营要退货报表", "owner": "我"}],
        "hard_filter_hits": [],
        "pain_tags": {"frequency": True, "severity": True, "solvability": False, "economics": True},
        "metrics": dict(VALID_METRICS),
    }
    card.update(overrides)
    return card


class TestStages(unittest.TestCase):

    def test_ten_stages_in_order(self):
        self.assertEqual(len(STAGES), 10)
        self.assertEqual(STAGES[0], "bounds")
        self.assertEqual(STAGES[-1], "retro")


class TestValidateCard(unittest.TestCase):

    def test_valid_card_has_no_problems(self):
        self.assertEqual(validate_card(make_card()), [])

    def test_empty_gaps_is_rejected(self):
        """Review Focus #4：缺口区必填，留空不算完成。"""
        problems = validate_card(make_card(gaps=[]))
        self.assertTrue(any("gaps" in p for p in problems))

    def test_gap_without_next_action_is_rejected(self):
        problems = validate_card(make_card(gaps=[{"missing": "退货率", "next_action": "", "owner": "我"}]))
        self.assertTrue(any("next_action" in p for p in problems))

    def test_gap_without_owner_is_rejected(self):
        problems = validate_card(make_card(gaps=[{"missing": "退货率", "next_action": "去问", "owner": ""}]))
        self.assertTrue(any("owner" in p for p in problems))

    def test_unknown_stage_is_rejected(self):
        problems = validate_card(make_card(stage="not-a-stage"))
        self.assertTrue(any("stage" in p for p in problems))

    def test_unknown_track_is_rejected(self):
        problems = validate_card(make_card(track="sideways"))
        self.assertTrue(any("track" in p for p in problems))

    def test_evidence_missing_source_is_rejected(self):
        problems = validate_card(make_card(evidence=[{"kind": "support", "content": "x", "source": "", "period": "2026-09"}]))
        self.assertTrue(any("source" in p for p in problems))

    def test_hard_filter_hit_without_name_is_rejected(self):
        problems = validate_card(make_card(hard_filter_hits=[{"name": ""}]))
        self.assertTrue(any("hard_filter_hits" in p for p in problems))

    def test_hard_filter_hit_without_status_is_rejected(self):
        """未筛 ≠ 通过：status 缺省不等于 pass，卡必须被拒。"""
        problems = validate_card(make_card(hard_filter_hits=[{"name": "return_rate_max"}]))
        self.assertTrue(
            any("hard_filter_hits" in p and "status" in p for p in problems),
            f"缺 status 的硬筛项应被拒，实际问题清单：{problems}",
        )

    def test_hard_filter_hit_with_illegal_status_is_rejected(self):
        """status 只认 hit / pass / unscreened 三值，其它一律拒收。"""
        problems = validate_card(
            make_card(hard_filter_hits=[{"name": "return_rate_max", "status": "passed"}])
        )
        self.assertTrue(
            any("hard_filter_hits" in p and "status" in p for p in problems),
            f"非法 status 应被拒，实际问题清单：{problems}",
        )

    def test_hard_filter_hits_with_three_legal_statuses_pass(self):
        """三值齐全的硬筛记录必须放行，防止校验过度收紧。"""
        problems = validate_card(make_card(hard_filter_hits=[
            {"name": "price_band_usd", "status": "hit"},
            {"name": "top3_brand_share_max", "status": "pass"},
            {"name": "return_rate_max", "status": "unscreened"},
        ]))
        self.assertEqual(problems, [])


class TestSaveLoad(unittest.TestCase):

    def test_roundtrip_preserves_card(self):
        card = make_card()
        with tempfile.TemporaryDirectory() as tmp:
            path = save_card(card, tmp)
            self.assertTrue(path.exists())
            self.assertEqual(load_card(str(path)), card)

    def test_save_rejects_invalid_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save_card(make_card(gaps=[]), tmp)


class TestRankCards(unittest.TestCase):

    def setUp(self):
        import pathlib as _p
        from score import load_anchors
        anchors_path = _p.Path(__file__).resolve().parents[1] / "config" / "anchors.yaml"
        self.anchors = load_anchors(str(anchors_path))

    def test_better_candidate_ranks_first(self):
        good = make_card(id="001", metrics={**VALID_METRICS, "moq": 100, "top10_avg_reviews": 100})
        bad = make_card(id="002", metrics={**VALID_METRICS, "moq": 5000, "top10_avg_reviews": 2000})
        ranked = rank_cards([bad, good], self.anchors)
        self.assertEqual(ranked[0]["card"]["id"], "001")

    def test_refused_cards_rank_last(self):
        full = make_card(id="001")
        empty = make_card(id="002", metrics={})
        ranked = rank_cards([empty, full], self.anchors)
        self.assertEqual(ranked[-1]["card"]["id"], "002")
        self.assertTrue(ranked[-1]["score"]["refused"])

    def test_ranking_does_not_mutate_input_cards(self):
        cards = [make_card(id="001"), make_card(id="002")]
        snapshot = copy.deepcopy(cards)
        rank_cards(cards, self.anchors)
        self.assertEqual(cards, snapshot)


class TestCliStdoutEncoding(unittest.TestCase):
    """GBK 等非 UTF-8 环境下，stdout 走管道时打印 ⚠️ 不得崩溃。"""

    def test_warning_survives_non_utf8_piped_stdout(self):
        v2_root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            card = make_card()
            (pathlib.Path(tmp) / f"{card['id']}.json").write_text(
                json.dumps(card, ensure_ascii=False), encoding="utf-8"
            )
            env = {**os.environ, "PYTHONIOENCODING": "gbk"}
            proc = subprocess.run(
                [sys.executable, "scripts/pool.py", "rank",
                 "--pool", tmp, "--anchors", "config/anchors.yaml"],
                cwd=str(v2_root), capture_output=True, env=env,
            )
        self.assertEqual(
            proc.returncode, 0,
            f"pool.py rank 在非 UTF-8 管道下崩溃：\n{proc.stderr.decode('utf-8', 'replace')}",
        )
        self.assertIn("⚠️", proc.stdout.decode("utf-8"))


class TestAddCli(unittest.TestCase):

    def test_add_writes_valid_card(self):
        v2_root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            card_path = pathlib.Path(tmp) / "in.json"
            card_path.write_text(
                json.dumps(make_card(), ensure_ascii=False), encoding="utf-8"
            )
            pool_dir = pathlib.Path(tmp) / "pool"
            proc = subprocess.run(
                [sys.executable, "scripts/pool.py", "add",
                 "--pool", str(pool_dir), "--card", str(card_path)],
                cwd=str(v2_root), capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            self.assertTrue((pool_dir / "007.json").exists())
            self.assertIn("已入库", proc.stdout.decode("utf-8"))

    def test_add_rejects_invalid_card(self):
        v2_root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            card_path = pathlib.Path(tmp) / "in.json"
            card_path.write_text(
                json.dumps(make_card(gaps=[]), ensure_ascii=False), encoding="utf-8"
            )
            pool_dir = pathlib.Path(tmp) / "pool"
            proc = subprocess.run(
                [sys.executable, "scripts/pool.py", "add",
                 "--pool", str(pool_dir), "--card", str(card_path)],
                cwd=str(v2_root), capture_output=True,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertFalse((pool_dir / "007.json").exists())


if __name__ == "__main__":
    unittest.main()
