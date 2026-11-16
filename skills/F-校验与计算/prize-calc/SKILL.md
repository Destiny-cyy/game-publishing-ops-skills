---
name: prize-calc
description: "奖品表计算与约束校验（场景驱动）：算行总价值、渠道小计、总盘子，并按当前场景档校验份数结构、价带、卡占比、每渠道头奖、渠道权重、预算带。当用户要「算一下奖品」「奖品表对不对」「改完价重算」「预算超没超」「份数对不对」「生成奖品表」时使用。开工先确认场景档（--profile / --list-profiles），不适用场景的检查项整组跳过。"
metadata:
  version: 2.0.0
  type: tool
---

> **本文件用到的占位符**（每个该填哪类信息、能不能外发，详见 `01-占位符字典.md`）
>
> | 占位符 | 该填哪类信息 |
> |---|---|
> | `{{BUDGET_AMOUNT}}` | 数值 · 单期总预算或价带金额（带币种） |
> | `{{CHANNEL_A}}` | 文本 · 合作渠道名，**按资源量从大到小**填；建议用代号而非真实商务主体名 |
> | `{{CHANNEL_C}}` | 文本 · 合作渠道名，**按资源量从大到小**填；建议用代号而非真实商务主体名 |
> | `{{CHANNEL_COUNT}}` | 数值 · 本期合作渠道**家数** |
> | `{{CHANNEL_D}}` | 文本 · 合作渠道名，**按资源量从大到小**填；建议用代号而非真实商务主体名 |
> | `{{CHANNEL_E}}` | 文本 · 第五类渠道（通常是社区/CPS 型，与前面四家口径不同） |
> | `{{WORK_DIR}}` | 路径 · 你的项目/输出目录 |

> **场景自适应**：本 skill 的具体数值一律按场景档取、不写死；开工先按 `_shared/规则三层说明.md` 选/建档（`--list-profiles`），不适用项整组跳过。硬红线见 `../REDLINES.md` 第零章，总则见准则 0.1。


# 奖品表计算与校验

## 这个 skill 解决什么

两个反复踩的坑：
1. **改完单价忘了重算小计**，各渠道之和与总盘子对不上（准则坑 13）——手工改数不复核必错
2. **奖品表维护两份导致数字打架**（330 vs 319，准则坑 5）

做法是：**奖品表只维护一份数据源（CSV/JSON），表格与数字全部由脚本算出来**，不再手抄；
**校验规则从场景档取**——同一张表在「{{CHANNEL_TYPE_A}}{{CHANNEL_COUNT}}家·抽奖梯度」和「{{CHANNEL_E}}·积分制」下，该查的项目完全不同。

## 用法

```bash
PY="{{WORK_DIR}}"
SK="{{WORK_DIR}}"

"$PY" "$SK" --list-profiles                       # 先看有哪些场景档
"$PY" "$SK" prizes.csv                            # 用默认档计算 + 校验
"$PY" "$SK" prizes.csv --profile community_cps   # 指定场景档（积分制：自动跳过梯度/权重/价带）
"$PY" "$SK" prizes.csv --md out.md               # 结果写成 markdown 表，可直接贴进方案
"$PY" "$SK" --demo --profile platform_resource     # 跑内置示例，验证「不适用检查被跳过」
```

场景档解析顺序：`--profile` > 数据源自带的 `profile` 字段 > `rules.json` 的 `default_profile`。
档支持 `extends` 继承（dict 深合并、list/标量覆盖），硬红线由 `profile_loader.py` 强制回填，子档覆盖不了。

## 输入格式

CSV（首行表头，顺序固定）或 JSON 数组：

```
渠道,档位,类型,名称,单价,数量
{{CHANNEL_A}},头奖,手柄,示例手柄 A,700,1
{{CHANNEL_A}},第二档,音频,示例音箱 A,300,2
{{CHANNEL_COUNT}}家,平台卡,卡,平台充值卡 30 元,30,60
```

