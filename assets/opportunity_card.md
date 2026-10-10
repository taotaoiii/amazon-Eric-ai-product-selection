# 机会卡模板

> 复制此模板为每个候选方向建一张卡。
> **`缺口区` 是必填的——留空意味着这张卡没有如实暴露缺口，不入库。**
> `scripts/pool.py` 会对同样的字段做机器校验。

---

```json
{
  "id": "007",
  "name": "磁性刀架",
  "track": "niche",
  "stage": "competition",
  "evidence": [
    {
      "kind": "support",
      "content": "类目 Top10 月销合计 900 件，需求真实",
      "source": "商机探测器",
      "period": "2026-09"
    },
    {
      "kind": "against",
      "content": "头部两个品牌合计占 62% 销量",
      "source": "卖家精灵（估算）",
      "period": "2026-09"
    }
  ],
  "gaps": [
    {
      "missing": "类目退货率未拿到",
      "next_action": "找运营要上季度退货报表",
      "owner": "我"
    },
    {
      "missing": "磁性刀架的专利检索未做",
      "next_action": "在 Stage 5 查 USPTO Patent Center",
      "owner": "我"
    }
  ],
  "hard_filter_hits": [
    {"name": "top3_brand_share_max", "status": "pass", "note": "62% < 锚点上界"},
    {"name": "return_rate_max", "status": "unscreened", "note": "类目退货率未拿到"}
  ],
  "pain_tags": {
    "frequency": true,
    "severity": true,
    "solvability": false,
    "economics": true
  },
  "metrics": {
    "monthly_search_volume": 12000,
    "monthly_sales_units": 900,
    "top10_avg_reviews": 400,
    "category_avg_rating": 4.3,
    "fba_seller_count": 8,
    "break_even_acos": 0.35,
    "net_margin_after_ad": 0.18,
    "moq": 800,
    "lead_time_days": 30,
    "mandatory_cert_count": 1,
    "ip_red_flag_count": 0
  }
}
```

## 人读版（贴在报告里用）

```markdown
# 机会卡 #007 · 磁性刀架（细分赛道）

- 目标人群/场景：家庭厨房，常做饭、刀具多但台面小
- 代表 ASIN / 关键词：magnetic knife holder
- 与现有品的关系：细分（复用刀具供应链）
- 当前阶段：Stage 4 竞争验证
- 数据充分度：本评分基于 5/5 维

## 证据
| 类目 | 内容 | 来源 | 统计周期 |
|---|---|---|---|
| 支持 | 类目 Top10 月销合计 900 件 | 商机探测器 | 2026-09 |
| 反对 | 头部两品牌合计占 62% 销量 | 卖家精灵（估算） | 2026-09 |

## 缺口（必填）
- 缺失：类目退货率 → 动作：找运营要上季度退货报表 → 负责人：我
- 缺失：专利检索 → 动作：Stage 5 查 USPTO Patent Center → 负责人：我

## 判定
- 硬筛：`top3_brand_share_max` 通过；另有 1 项未筛（退货率）
- 痛点四维：F ✓ / S ✓ / Solvability ✗ / E ✓ → **未全部满足，不纳入改良方向**
- 阶段结论：需求成立，竞争有窗口，带着 1 项未筛进入 Stage 5
```

## 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✓ | 卡片编号，全局唯一 |
| `name` | ✓ | 方向名 |
| `track` | ✓ | `niche`（细分赛道）或 `complementary`（互补赛道） |
| `stage` | ✓ | Stage 0–9 标识符之一（共 10 个），见 `references/workflow.md` |
| `evidence[].kind` | ✓ | `support` 或 `against` |
| `evidence[].source` | ✓ | 数据来源，必须能溯源 |
| `evidence[].period` | ✓ | 统计周期 |
| `gaps[].missing` | ✓ | 缺什么 |
| `gaps[].next_action` | ✓ | 下一步做什么 |
| `gaps[].owner` | ✓ | 谁负责 |
| `hard_filter_hits[].status` | ✓ | `hit` / `pass` / `unscreened` 三值 |
| `pain_tags` | | 痛点四维，四项全 true 才纳入改良方向 |
| `metrics` | | 实测值，键名与 `anchors.yaml` 里的 metric 名一致；缺失的键直接不写 |
