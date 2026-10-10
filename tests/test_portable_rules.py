"""portable/dist/ 下的规则文件必须与 portable/prompt-full.md 保持同步。

规则是「单一来源 → 多份产物」：同一套内容要放进 Cursor、Copilot、Windsurf、Cline、
Roo、Gemini CLI 等十几种格式。只要有人手改了其中一份，各工具之间就会悄悄跑偏，
而这种跑偏在真实使用中极难发现——你只会觉得"换个工具结果怎么不一样"。

本测试把这件事钉死：产物只要和 prompt-full.md 对不上（包括被删掉），就失败。
"""

import pathlib
import sys
import unittest

V2_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2_ROOT / "portable"))

import build_rules  # noqa: E402

REGENERATE = "请运行：python -X utf8 portable/build_rules.py"


class TestPortableRules(unittest.TestCase):
    def test_dist_stays_in_sync_with_source(self):
        stale = build_rules.find_drift()
        self.assertEqual([], stale, f"以下产物与 prompt-full.md 不一致：{stale}。{REGENERATE}")

    def test_every_target_is_rendered_and_non_trivial(self):
        rendered = build_rules.render_all()
        self.assertEqual(
            sorted(rel for rel, _ in build_rules.TARGETS),
            sorted(rendered),
            "每个声明过的目标都必须有产物",
        )
        for relative_path, content in rendered.items():
            with self.subTest(target=relative_path):
                self.assertGreater(len(content), 2000, f"{relative_path} 内容过短，像是被截断了")
                self.assertIn("未筛 ≠ 通过", content, f"{relative_path} 缺少核心硬规则")
                self.assertIn("本文件由 portable/build_rules.py", content, "缺少生成来源标注")

    def test_frontmatter_targets_start_with_frontmatter(self):
        """Cursor / Windsurf / Copilot 的新格式要求 frontmatter 是文件第一行。"""
        rendered = build_rules.render_all()
        for relative_path, frontmatter in build_rules.TARGETS:
            if not frontmatter:
                continue
            with self.subTest(target=relative_path):
                self.assertTrue(
                    rendered[relative_path].startswith("---\n"),
                    f"{relative_path} 必须以 frontmatter 开头，否则工具不会识别",
                )

    def test_plain_targets_have_no_frontmatter(self):
        """纯 Markdown 的格式不要凭空加 frontmatter——那会被当成正文显示出来。"""
        rendered = build_rules.render_all()
        for relative_path, frontmatter in build_rules.TARGETS:
            if frontmatter:
                continue
            with self.subTest(target=relative_path):
                self.assertFalse(
                    rendered[relative_path].startswith("---\n"),
                    f"{relative_path} 不应有 frontmatter",
                )
                self.assertTrue(rendered[relative_path].startswith("<!--"))

    def test_prompt_lite_stays_within_custom_instruction_budget(self):
        """精简版是给「自定义指令」这类有字数上限的位置用的，超了就没法用。"""
        lite = (V2_ROOT / "portable" / "prompt-lite.md").read_text(encoding="utf-8")
        self.assertLess(len(lite), 1600, "精简版超过 1600 字符，塞不进多数工具的自定义指令栏")


if __name__ == "__main__":
    unittest.main()
