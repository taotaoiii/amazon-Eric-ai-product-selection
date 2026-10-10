# 移植版：在其他 AI 工具里用这套选品规则

原 skill 是 Claude Code Skill 形态，依赖「按需加载三级文档」这个机制——别的工具没有。
本目录把整套规则压成**自包含**的文件，让 Cursor / Copilot / ChatGPT 等也能用同一套判读口径。

## 先说清楚：什么能移植，什么会打折

| 部分 | 移植性 | 说明 |
|---|---|---|
| **流程与判读规则** | ✅ 完全可移植 | 三条硬规则、十阶段、两道闸门、缺失数据处理——都是文字，哪都能用 |
| **三个脚本** | ✅ 完全可移植 | 只依赖 Python 3.10+ 与 PyYAML，跟用哪个 AI 无关 |
| **阈值** | ⚠️ 快照 | 已内联进规则文件，是 `config/anchors.yaml` 某一时刻的副本 |
| **自动触发** | ❌ 仅 Claude 系 | 别的工具靠各自的规则文件常驻生效，没有「按需加载」 |
| **硬规则的强制力** | ⚠️ 靠模型自觉 | 见下 |

> **最大的实际风险：硬规则没有代码强制。**
> 「数字必须可溯源」「未筛 ≠ 通过」是用自然语言约束模型行为。强模型守得住，
> 弱模型会照样编市场数据。脚本能兜住打分与校验，**兜不住取数环节**。
> 换平台后请自己盯紧这一条。

## 怎么装

### 1. 代码编辑器里的 AI（Cursor / Copilot / Windsurf / Cline / Roo / Zed / Junie / Amazon Q / Aider）

`dist/` 里的文件**按相对路径原样拷到你的项目根目录**。只拷你要用的那个就行：

```bash
# 例：在某个项目里启用 Cursor + Copilot
cp -r amazon-ai-product-selection-v2/portable/dist/.cursor .
cp -r amazon-ai-product-selection-v2/portable/dist/.github .
```

| 工具 | 拷贝这个 |
|---|---|
| **通用（Codex、Cursor、Zed、Jules、Amp…）** | `dist/AGENTS.md` |
| Claude Code（项目级，非 skill） | `dist/CLAUDE.md` |
| Gemini CLI | `dist/GEMINI.md` |
| Cursor（新版） | `dist/.cursor/rules/amazon-selection.mdc` |
| Cursor（旧版） | `dist/.cursorrules` |
| GitHub Copilot（仓库级） | `dist/.github/copilot-instructions.md` |
| GitHub Copilot（作用域式） | `dist/.github/instructions/amazon-selection.instructions.md` |
| Windsurf（新版） | `dist/.windsurf/rules/amazon-selection.md` |
| Windsurf / Codeium（旧版） | `dist/.windsurfrules` |
| Cline | `dist/.clinerules/amazon-selection.md` |
| Roo Code | `dist/.roo/rules/amazon-selection.md` |
| JetBrains Junie | `dist/.junie/guidelines.md` |
| Amazon Q Developer | `dist/.amazonq/rules/amazon-selection.md` |
| Aider | `dist/CONVENTIONS.md` |
| Zed | `dist/.rules` |

**建议：把脚本也带上。** 规则文件只定义判读口径；要真把分数算出来，还得有脚本：

```bash
cp -r amazon-ai-product-selection-v2/scripts ./amazon-selection-scripts
```

### 2. 对话型 AI（ChatGPT / Gemini / Claude / DeepSeek / 豆包 / Kimi）

这些工具没有项目文件的概念，用 `portable/` 下的提示词：

- **`prompt-full.md`** —— 完整版，自包含。适合：
  - ChatGPT：**Projects** 的 Instructions，或对话第一条消息
  - Gemini：**Gem** 的指令
  - Claude：**Project** 的 Instructions
  - 豆包 / Kimi / DeepSeek：对话首条消息（这些没有常驻指令位）
- **`prompt-lite.md`** —— 精简版，1091 字符。适合有字数上限的「自定义指令」栏。

> 自定义指令栏的字数通常只够放骨架。真做选品时，**把 `prompt-full.md` 整份贴进对话**。

## 改了规则怎么更新

**所有产物由 `prompt-full.md` 生成，不要直接编辑 `dist/` 下的文件**——会被整份覆盖。

```bash
# 改完 prompt-full.md 后
python -X utf8 portable/build_rules.py

# 只想检查有没有跑偏
python -X utf8 portable/build_rules.py --check
```

`tests/test_portable_rules.py` 会校验产物与源文件一致，跑偏即测试失败——
这样就不会出现「改了 Cursor 那份、忘了 Copilot 那份」的情况。

## 改了 `config/anchors.yaml` 怎么办

规则文件里的「阈值快照」会**过时**。锚点调整后：

1. 重跑 `python -X utf8 portable/build_rules.py` —— 但**这不会自动同步阈值**，
   因为快照写在 `prompt-full.md` 里，是手写的；
2. 所以请**同时**更新 `prompt-full.md` 第六节的那两张表，再重跑生成器。

> 这是本移植版的已知取舍：为了自包含，阈值只能内联；
> 而内联就意味着多一处需要手工同步。权威来源始终是 `config/anchors.yaml`。

## 一个要留意的限制：文件偏大

每份产物约 **21 KB**（约 530 行）。多数工具吃得下，但有些对常驻上下文有硬性截断，
规则尾部会被悄悄丢掉——而丢掉的往往正是最后的「质量校验」和「避坑清单」。

如果发现模型不遵守后半段规则，改用 `prompt-lite.md`（1091 字符），
或者只把 `prompt-full.md` 的第三、六、七节贴进对话。

## 文件结构

```
portable/
├── README.md            ← 你正在看的这份
├── prompt-full.md       ← 【单一来源】完整规则，可直接粘贴
├── prompt-lite.md       ← 精简版（1091 字符）
├── build_rules.py       ← 生成器：把 prompt-full.md 编译成各种工具格式
└── dist/                ← 生成物，按相对路径拷进你的项目
    ├── AGENTS.md
    ├── CLAUDE.md
    ├── GEMINI.md
    ├── CONVENTIONS.md
    ├── .rules
    ├── .cursorrules
    ├── .windsurfrules
    ├── .cursor/rules/amazon-selection.mdc
    ├── .windsurf/rules/amazon-selection.md
    ├── .github/copilot-instructions.md
    ├── .github/instructions/amazon-selection.instructions.md
    ├── .clinerules/amazon-selection.md
    ├── .roo/rules/amazon-selection.md
    ├── .junie/guidelines.md
    └── .amazonq/rules/amazon-selection.md
```
