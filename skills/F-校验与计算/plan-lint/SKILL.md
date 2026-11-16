---
name: plan-lint
description: "方案出稿前的自动体检（场景驱动）：扫方案全文，按当前场景档列出硬伤。当用户要「检查一下方案」「出稿前体检」「方案有没有问题」「帮我审一遍」「能不能发出去」「跑一下 lint」「检查口径」「检查奖品表」时使用。硬红线全局恒查；禁用的指标、排期锚点、风险、价带、脱敏词都从 profile 取，不适用就整组跳过。输出 ERROR/WARN/INFO 三级，ERROR 未修完不要出稿。"
metadata:
  version: 2.1.0
  type: tool
---

> **本文件用到的占位符**（每个该填哪类信息、能不能外发，详见 `01-占位符字典.md`）
>
> | 占位符 | 该填哪类信息 |
> |---|---|
> | `{{BUDGET_AMOUNT}}` | 数值 · 单期总预算或价带金额（带币种） |
> | `{{CHANNEL_A}}` | 文本 · 合作渠道名，**按资源量从大到小**填；建议用代号而非真实商务主体名 |
> | `{{CHANNEL_COUNT}}` | 数值 · 本期合作渠道**家数** |
> | `{{CHANNEL_E}}` | 文本 · 第五类渠道（通常是社区/CPS 型，与前面四家口径不同） |
> | `{{DEVELOPER}}` | 文本 · 游戏研发/发行主体称谓 |
> | `{{SERVER_LINE_A}}` | 文本 · 主服线名称 |
> | `{{SERVER_LINE_B}}` | 文本 · 另一条服线名称。**两条服线的信息不可混用**是硬红线 |
> | `{{VERSION_NAME}}` | 文本 · 本期版本/活动的**官方名称** |
> | `{{WORK_DIR}}` | 路径 · 你的项目/输出目录 |

> **场景自适应**：本 skill 的具体数值一律按场景档取、不写死；开工先按 `_shared/规则三层说明.md` 选/建档（`--list-profiles`），不适用项整组跳过。硬红线见 `../REDLINES.md` 第零章，总则见准则 0.1。


# 方案出稿体检

## 这个 skill 解决什么

准则里最硬的几条防线以前全靠人肉检查——这正是坑反复出现的原因（改价忘复核、跨口径相加、外发裂图，都是"规则写在文档里但没人真的执行"）。

这个脚本把检查变成一条命令：**出稿前跑一次，硬伤列出来，修完再发。**
v2.0 起 **检查项随场景档变**：同一份方案在「预约期·{{CHANNEL_TYPE_A}}{{CHANNEL_COUNT}}家」和「{{CHANNEL_E}}·积分制」下，该报的项不一样——避免把 {{VERSION_NAME}} 的 T-45、{{CHANNEL_COUNT}}家权重、{{BUDGET_AMOUNT}}~700 套到所有活动上。

## 用法

```bash
PY="{{WORK_DIR}}"
SK="{{WORK_DIR}}"

"$PY" "$SK" --list-profiles                       # 先看有哪些场景档

# 体检（方案 + 外置的排期/风险 md 一起传，锚点互认）；--profile 指定场景档
"$PY" "$SK" "{{WORK_DIR}}/output/方案_v6.html" "{{WORK_DIR}}/output/执行与风险.md" --profile channel_prebook

# 换个场景：积分制{{CHANNEL_E}}，禁用指标/排期锚点/价带自动换一套
"$PY" "$SK" "{{WORK_DIR}}/output/{{CHANNEL_E}}方案.md" --profile community_cps

# 外发模式：额外按场景档的脱敏词表提示
"$PY" "$SK" "{{WORK_DIR}}/output/方案_v6_自包含.html" --external

# 只看摘要 / 只看某一级
"$PY" "$SK" "{{WORK_DIR}}/output/方案_v6.html" --summary
"$PY" "$SK" "{{WORK_DIR}}/output/方案_v6.html" --only error
```

退出码：`0` 通过（无 ERROR）／`1` 有 ERROR／`2` 出错（含场景档加载失败）。
场景档解析：`--profile` > 方案 frontmatter 的 `profile` 字段 > `rules.json` 的 `default_profile`。

## 检查项

**A. 硬红线（全局恒查，任何场景都不跳过）**

