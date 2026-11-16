---
name: audience-insight
description: "{{GAME_CN}} 目标地区玩家群体数据采集、聚类分析与渠道方案对接工具。当用户要「采集玩家数据」「分析玩家群体」「玩家画像」「社区舆情聚类」「了解PC端{{GAME_CN}}玩家」「找潜在用户」「数据驱动运营方案」「用户分群」「把玩家洞察对接渠道方案」「生成人群事实」时使用。从{{COMMUNITY_VIDEO}}评论+{{COMMUNITY_FORUM}}帖子+{{GAME_DATA_API}}官方游戏数据采集，用TF-IDF+KMeans聚类出玩家群体画像并给出运营建议，产出HTML洞察报告，并可export机器可读人群事实对接渠道方案场景档。"
metadata:
  version: 1.4.0
---

> **本文件用到的占位符**（每个该填哪类信息、能不能外发，详见 `01-占位符字典.md`）
>
> | 占位符 | 该填哪类信息 |
> |---|---|
> | `{{CHANNEL_E}}` | 文本 · 第五类渠道（通常是社区/CPS 型，与前面四家口径不同） |
> | `{{COMMUNITY_FORUM}}` | 文本 · 玩家讨论的**论坛/社区**名 |
> | `{{COMMUNITY_VIDEO}}` | 文本 · 玩家讨论的**视频社区**名 |
> | `{{GAME_CN}}` | 文本 · 游戏**中文官方全名**，不含版本号 |
> | `{{GAME_DATA_API}}` | 文本 · 游戏公开数据接口/服务名 |
> | `{{GAME_DATA_API_HOST}}` | 文本 · 该接口的域名 |
> | `{{GAME_KEYWORD}}` | 文本 · 代码里做搜索用的小写英文关键词 |
> | `{{SAMPLE_N}}` | 整数 · 有效样本量，须带口径 |
> | `{{SERVER_LINE_A}}` | 文本 · 主服线名称 |
> | `{{USER_ACCOUNT}}` | 文本 · 本机账户名（脚本里若出现） |
> | `{{WORK_DIR}}` | 路径 · 你的项目/输出目录 |

# 玩家群体数据洞察（采集 + 聚类分析）

**一句话**：把国内 {{GAME_CN}} 玩家的真实讨论采下来 → 自动聚成若干「玩家群体」→ 每个群体给出运营打法建议 → 出一份 HTML 报告。为渠道/社区运营方案提供**数据支撑**，替代拍脑袋。

**与其它 skill 的关系**：本 skill 是**数据洞察层**（回答"玩家是谁、在聊什么、分几群"）；
拿到群体画像后，用 `community-ops`（社区运营动作）、`content-brief`（内容选题）、
`channel-plan`（渠道方案）去承接。**先洞察后动作**。

---

## 零、最优路径（照这个顺序做，别跳步）

这是踩过坑总结的最短路径，**按序执行**：

1. **定目标**：先想清这次洞察要回答什么运营问题（如“回归用户在关注什么”“新手在哪个环节受阻”），
   决定 `SEARCH_KEYWORDS` 怎么铺。关键词铺得越开，群体覆盖越全。
2. **采集** `python -m wfci.cli collect`：{{COMMUNITY_VIDEO}}热评 + {{COMMUNITY_FORUM}}帖子 + {{GAME_DATA_API}}游戏数据 → `data/`。
   （{{COMMUNITY_FORUM}} 需 Playwright+chromium，没装会自动跳过，不影响 {{COMMUNITY_VIDEO}}/游戏数据）
3. **分析** `python -m wfci.cli analyze`：聚成 K 个群体 → `{{WORK_DIR}}/output/cluster_result.json`。
4. **看关键词调停用词**：若某群关键词里冒出虚词（"一个/是不是/发现"），加进 `config.STOPWORDS`
   → **只重跑 analyze**（几秒，不用重新采集）。
5. **出报告** `python -m wfci.cli report`：运营决策报告 → HTML。
6. **对接方案** `python -m wfci.cli export`：生成机器可读人群事实 + 与场景档 diff。
   要把洞察喂给渠道方案时走这步（见「五、洞察→方案对接」）。
7. **口径标注**：对外引用注明"{{COMMUNITY_VIDEO}}评论+{{COMMUNITY_FORUM}}帖子样本、声量口径"，别当人口普查。

> ⚡ 核心心法：**采集慢、分析快**。采集一次几分钟，分析几秒。
> 所以调参迭代永远只重跑 analyze/report，别反复 collect。

---

## 一、工具在哪、怎么跑

- 工具代码：`skills/A-用户研究与用户分析/audience-insight/wfci/`（Python 包）
- 运行环境：项目 venv `{{PYTHON_ENV}}`（填你自己的 Python 解释器目录，见 `_shared/config.example.yaml`）
  （已装 requests / scikit-learn / jieba / pandas / numpy / matplotlib / beautifulsoup4 / playwright）
  {{COMMUNITY_FORUM}} 采集还需浏览器内核：`playwright install chromium`
