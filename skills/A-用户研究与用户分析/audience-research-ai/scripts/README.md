# scripts · 轻量本地工具说明


> **本文件用到的占位符**（每个该填哪类信息、能不能外发，详见 `01-占位符字典.md`）
>
> | 占位符 | 该填哪类信息 |
> |---|---|
> | `{{AS_OF_DATE}}` | 文本 · 数据/资料的**时点**，格式 `YYYY-MM-DD`，引用时必带 |
> | `{{PYTHON_ENV}}` | 路径 · 你的 Python 解释器或虚拟环境 |

> 这些脚本**只做统计与体检，不做 AI 推理**。推理由对话里的智能体按 `agents/` 角色卡完成。

---

## 依赖与边界

- Python 3.10+，**只用标准库**：csv / json / statistics / collections / argparse / pathlib。**不需要 pip install 任何东西**。
- **不联网**、不读任何绝对路径、不接任何账号 / 密钥 / 外部大模型接口。
- 默认解释器按你的环境填 `{{PYTHON_ENV}}`（本包不预置任何本机路径）；下面命令用 `python` 代指你的默认解释器。
- 输出统一是 JSON + 一行控制台摘要，写到 `out/`（自动创建，不进版本库）。

---

## 先跑自测

```bash
cd skills/A-用户研究与用户分析/audience-research-ai/scripts
python selftest.py
```

看到全部 `PASS` 才继续。`selftest.py` 用 `sample_data/` 里的最小虚构样本把五个工具全跑一遍，并断言「能检出重复/缺字段」「能拦住不合规策略」等能力。

---

## 五个工具

| 脚本 | 干什么 | 对应阶段 |
|---|---|---|
| `data_contract.py` | 四类数据统一成标准记录、必填校验、按 `user_tag + text` 去重、报缺口与问题 | 2 取数 |
| `segment.py` | 频次表、交叉表、分位数式轻量分层（近似 RFM），小样本组标「样本不足」 | 3 维度② |
| `theme_count.py` | 按自填词典做主题词频与共现 | 3 维度⑤ |
| `sentiment_lexicon.py` | 按自填词典统计正/负/中/混合倾向 | 3 维度④ |
| `strategy_lint.py` | 策略清单体检：五元组、三档、依据编号、C 级门槛、红线词 | 5 策略 |
| `selftest.py` | 一键自测 | 验收 |

## 命令

```bash
python data_contract.py --input sample_data/comments.csv --out out/contract.json
python segment.py       --input sample_data/profiles.csv --by server_line --cross-by device --rfm --out out/segments.json
python theme_count.py   --input sample_data/comments.csv --lexicon sample_data/lexicon.csv --out out/themes.json
python sentiment_lexicon.py --input sample_data/comments.csv --lexicon sample_data/lexicon.csv --out out/sentiment.json
python strategy_lint.py --input sample_data/strategies.csv --out out/lint.json
```

`strategy_lint.py` 有阻断项时退出码为 1，可串进自动化检查。红线词表默认内置，也可 `--redlines your_words.txt`（每行一个词）替换成你团队的词表。

---

## 输入字段

| 文件 | 列 | 说明 |
|---|---|---|
| `comments.csv` | `id, source, text, user_tag, timestamp, server_line, device` | 前五列必填；`extra` 自动收其余列 |
| `profiles.csv` | `user_tag, server_line, device, recency_days, freq, value` | 后三列用于分层，非数值会被归到「数据不足」 |
| `lexicon.csv` | `term, theme, polarity` | `theme_count` 用前两列；`sentiment_lexicon` 用 `term` + `polarity`（`pos`/`neg`，空值忽略） |
| `strategies.csv` | `id, insight_id, audience, touchpoint, action, timing, metric, metric_denominator, evidence_level, tier, expected, validation, redline_check` | 列名与 `references/05-洞察转策略规则.md` 一致 |

---

## 体检判定

`strategy_lint.py` 的 **block**（不放行）：五元组任一列为空、`insight_id` 为空、三档取值非法、证据等级非法、C 级却标「可立即执行」、动作/时机命中红线词。
**warn**（提示不阻断）：指标未写分母、缺验证方式。

> 脚本只查**结构与词表**，查不了语义和事实。红队审查与人工复核仍然必需。

---

## 示例数据说明（全部虚构）

- `comments.csv` 故意含 **1 条重复**（同 `user_tag + text`）和 **1 条缺 `text`**，用来演示入场校验能报出来。
- `strategies.csv` 故意含 **1 条不合规**（缺触点、C 级却标可立即执行），用来演示体检能拦住；所以直接跑 `strategy_lint.py` 看到 blocked 是**预期结果**。
- `timestamp` 用 `D1`~`Dx` 表示相对日序，真实使用时换成实际时点并带 `{{AS_OF_DATE}}` 口径。
- 文本、人群、触点、指标全是虚构，不对应任何真实项目。

---

## 能力边界（重要）

| 本脚本 | 不等价于 |
|---|---|
| 词典词频主题 | 语义主题模型（embedding → 聚类） |
| 词典情感 | 真实态度；反讽、黑话、玩梗需人工复核 |
| 中位数分层 | 机器学习聚类；它只是判据透明、可复算 |

价值在于**把口径和算术固定下来**，让不同智能体算出来的数能对得上。判断仍由智能体和人做；想上语义模型请自行评估依赖与许可证（见 `references/07-借鉴来源与许可证.md`）。