- **渠道名自动归一**：同一家写 `{{CHANNEL_C}}` / `{{CHANNEL_C}}` / `{{CHANNEL_C}}{{CHANNEL_TYPE_A}}` 都认，别名登记在场景档 `channels[].aliases`。共用行填 `{{CHANNEL_COUNT}}家`（计入 `shared_total`，**不参与单渠道权重**）。
- **档位**：`头奖` / `第二档` / `平台卡` 会被校验，其他档位只参与汇总。
- **排除行**：场景档 `prize.exclude_types` 里的类型（默认档为 `CDK`）整行排除，不列支、不进渠道汇总，并报 `SCOPE-01` INFO——CDK 是已购库存，准则规定不计采买。

## 校验项（场景驱动）

「适用条件」不满足时，该检查项**整组跳过并报 INFO**，不算通过也不算违规。

| 码 | 级别 | 查什么 | 适用条件 / 取值来源 |
|---|---|---|---|
| `SCOPE-01` | INFO | 按 `prize.exclude_types` 排除的行数与类型 | 有排除行时 |
| `PRIZE-01` | ERROR / OK | 第二档份数 > 头奖份数 | `prize.model=lottery_tiers` 且 `prize.structure.second_gt_head`；其他模型跳过 |
| `PRIZE-02` | ERROR / INFO | 头奖单价在价带内 | 价带 = `prize.bands.头奖`；命中 `prize.exceptions` 的破例降级 INFO（默认档{{CHANNEL_D}} {{BUDGET_AMOUNT}}） |
| `PRIZE-03` | WARN / INFO | 第二档单价在价带内 | 价带 = `prize.bands.第二档` |
| `PRIZE-06` | ERROR / OK | 卡占比 ≥ 下限 | 下限 = `prize.structure.card_ratio_min`（默认档 60%）；盘子超标先看结构，别先砍卡 |
| `PRIZE-07` | ERROR / OK | 每渠道头奖件数 ≥ 下限 | 下限 = `prize.structure.head_per_channel_min`（默认档 1 件）；只查 `channels[].head_prize` 为真的渠道 |
| `PRIZE-04/05` | WARN / OK | 渠道金额权重顺序、同级容差 | `weight.order` / `weight.equal_pairs` / `weight.tolerance`；同级＝差额 ≤容差（**不是精确等额**） |
| `PRIZE-04b` | WARN | 头奖份数权重（份数不完全相同时才查） | 同上 |
| `BUDGET-01` | WARN / OK | 总额超阈值需给理由 | 阈值 = `budget.over_requires_reason`，参考带 = `budget.reference_band`；未设阈值则跳过 |

**`weight.enabled=false` 的场景**（单渠道 / 积分制 `h5_points` / 平台奖励 `platform_reward`）：
`PRIZE-01/02/03/06/07/04/05/04b` 全部跳过，只保留汇总与（若设了）`BUDGET-01`。

## 规则来源

- **硬红线**：`../_shared/rules.json` → `layers.hard` / `redline_words` / `delivery`（任何场景不许改）
- **场景参数**：`../_shared/profiles/<id>.json` → `prize` / `weight` / `budget` / `channels`
- **加载器**：`../_shared/profile_loader.py`（`extends` 深合并 + 硬红线回填）

规则不硬编码在脚本里。**改数值改 profile 并写 `overrides_log`，不要改脚本**；人读准则在 `_shared/REDLINES.md` 第五章。

## 工作流位置

选品定稿 → **本脚本算表** → 结果贴进方案正文（**只贴这一处**）→ 换款时改 CSV 重跑，同步备选清单与图片链接表。

换款时先列清楚「谁进、谁退到备选池」，再改 CSV 重跑——不要直接在方案正文里改数字。

## 配套

- 出稿前跑 `plan-lint`（**同一场景档**），它会检查正文里的奖品数字与价带
- 准则依据：`_shared/REDLINES.md` 第五章与第八章坑 4、5、12、13
