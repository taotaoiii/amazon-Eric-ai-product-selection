"""锚点完整性测试：保证 anchors.yaml 里每条锚点都带依据和校准标记。"""
import pathlib
import unittest

import yaml

ANCHORS_PATH = pathlib.Path(__file__).resolve().parents[1] / "config" / "anchors.yaml"
REQUIRED_FIELDS = ("value", "basis", "calibrated", "last_reviewed")


def load_anchors():
    with ANCHORS_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def iter_anchor_nodes(node, prefix=""):
    """递归产出 (键路径, 节点) —— 只产出“叶子锚点”（含 basis 字段的 dict）。"""
    if isinstance(node, dict):
        if "basis" in node:
            yield prefix, node
            return
        for key, value in node.items():
            yield from iter_anchor_nodes(value, f"{prefix}.{key}" if prefix else key)


class TestAnchorsFile(unittest.TestCase):

    def test_file_exists_and_parses(self):
        self.assertTrue(ANCHORS_PATH.exists(), f"缺少锚点文件：{ANCHORS_PATH}")
        self.assertIsInstance(load_anchors(), dict)

    def test_every_anchor_has_required_fields(self):
        for path, node in iter_anchor_nodes(load_anchors()):
            for field in REQUIRED_FIELDS:
                self.assertIn(field, node, f"锚点 {path} 缺少字段 {field}")

    def test_basis_is_non_empty_string(self):
        for path, node in iter_anchor_nodes(load_anchors()):
            basis = node["basis"]
            self.assertIsInstance(basis, str, f"锚点 {path} 的 basis 必须是字符串")
            self.assertTrue(basis.strip(), f"锚点 {path} 的 basis 不能为空")

    def test_calibrated_is_bool(self):
        for path, node in iter_anchor_nodes(load_anchors()):
            self.assertIsInstance(
                node["calibrated"], bool,
                f"锚点 {path} 的 calibrated 必须是布尔值，不能是字符串",
            )

    def test_value_is_number_or_two_element_range(self):
        for path, node in iter_anchor_nodes(load_anchors()):
            value = node["value"]
            if isinstance(value, list):
                self.assertEqual(len(value), 2, f"锚点 {path} 的区间必须是两个元素")
                self.assertLess(value[0], value[1], f"锚点 {path} 的区间下界必须小于上界")
                for item in value:
                    self.assertIsInstance(item, (int, float), f"锚点 {path} 区间元素必须是数字")
                    self.assertNotIsInstance(item, bool, f"锚点 {path} 区间元素不能是布尔值")
            else:
                self.assertIsInstance(value, (int, float), f"锚点 {path} 的 value 必须是数字")
                self.assertNotIsInstance(value, bool, f"锚点 {path} 的 value 不能是布尔值")

    def test_scoring_weights_sum_to_100(self):
        dims = load_anchors()["scoring"]["dimensions"]
        total = sum(d["weight"] for d in dims.values())
        self.assertEqual(total, 100, f"五维权重合计必须为 100，当前为 {total}")

    def test_scoring_dimensions_have_metrics(self):
        dims = load_anchors()["scoring"]["dimensions"]
        self.assertEqual(
            set(dims), {"demand", "competition", "profit", "supply", "compliance"},
        )
        for name, dim in dims.items():
            self.assertTrue(dim.get("metrics"), f"维度 {name} 至少要有 1 个指标")


if __name__ == "__main__":
    unittest.main()
