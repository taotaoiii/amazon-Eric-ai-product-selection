"""保证文档里的每一种 anchors.yaml#key 引用都真实存在。

这是"阈值唯一来源"这条约束的自动化守卫：
文档里不许出现硬编码阈值，只能引用 anchors.yaml。
"""
import pathlib
import re
import unittest

import yaml

V2_ROOT = pathlib.Path(__file__).resolve().parents[1]
ANCHORS = yaml.safe_load((V2_ROOT / "config" / "anchors.yaml").read_text(encoding="utf-8"))

# 匹配 anchors.yaml#scoring.dimensions.demand.weight 这类引用
# 每段必须以字母/数字/下划线开头，避免把 `scoring.dimensions.<维度名>` 里的尾点吞进来
REFERENCE_PATTERN = re.compile(r"anchors\.yaml#([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)")


def all_markdown_files():
    for pattern in ("*.md", "references/*.md", "assets/*.md", "config/*.md"):
        yield from V2_ROOT.glob(pattern)


def resolve(node, dotted_path):
    """按点号路径深入嵌套 dict；任一层缺失返回 None。"""
    current = node
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


class TestDocumentationReferences(unittest.TestCase):

    def test_there_is_at_least_one_reference(self):
        """先确保测试本身有东西可测，避免全绿是假象。"""
        found = [
            match.group(1)
            for path in all_markdown_files()
            for match in REFERENCE_PATTERN.finditer(path.read_text(encoding="utf-8"))
        ]
        self.assertTrue(found, "没有任何 anchors.yaml#key 引用——文档可能仍在硬编码阈值")

    def test_every_reference_resolves(self):
        problems = []
        for path in all_markdown_files():
            text = path.read_text(encoding="utf-8")
            for match in REFERENCE_PATTERN.finditer(text):
                key = match.group(1)
                if resolve(ANCHORS, key) is None:
                    line = text[:match.start()].count("\n") + 1
                    problems.append(f"{path.name}:{line} 引用了不存在的锚点 {key}")
        self.assertEqual(problems, [], "存在悬空的锚点引用：\n" + "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