- **必须先切工作目录**：`cd tools/audience-insight`，否则 `python -m wfci.cli` 找不到包。

### 三条命令（+一条龙）

```bash
python -m wfci.cli collect   # 采集：{{COMMUNITY_VIDEO}}评论 + {{COMMUNITY_FORUM}}帖子 + {{GAME_DATA_API}}游戏数据 → data/
python -m wfci.cli analyze   # 聚类：TF-IDF+KMeans → {{WORK_DIR}}/output/cluster_result.json
python -m wfci.cli report    # 出报告：{{WORK_DIR}}/output/{{GAME_CN}}玩家群体洞察_YYYY-MM-DD.html
python -m wfci.cli export    # 洞察→方案对接：生成机器可读人群事实 + 与场景档diff
python -m wfci.cli all       # 一条龙：采集+分析+报告(无参数时默认跑 all)
```

---

## 二、数据源适配器

| 数据源 | 类型 | 免密钥 | 说明 |
|---|---|---|---|
| **{{COMMUNITY_VIDEO}}** 搜索+评论接口 | 玩家讨论 | 依平台而定 | 填写 API 域名与路径，并按公开响应结构调整字段映射 |
| **{{COMMUNITY_FORUM}}** `{{COMMUNITY_FORUM_SECTION}}` | 玩家讨论 | 依平台而定 | 填写板块代号，并按公开页面结构调整选择器与字段映射 |
| **{{GAME_DATA_API}}** {{GAME_DATA_API_HOST}} | 游戏公开摘要 | 依平台而定 | 默认关闭；仅接入已获授权的 `/summary` 兼容端点 |

两个社区源用于相互补充：一个提供评论声量，一个提供主题与讨论结构。采集器只是场景模板，
不承诺兼容任何特定平台。接入前必须确认接口许可、访问频率、隐私边界与数据留存要求；
不得绕过登录、验证码、付费墙或其他访问控制。

---

## 三、可调参数（改 `wfci/config.py`）

下表是**当前实际值**（热评模式），改完只重跑受影响的命令：

| 参数 | 当前值 | 含义 / 改动后重跑 |
|---|---|---|
| `SEARCH_KEYWORDS` | 9 个通用模板词（游戏名/攻略/新手/版本/活动/养成/回归/社交） | {{COMMUNITY_VIDEO}} 搜索关键词；按项目词表修改后重跑 collect |
| `MAX_VIDEOS_PER_KEYWORD` | 20 | 每关键词抓多少视频。改→重跑 collect |
| `MAX_COMMENTS_PER_VIDEO` | 20 | 每个内容项最多读取的评论数；不得超过平台授权范围 |
| `MAX_REPLIES_PAGES` | 2 | 评论分页上限；按平台公开接口能力调整 |
| `REQUEST_INTERVAL` | 1.2s | 请求间隔(**别调太小**，防风控封IP) |
| `CLUSTER_K` | 7 | 玩家分群数。改→重跑 analyze |
| `MIN_TEXT_LEN` | 6 | 短于此的评论丢弃 |
| `STOPWORDS` | 见文件(约147条) | 停用词。发现虚词混进关键词就加。改→只重跑 analyze |

**样本量口径(区分三个值，别混)**：候选内容数、原始评论/帖子数、清洗去重后的 `{{SAMPLE_N}}`
必须分别记录。是否达到可聚类规模应结合文本质量、主题分布与稳定性检验判断，不套用历史项目阈值。

---

## 四、聚类方案（轻量经典，已预留升级）

- **当前**：jieba 中文分词 → TF-IDF → KMeans → 每簇提取关键词/高赞代表评论。
  秒级出结果、零额外依赖、结果可解释。
- **语义升级(仅预留，尚未实现)**：目前只有 `analyze.embed_upgrade_available()` 探测函数 + 注释示例，
  **没有可切换的 embedding 聚类实现**。真要用需自行改造：`pip install sentence-transformers`，
  用 `paraphrase-multilingual-MiniLM-L12-v2` 做 embedding 再聚类。代价：首次下载数百MB模型、慢几倍。
  **当前 TF-IDF 轻量版够用，别急着上**。

**调参经验（重要）**：中文停用词要反复补——虚词（一个/是不是/发现/大家/de）极易混进关键词稀释主题。
发现就加进 `STOPWORDS`，只重跑 analyze。**拿不准的词别停**（可能正是玩家诉求词）。

---

## 五、运营解读（工具的核心价值）

报告定位是**运营决策工具**，不是画像展示。结构：一页看懂(TLDR) → 运营决策总览表 →
按【拉新/回流/留存】三目标拆解的可执行方案 → 数据附录。

