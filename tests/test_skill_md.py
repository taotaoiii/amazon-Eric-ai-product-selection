"""SKILL.md 的规范测试：渐进披露、frontmatter、引用完整性。"""
import pathlib
import re
import unittest

V2_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_PATH = V2_ROOT / "SKILL.md"
MAX_BODY_LINES = 500

FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
# 匹配反引号里的相对路径引用，如 references/workflow.md
PATH_PATTERN = re.compile(r"`((?:references|scripts|assets|config)/[A-Za-z0-9_\-./]+)`")


def read_skill():
    return SKILL_PATH.read_text(encoding="utf-8")


class TestSkillMd(unittest.TestCase):

    def test_exists(self):
        self.assertTrue(SKILL_PATH.exists(), "缺少 SKILL.md")

    def test_has_frontmatter_with_name_and_description(self):
        text = read_skill()
        match = FRONTMATTER_PATTERN.match(text)
        self.assertIsNotNone(match, "SKILL.md 必须以 YAML frontmatter 开头")
        frontmatter = match.group(1)
        self.assertRegex(frontmatter, r"(?m)^name:\s*\S+")
        self.assertRegex(frontmatter, r"(?m)^description:\s*\S+")

    def test_name_matches_directory_convention(self):
        frontmatter = FRONTMATTER_PATTERN.match(read_skill()).group(1)
        name = re.search(r"(?m)^name:\s*(.+)$", frontmatter).group(1).strip()
        self.assertEqual(name, "amazon-ai-product-selection-v2")

    def test_description_states_when_to_use(self):
        """description 要同时说清「做什么」和「何时用」——这是触发判断的全部依据。"""
        frontmatter = FRONTMATTER_PATTERN.match(read_skill()).group(1)
        description = re.search(r"(?m)^description:\s*(.+)$", frontmatter).group(1)
        for keyword in ("选品", "拓品"):
            self.assertIn(keyword, description, f"description 应包含触发词「{keyword}」")

    def test_body_under_line_limit(self):
        text = read_skill()
        body = FRONTMATTER_PATTERN.sub("", text)
        line_count = len(body.splitlines())
        self.assertLess(
            line_count, MAX_BODY_LINES,
            f"SKILL.md 正文 {line_count} 行，超过 {MAX_BODY_LINES} 行上限；"
            f"应将细节移入 references/",
        )

    def test_all_referenced_paths_exist(self):
        paths = set(PATH_PATTERN.findall(read_skill()))
        self.assertTrue(paths, "SKILL.md 里没有任何文件路径引用——路径检查会假绿，无法证伪")
        missing = [rel for rel in paths if not (V2_ROOT / rel).exists()]
        self.assertEqual(missing, [], f"SKILL.md 引用了不存在的文件：{missing}")

    def test_states_the_three_hard_rules(self):
        text = read_skill()
        self.assertIn("未筛", text, "SKILL.md 必须写明「未筛 ≠ 通过」")
        self.assertIn("溯源", text, "SKILL.md 必须写明数字可溯源的要求")
        self.assertIn("待补", text, "SKILL.md 必须写明「'待补'不能写成'已通过'」")

    def test_states_all_ten_stage_identifiers(self):
        text = read_skill()
        for stage in ("bounds", "discovery", "hard_filter", "demand",
                      "competition", "deep_gate", "economics", "priority",
                      "test", "retro"):
            self.assertIn(stage, text, f"SKILL.md 应提到阶段标识符 {stage}")

    def test_points_to_anchors_yaml_as_single_source(self):
        self.assertIn("config/anchors.yaml", read_skill(),
                      "SKILL.md 必须把 config/anchors.yaml 指为唯一阈值来源")


if __name__ == "__main__":
    unittest.main()
