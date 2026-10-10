#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
候选池管理（流程层核心）
========================
每张"机会卡"是一个 JSON 文件，卡上带着它的证据、缺口和实测数据。
本脚本负责读写、必填校验、以及横向排序。

用法：
  python pool.py check --pool pool/
  python pool.py rank  --pool pool/ --anchors config/anchors.yaml
  python pool.py list  --pool pool/
  python pool.py add   --pool pool/ --card card.json
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from score import load_anchors, score_candidate  # noqa: E402

# 阶段标识符（Step 0-9，共 10 个），与 references/workflow.md 一一对应
STAGES = [
    "bounds",       # 0 经营边界输入
    "discovery",    # 1 机会发现
    "hard_filter",  # 2 硬筛
    "demand",       # 3 需求验证
    "competition",  # 4 竞争验证 + VOC
    "deep_gate",    # 5 深度闸门（合规/IP + 供应链六问）
    "economics",    # 6 经济测算
    "priority",     # 7 优先级矩阵
    "test",         # 8 小批实测
    "retro",        # 9 复盘回填
]

TRACKS = ["niche", "complementary"]
EVIDENCE_KINDS = ["support", "against"]
# 硬筛结论三值。「未筛 ≠ 通过」的唯一机器层执行点：缺数据只能标 unscreened，
# 不得省略、不得用 pass 冒充（见 references/hard-filters.md 第三节）。
HARD_FILTER_STATUSES = ["hit", "pass", "unscreened"]

# Step 0-9 全部是有效状态（Step 9 复盘回填之后闭环，仍是有效阶段）
VALID_STAGES = set(STAGES)


def validate_card(card: dict) -> list:
    """返回问题清单；空列表表示这张卡结构完整、可以入库。"""
    problems = []

    for field in ("id", "name", "track", "stage"):
        if not card.get(field):
            problems.append(f"缺少必填字段：{field}")

    if card.get("track") and card["track"] not in TRACKS:
        problems.append(f"track 必须是 {TRACKS} 之一，当前为 {card['track']!r}")
    if card.get("stage") and card["stage"] not in VALID_STAGES:
        problems.append(f"stage 必须是 {sorted(VALID_STAGES)} 之一，当前为 {card['stage']!r}")

    gaps = card.get("gaps")
    if not gaps:
        problems.append(
            "gaps 不能为空：每张机会卡都必须写明「还缺什么信息」和「下一步动作」，"
            "留空意味着这张卡没有如实暴露缺口。"
        )
    else:
        for index, gap in enumerate(gaps):
            if not gap.get("missing"):
                problems.append(f"gaps[{index}] 缺少 missing")
            if not gap.get("next_action"):
                problems.append(f"gaps[{index}] 缺少 next_action（下一步动作必填）")
            if not gap.get("owner"):
                problems.append(f"gaps[{index}] 缺少 owner（负责人必填）")

    for index, item in enumerate(card.get("evidence", [])):
        if item.get("kind") not in EVIDENCE_KINDS:
            problems.append(f"evidence[{index}] 的 kind 必须是 {EVIDENCE_KINDS} 之一")
        if not item.get("content"):
            problems.append(f"evidence[{index}] 缺少 content")
        if not item.get("source"):
            problems.append(f"evidence[{index}] 缺少 source（来源必填）")
        if not item.get("period"):
            problems.append(f"evidence[{index}] 缺少 period（统计周期必填）")

    for index, hit in enumerate(card.get("hard_filter_hits", [])):
        if not hit.get("name"):
            problems.append(f"hard_filter_hits[{index}] 缺少 name")
        if hit.get("status") not in HARD_FILTER_STATUSES:
            problems.append(
                f"hard_filter_hits[{index}] 的 status 必须是 {HARD_FILTER_STATUSES} 之一，"
                f"当前为 {hit.get('status')!r}——数据缺失必须显式标 unscreened，"
                f"不得省略，也不得当作 pass"
            )

    return problems


def save_card(card: dict, pool_dir: str) -> pathlib.Path:
    """校验后写入候选池。结构不完整直接拒绝，不落盘。"""
    problems = validate_card(card)
    if problems:
        raise ValueError("机会卡结构不完整，拒绝入库：\n- " + "\n- ".join(problems))

    directory = pathlib.Path(pool_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{card['id']}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(card, fh, ensure_ascii=False, indent=2)
    return path


def load_card(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_pool(pool_dir: str) -> list:
    directory = pathlib.Path(pool_dir)
    if not directory.exists():
        return []
    return [load_card(str(p)) for p in sorted(directory.glob("*.json"))]


def rank_cards(cards: list, anchors: dict) -> list:
    """按总分降序排序。拒绝出分（缺失权重超限）的卡一律排在最后。

    不修改入参卡片——输出是新的包装结构。
    """
    ranked = []
    for card in cards:
        score = score_candidate(card.get("metrics", {}), anchors)
        ranked.append({"card": card, "score": score})

    def sort_key(entry):
        score = entry["score"]
        refused = 1 if score["refused"] or score["total"] is None else 0
        return (refused, -(score["total"] or 0.0))

    ranked.sort(key=sort_key)
    return ranked


def main():
    # Windows 下 stdout 走管道时默认继承本地编码（如 GBK），打印 ⚠️ 会抛
    # UnicodeEncodeError。统一锁定 UTF-8，保证 agent 通过管道捕获输出时可用。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="候选池管理")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="校验池内所有机会卡的结构完整性")
    check.add_argument("--pool", required=True)

    listing = sub.add_parser("list", help="列出池内所有机会卡")
    listing.add_argument("--pool", required=True)

    rank = sub.add_parser("rank", help="横向排序")
    rank.add_argument("--pool", required=True)
    rank.add_argument("--anchors", default="config/anchors.yaml")

    add = sub.add_parser("add", help="校验后新增一张机会卡到候选池")
    add.add_argument("--pool", required=True)
    add.add_argument("--card", required=True, help="机会卡 JSON 文件路径")

    args = parser.parse_args()

    if args.command == "add":
        card = load_card(args.card)
        try:
            path = save_card(card, args.pool)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        print(f"[已入库] {card['id']} {card['name']} → {path}")

    if args.command == "check":
        cards = load_pool(args.pool)
        if not cards:
            print(f"候选池为空或目录不存在：{args.pool}")
            return
        failed = False
        for card in cards:
            problems = validate_card(card)
            if problems:
                failed = True
                print(f"[不合格] {card.get('id', '?')} {card.get('name', '')}")
                for problem in problems:
                    print(f"    - {problem}")
            else:
                print(f"[合格] {card['id']} {card['name']}（阶段：{card['stage']}）")
        sys.exit(1 if failed else 0)

    if args.command == "list":
        for card in load_pool(args.pool):
            print(f"{card['id']}\t{card['stage']}\t{card['track']}\t{card['name']}")

    if args.command == "rank":
        anchors = load_anchors(args.anchors)
        rows = rank_cards(load_pool(args.pool), anchors)
        for entry in rows:
            score = entry["score"]
            if score["refused"]:
                total_display = "拒绝出分"
            else:
                total_display = f"{score['total']}"
            print(
                f"{entry['card']['id']}\t{total_display}\t{score['declaration']}\t{entry['card']['name']}"
            )
        if any(e["score"]["uncalibrated_anchors"] for e in rows):
            print("\n⚠️ 本次排序使用了未校准锚点，结论仅供参考。")


if __name__ == "__main__":
    main()
