#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可复现评分器（规则层核心）
==========================
读 config/anchors.yaml，把候选的实测值归一化成 0-100 的总分。

设计原则（见 references/scoring.md）：
  1. 算术要确定，锚点要诚实——公式固定，锚点可校准。
  2. 缺失维度被丢弃并重归一化，绝不填零充当"差"。
  3. 缺失权重严格大于熔断线时，拒绝输出总分。

用法：
  python score.py --anchors config/anchors.yaml --input values.json
"""

import argparse
import json
import math
import sys

DIMENSION_ORDER = ["demand", "competition", "profit", "supply", "compliance"]


def load_anchors(path: str) -> dict:
    """读取锚点配置。缺少 PyYAML 时给出可操作的提示。"""
    import pathlib

    file_path = pathlib.Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"找不到锚点文件：{file_path}")
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - 环境相关
        raise ImportError(
            "缺少 PyYAML。请先运行：pip install pyyaml"
        ) from exc
    with file_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _transform(value: float, transform: str) -> float:
    """对数值做变换。log 变换用于压缩量级差异极大的指标（搜索量、BSR、评论数）。"""
    if transform == "log":
        return math.log10(max(float(value), 1.0))
    return float(value)


def normalize(value: float, lo: float, hi: float, transform: str, direction: str) -> float:
    """把实测值归一化到 [0, 1]。

    direction = "higher"：区间上界 hi 得满分（lo 最差）
    direction = "lower" ：区间下界 lo 得满分（hi 最差）——用于 MOQ、退货率、垄断度
    """
    if hi == lo:
        raise ValueError("锚点区间上下界不能相等")
    f_value = _transform(value, transform)
    f_lo = _transform(lo, transform)
    f_hi = _transform(hi, transform)
    if f_hi == f_lo:
        raise ValueError("锚点区间上下界在变换后相等，无法归一化")
    if direction == "higher":
        ratio = (f_value - f_lo) / (f_hi - f_lo)
    elif direction == "lower":
        ratio = (f_hi - f_value) / (f_hi - f_lo)
    else:
        raise ValueError(f"未知的 direction：{direction}")
    return min(1.0, max(0.0, ratio))


def _collect_anchor_paths(anchors: dict) -> list:
    """列出评分实际用到的所有锚点路径，用于报告"哪些锚点未校准"。"""
    paths = []
    refuse_node = anchors["scoring"]["refuse_total_above_missing_weight"]
    paths.append(("scoring.refuse_total_above_missing_weight", refuse_node))
    for dim_name, dim in anchors["scoring"]["dimensions"].items():
        for metric_name, metric in dim["metrics"].items():
            paths.append((f"scoring.dimensions.{dim_name}.metrics.{metric_name}", metric))
    return paths


def score_candidate(candidate: dict, anchors: dict) -> dict:
    """给一个候选打分。

    candidate 的键与 anchors 里的 metric 名一一对应；缺失的键表示该项数据没有拿到。
    """
    dimensions_cfg = anchors["scoring"]["dimensions"]
    refuse_line = anchors["scoring"]["refuse_total_above_missing_weight"]["value"]

    total_weight = sum(dim["weight"] for dim in dimensions_cfg.values())
    computable_weight = 0
    weighted_sum = 0.0
    dimensions_out = {}
    computable_count = 0

    for dim_name in DIMENSION_ORDER:
        dim_cfg = dimensions_cfg[dim_name]
        metric_scores = []
        metrics_used = []

        for metric_name, metric_cfg in dim_cfg["metrics"].items():
            if metric_name not in candidate or candidate[metric_name] is None:
                continue
            lo, hi = metric_cfg["value"]
            score = normalize(
                candidate[metric_name], lo, hi,
                metric_cfg.get("transform", "none"),
                metric_cfg.get("direction", "higher"),
            )
            metric_scores.append(score)
            metrics_used.append(metric_name)

        if metric_scores:
            dim_score = sum(metric_scores) / len(metric_scores)
            dimensions_out[dim_name] = {
                "score": round(dim_score, 4),
                "weight": dim_cfg["weight"],
                "metrics_used": metrics_used,
                "skipped": False,
            }
            weighted_sum += dim_score * dim_cfg["weight"]
            computable_weight += dim_cfg["weight"]
            computable_count += 1
        else:
            dimensions_out[dim_name] = {
                "score": None,
                "weight": dim_cfg["weight"],
                "metrics_used": [],
                "skipped": True,
            }

    dimension_total = len(DIMENSION_ORDER)
    missing_weight_pct = round((total_weight - computable_weight) / total_weight, 4)
    declaration = f"本评分基于 {computable_count}/{dimension_total} 维"

    refused = missing_weight_pct > refuse_line
    if refused:
        total = None
        refuse_reason = (
            f"缺失维度权重占比 {missing_weight_pct:.0%} 已超过熔断线 {refuse_line:.0%}，"
            f"剩余维度的总分不具备区分度，拒绝输出总分。请补齐数据后重跑。"
        )
    else:
        total = round(weighted_sum / computable_weight * 100, 1) if computable_weight else None
        refuse_reason = None

    uncalibrated = [
        path for path, node in _collect_anchor_paths(anchors)
        if not node.get("calibrated", False)
    ]

    return {
        "dimensions": dimensions_out,
        "total": total,
        "declaration": declaration,
        "missing_weight_pct": missing_weight_pct,
        "refused": refused,
        "refuse_reason": refuse_reason,
        "uncalibrated_anchors": uncalibrated,
    }


def main():
    # Windows 下 stdout 走管道时默认继承本地编码（如 GBK），打印 ⚠️ 会抛
    # UnicodeEncodeError。统一锁定 UTF-8，保证 agent 通过管道捕获输出时可用。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="亚马逊选品候选评分器")
    parser.add_argument("--anchors", default="config/anchors.yaml", help="锚点配置文件路径")
    parser.add_argument("--input", required=True, help="候选实测值的 JSON 文件")
    args = parser.parse_args()

    anchors = load_anchors(args.anchors)
    with open(args.input, encoding="utf-8") as fh:
        candidate = json.load(fh)

    result = score_candidate(candidate, anchors)
    if result["uncalibrated_anchors"]:
        result["warning"] = (
            "⚠️ 本次评分使用了未校准锚点，结论仅供参考，"
            "请按 references/calibration.md 校准后重跑。"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
