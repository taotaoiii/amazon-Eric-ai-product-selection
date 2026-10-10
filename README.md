# amazon-ai-product-selection-v2

亚马逊 AI 选品全流程技能（Claude Code Skill）。把选品从"凭感觉"变成一条
**可重复执行、可复盘校准**的候选池流水线——**人为定规则，AI 提假设，数据来验证**。

它不输出"爆款清单"，输出的是**可核验的候选方向 + 决策证据**。

- 📖 **完整使用说明** → [`使用说明.md`](使用说明.md)
- 🤖 **给 AI 的入口** → [`SKILL.md`](SKILL.md)
- 🎚️ **唯一阈值来源** → [`config/anchors.yaml`](config/anchors.yaml)

## 它解决什么

选品失败通常不是"没市场"，而是三个问题之一：**不能卖**（合规/知识产权踩线）、
**做不出来**（供应链落不了地）、**卖了不赚钱**（成本算漏、模型跑不通）。
本技能把它拆成十个阶段（Step 0–9），中间嵌两道闸门——Stage 2 硬筛与 Stage 5 深度闸门。

三条硬规则贯穿全程：**未筛 ≠ 通过**、**数字必须可溯源**、**"待补"不能写成"已通过"**。

## 安装

```bash
cp -r amazon-ai-product-selection-v2 ~/.claude/skills/
```

重启 Claude Code 后，说"帮我选品 / 拓品 / 看看这个类目有没有机会"即可触发。

## 自测

```bash
cd amazon-ai-product-selection-v2 && python -X utf8 -m unittest discover -s tests -v
```

需要 Python 3.10+ 与 PyYAML。

> ⚠️ `config/anchors.yaml` 里每条锚点当前都是 `calibrated: false`，
> 用它得出的结论会带 ⚠️ 标。这是设计使然——它们是"带依据的起始值"，不是行业标准。
> 校准方法见 [`references/calibration.md`](references/calibration.md)。

## 许可证

[MIT](LICENSE)