每个玩家群体自动匹配四要素：**核心需求 + 运营目标(拉新/回流/留存) + 渠道资源活动打法**。
映射表在 `wfci/report.py` 的 `OPS_PLAYBOOK`，格式：
`触发关键词 → (人群名, 核心需求, 目标, 渠道打法)`。
**改运营建议就改这个字典**，不动分析逻辑。

**复合目标判定**：一个群体可能横跨多目标（如新手+社交=拉新+留存），按命中词的运营目标聚合打分，
取最高为主目标、次高为次要目标，报告里两者都体现，避免单一目标埋没其它信号。

**模板覆盖主题**：新手、攻略、回归、版本、角色、养成、战斗、活动、社交、付费、问题与流失；
阵营声望党、剧情版本党、退坑预警、进阶系统进阶党、活动福利党、社交公会党、交易游戏内货币党。
**新群体落到兜底"综合讨论群体"时，往字典补一条**。

> ⚠️ 占比 = 讨论声量，**不是**人口比例（发帖人≠全体玩家，热评偏高赞）。
> 目标归属受聚类粒度影响，是**方向参考**。回流玩家在公开社区天然声量小(不太发弹幕)，
> 实际召回要靠定向触达而非社区内容——这本身是给运营的真实结论。
> 对外引用必须标注"{{COMMUNITY_VIDEO}}评论+{{COMMUNITY_FORUM}}帖子样本、声量口径"。

---

## 六、洞察 → 渠道方案对接（export 命令）

把聚类结果直接变成渠道方案的机器可读输入，**替代手工搬运数字进场景档**。

```bash
python -m wfci.cli export
```

**做什么**：
1. 从 `cluster_result.json` 生成 `{{WORK_DIR}}/output/audience_export_<date>.json`——格式与
   `_shared/profiles/*.json` 的 `reality.audience_facts` **完全兼容**（cluster/label/
   share_pct/size/goal/keywords/guard），可直接喂给 `channel-plan` Step 0 选档。
2. 自动生成**护栏(guard)**：占比最大的群体提醒"它是回流不是拉新"、拉新声量小提醒"别夸大"。
3. **对比现有场景档，产出待确认 diff**——重采后新旧值并列，⚠️ **不静默覆盖 profile**。

**关键纪律（踩坑）**：
- **人群事实只认原始聚类字段**（cluster/size/share_pct/top_keywords）。
  报告里的"人群名/核心需求/打法"是 `OPS_PLAYBOOK` 模板生成的**仅供参考**，
  与准则 0.2 对齐——正式人群事实以 `cluster_result.json` / `audience_export` 为准。
- **重采后不自动回写 profile**：旧值可能是上一期基线。看 diff → 人工确认 → 手动回写。
- export 带**元数据**（时点/样本量/关键词集/K值），供 `plan-lint` 的 REALITY-02
  （声量≠人口）与口径溯源引用。

**下游怎么用**：`channel-plan` 模块2「人群与场景」读 profile 的 `reality.audience_facts`；
`campaign-retro` 复盘时引用活动前后两份 export 对比声量/诉求变化。

---

## 七、红线（沿用项目公约，硬红线不随场景变）

1. **样本口径诚实**：报告注明数据来源与口径，声量不冒充人口。
2. **频率克制**：`REQUEST_INTERVAL` 不得小于目标平台允许值；只采获准访问的数据。
3. **合规**：遵守平台条款、robots 约束、隐私要求与数据保留政策；模板不包含绕过访问控制的实现。
4. **不外泄敏感**：外发报告前确认无内部预算/权重/KPI 拆解（本报告默认不含，别手动加）。
5. **html 外发**：对外一律出自包含版（本报告已内联CSS，天然自包含）。

---

## 八、常见问题

- **搜索或评论为空**：先核对配置端点、公开接口权限和字段映射，不要通过规避访问控制来补数据。
- **字段解析失败**：按目标平台公开响应结构调整 `collect_video.py` / `collect_forum.py` 的适配层。
- **聚类全堆在一个群**：样本太少或停用词不够。加大 `MAX_VIDEOS_PER_KEYWORD` + 补 `STOPWORDS`。
- **关键词里出现虚词**：往 `STOPWORDS` 加，只重跑 analyze。
- **新群体没匹配到运营建议**：往 `report.py` 的 `OPS_PLAYBOOK` 补一条。
- **{{COMMUNITY_FORUM}} 采集报错/空**：确认已安装浏览器依赖，并检查页面选择器是否仍匹配公开页面结构。

---

## 九、模板边界

- 已验证的是本地分析、报告生成与 export 数据契约；在线采集适配器必须由使用方针对获准的数据源完成配置与验证。
- 不保存登录凭据，不内置第三方平台标识，不包含绕过签名、验证码或访问控制的逻辑。
- 需要语义聚类或新增数据源时，先单独评估依赖许可证、平台条款、数据最小化与部署成本。
