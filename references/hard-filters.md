# 硬筛清单（Stage 2）—— 便宜的先筛掉

> 本文件只定义"筛什么"，具体数值一律取 `config/anchors.yaml` 的 `hard_filters.*`。
> 改阈值请改配置文件，不要改这份文档。

## 一、为什么把硬筛放在最前面

文章版 SOP 把"合规与知识产权"做成了第一道闸门。实操上这是行不通的——
你不可能为了 20 个候选方向，每个都去做一遍 USPTO 商标和专利检索，
那是每个方向几十分钟到几小时的活，做完黄花菜都凉了。

正确的顺序是：

1. **Stage 2 硬筛（便宜）**：全池 10–20 个候选都过一遍。判据是纯布尔值，看数据就能判死。
2. **Stage 5 深度闸门（昂贵）**：只对活下来的 2–3 个做完整 IP 检索和工厂询价。

**判据一句话：能用数据一秒判死的，放 Stage 2；需要人工去查、去问的，放 Stage 5。**

## 二、硬筛清单

每一条都是布尔判断。**任一条命中即出局**，命中记录写进机会卡的 `hard_filter_hits`。

| # | 筛什么 | 锚点键 | 命中即出局的情形 |
|---|---|---|---|
| 1 | 价格带 | `anchors.yaml#hard_filters.price_band_usd` | 均价落在区间之外 |
| 2 | 评论壁垒 | `anchors.yaml#hard_filters.top10_avg_reviews_max` | TOP10 平均评论数高于上限 |
| 3 | 动销强度 | `anchors.yaml#hard_filters.avg_bsr_max` | 类目平均 BSR 高于上限 |
| 4 | 品牌垄断 | `anchors.yaml#hard_filters.top3_brand_share_max` | TOP3 品牌销量占比高于上限 |
| 5 | 竞争密度 | `anchors.yaml#hard_filters.fba_seller_count_max` | FBA 卖家数高于上限 |
| 6 | 退货成本 | `anchors.yaml#hard_filters.return_rate_max` | 类目退货率高于上限 |
| 7 | 认证周期 | `anchors.yaml#hard_filters.cert_lead_time_months_max` | 强制认证周期长于上限 |

### 2.1 非数值型硬筛（不需要锚点，直接判）

这几条是"看一眼就知道不行"，不需要配置数值：

- **类目禁售 / 需专项审批**：亚马逊明确限制销售的品类，或需要额外审批的类目。
- **危险品**：需要 Hazmat / SDS 文件且你无能力提供的品类。
- **明显 IP 红牌**：通用词撞知名品牌、外观明显抄袭在售专利产品。
- **明显供应链不可行**：超大件、超重件、MOQ 远超你预算。
- **明显季节性**：单季营收占全年绝大部分，与你资金周转周期冲突。

## 三、最重要的一条规则：未筛 ≠ 通过

**任何一条硬筛，如果数据拿不到，标记为"未筛"，绝不标记为"通过"。**

这是整个流程里最容易自欺的地方。做法：

```json
"hard_filter_hits": [
  {"name": "return_rate_max", "status": "unscreened", "note": "类目退货率未拿到"}
]
```

`status` 取 `hit` / `pass` / `unscreened` 三值。

**某一"硬筛项"未筛时，候选可以继续往下走**——本节只管硬筛这一数据类，
其他数据（如类目月销规模）的缺失处理见 `references/data-sources.md` 的降级列，不受本条放行：

- 报告里必须显示它带着 N 条未筛项；
- 未筛项在 Stage 5 必须补上，否则不能进入 Stage 6 经济测算。

## 四、怎么按自己的类目调整

硬筛阈值不是普适的。同一个"TOP10 平均评论数"上限，
在手机壳类目和在工业drill press类目完全不是一个数量级。

调整方法见 `references/calibration.md`。调整后必须更新该锚点的
`last_reviewed`，若已通过回测验证则把 `calibrated` 改为 `true`。