| 码 | 级别 | 查什么 |
|---|---|---|
| `DELIVERY-01` | ERROR/WARN | html 外部图片引用——单独发送对方看不到。自包含版 / `--external` 报 ERROR，其余报 WARN |
| `RED-PAY_TO_WIN` | ERROR | 付费变强类表述（氪金 / 碾压 / 战力领先…） |
| `RED-OFFICIAL_TONE` | ERROR | 官方腔（敬请期待 / 官方指定 / 唯一合作…） |
| `RED-PREBOOKING_FALSE_CLAIM` | ERROR | 预约期写成「版本已上线 / 现已开放」——**仅 `node.type=预约期` 启用**；版本周不查（那时是事实） |
| `RED-SERVER` | WARN | 同一句混用{{SERVER_LINE_B}}与{{SERVER_LINE_A}} |
| `METRIC-02` | WARN | 疑似把不可比口径做合计——**清单随档变，但「不相加」是硬纪律** |
| `REALITY-01` | ERROR/WARN/INFO | **现实边界线**：脱实表述（付费变强 / 数据互通 / 跨服继承 / {{PAID_BUNDLE_NAME}} / {{PAID_CURRENCY_NAME}} / {{EXCLUSIVE_ITEM_WORD}} 等），级别取自 `rules.json` 的 `reality_guard.forbidden_claims`；否定语境降 INFO |
| `REALITY-02` | WARN | 把「讨论声量占比」写成人口比例（「X% 的玩家/用户/人群」缺「声量 / 讨论 / 样本」限定），准则 0.2 |

**B. 场景派生项（从 `profiles/<id>.json` 取，不适用整组跳过）**

| 码 | 级别 | 查什么 | 取值来源 |
|---|---|---|---|
| `METRIC-01` | WARN/INFO | 违禁指标（默认档「入库人数」） | `metrics.forbidden`；**若有渠道 `can_report_install` 则禁用不适用**（{{CHANNEL_E}}能回传 → 不报） |
| `CHANNEL-01` | WARN | 被按参与规模考核的渠道 | `channels[].no_participation_kpi`（默认档 {{CHANNEL_A}}），名单不写死 |
| `SCHED-01` | WARN | 缺排期锚点 | `schedule.anchors`；无 {{DEVELOPER}} 审批的场景不要求 T-45 |
| `RISK-01` | WARN | 缺版本延期预案 | 仅 `schedule.needs_version_delay_risk=true` 时查 |
| `PRIZE-01` | ERROR/INFO | 第二档份数 > 头奖份数 | 仅 `prize.model=lottery_tiers` 且 `second_gt_head` |
| `PRIZE-02` | WARN/INFO | 单价超出头奖价带 | `prize.bands.头奖`；命中 `prize.exceptions` 的登记价降级 INFO |
| `DESENS-01` | INFO | 外发脱敏词表 | `delivery.desensitize_keywords` / `delivery.audience` |
| `RED-NEG` | INFO | 红线词出现在「不写 XX」否定语境，已自动跳过 | — |

**否定语境自动豁免**：规则说明里写「不写变强 / 碾压」「曝光一律分渠道单列、不合计」不算违规，脚本识别 `不写 / 禁止 / 不得 / 严禁 / 不合计 / 单列 / 分渠道` 等上下文后降级为 INFO。

## 规则来源

- **硬红线**：`../_shared/rules.json` → `layers.hard` / `redline_words` / `delivery` / `reality_guard`（现实边界线，准则 0.2）
- **场景参数**：`../_shared/profiles/<id>.json` → `channels` / `metrics` / `schedule` / `prize` / `delivery`
- **加载器**：`../_shared/profile_loader.py`

规则不硬编码在脚本里。**改数值改 profile 并写 `overrides_log`，不要改脚本。**
人读版在 `../REDLINES.md`，准则版在 `_shared/REDLINES.md`，三处需同步。

## 配套动作

- 报 `DELIVERY-01` → 跑 `{{可选工具·HTML自包含}}` 生成自包含版
- 报 `PRIZE-*` → 用 `prize-calc` 重算奖品表（**用同一场景档**，两边才对得上）

## 已知边界

脚本做的是**正则级文本扫描**，不是语义理解：
- 报出来的 WARN 需要人工确认是不是误判
- 查不出"该写但没写"的东西（比如缺素材×人群配对表）
- 真正的判断仍在准则 10.1 / 10.2 / 10.3 三段自检里，脚本只负责那些**可机械化的部分**
