#!/usr/bin/env python3
"""把 portable/prompt-full.md 编译成各种 AI 工具的规则文件。

用法::

    python -X utf8 portable/build_rules.py           # 生成/刷新 portable/dist/
    python -X utf8 portable/build_rules.py --check   # 只校验是否同步，不写盘

**单一来源是 `portable/prompt-full.md`。** 要改规则内容就改那个文件，然后重跑本脚本。
不要直接编辑 `portable/dist/` 下的产物——它们会被整份覆盖。

为什么要生成而不是手写十几份：同一套规则要在 Cursor / Copilot / Windsurf / Cline /
Roo / Gemini CLI / JetBrains / Amazon Q 等十几种格式里各放一份，手写必然跑偏。
`tests/test_portable_rules.py` 会校验产物与源文件一致，跑偏即测试失败。
"""

from __future__ import annotations

import argparse
import pathlib

PORTABLE_DIR = pathlib.Path(__file__).resolve().parent
SOURCE = PORTABLE_DIR / "prompt-full.md"
DIST = PORTABLE_DIR / "dist"

PROVENANCE = (
    "<!-- 本文件由 portable/build_rules.py 从 portable/prompt-full.md 生成，请勿直接编辑。"
    " 要改规则，改 prompt-full.md 后重跑该脚本。 -->"
)

# Cursor 新版规则（.mdc）：三个字段都要给，alwaysApply 让它常驻上下文。
CURSOR_FRONTMATTER = """\
---
description: 亚马逊 AI 选品十阶段流水线（选品/拓品/需求验证/竞争分析/供应链核验/利润测算/Go-No-Go）
globs: **/*
alwaysApply: true
---"""

# Windsurf 新版规则目录：trigger 取 always_on 才会自动加载。
WINDSURF_FRONTMATTER = """\
---
trigger: always_on
---"""

# GitHub Copilot 的 .instructions.md：applyTo 决定作用范围。
COPILOT_FRONTMATTER = """\
---
applyTo: "**"
---"""

# (dist 内相对路径, 该格式要求的 frontmatter)
#
# 空字符串 = 纯 Markdown，无 frontmatter。
TARGETS: list[tuple[str, str]] = [
    # —— 通用 / 跨工具 ——
    ("AGENTS.md", ""),                       # 事实标准：Codex、Cursor、Zed、Jules、Amp …
    ("CLAUDE.md", ""),                       # Claude Code 项目级记忆
    ("GEMINI.md", ""),                       # Gemini CLI
    ("CONVENTIONS.md", ""),                  # Aider
    (".rules", ""),                          # Zed
    # —— 各编辑器的传统单文件约定 ——
    (".cursorrules", ""),                    # Cursor 旧版（仍在广泛使用）
    (".windsurfrules", ""),                  # Windsurf / Codeium 旧版
    (".clinerules/amazon-selection.md", ""),  # Cline 目录式
    (".roo/rules/amazon-selection.md", ""),  # Roo Code
    (".junie/guidelines.md", ""),            # JetBrains Junie
    (".amazonq/rules/amazon-selection.md", ""),  # Amazon Q Developer
    (".github/copilot-instructions.md", ""),  # GitHub Copilot（仓库级）
    # —— 需要 frontmatter 的新式约定 ——
    (".cursor/rules/amazon-selection.mdc", CURSOR_FRONTMATTER),
    (".windsurf/rules/amazon-selection.md", WINDSURF_FRONTMATTER),
    (".github/instructions/amazon-selection.instructions.md", COPILOT_FRONTMATTER),
]


def render_all() -> dict[str, str]:
    """返回 {dist 内相对路径: 文件全文}。不碰磁盘。"""
    body = SOURCE.read_text(encoding="utf-8").strip()
    rendered: dict[str, str] = {}
    for relative_path, frontmatter in TARGETS:
        blocks = []
        if frontmatter:
            blocks.append(frontmatter)
        blocks.append(PROVENANCE)
        blocks.append(body)
        rendered[relative_path] = "\n\n".join(blocks) + "\n"
    return rendered


def find_drift() -> list[str]:
    """返回与源文件不一致的产物相对路径（缺失也算）。"""
    drift = []
    for relative_path, expected in render_all().items():
        path = DIST / relative_path
        actual = path.read_text(encoding="utf-8") if path.exists() else None
        if actual != expected:
            drift.append(relative_path)
    return drift


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成各 AI 工具的规则文件")
    parser.add_argument("--check", action="store_true", help="只校验同步状态，不写盘")
    args = parser.parse_args(argv)

    if args.check:
        drift = find_drift()
        for relative_path in drift:
            print(f"不同步: {relative_path}")
        print(f"{len(TARGETS) - len(drift)}/{len(TARGETS)} 个规则文件与 prompt-full.md 一致")
        return 1 if drift else 0

    rendered = render_all()
    for relative_path, content in rendered.items():
        path = DIST / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"已生成 {len(rendered)} 个规则文件 → {DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
