# {{TABLE_TOOL}} / {{DOC_TOOL}}操作要点与已知坑


> **本文件用到的占位符**（每个该填哪类信息、能不能外发，详见 `01-占位符字典.md`）
>
> | 占位符 | 该填哪类信息 |
> |---|---|
> | `{{BENCHMARK_GAME_C}}` | 文本 · 同品类**历史参照游戏**，用于引用 CTR 之类的参考值 |
> | `{{COLLAB_PLATFORM}}` | 文本 · 团队协作平台称谓 |
> | `{{DOC_TOOL}}` | 文本 · 你团队用的**在线文档工具** |
> | `{{DOC_TOOL_PAGE}}` | 文本 · 文档工具里「页面/文档」的对象叫法 |
> | `{{SAMPLE_RECORDS}}` | 整数 · 投放记录**行数** |
> | `{{TABLE_TOOL}}` | 文本 · 你团队用的**在线表格工具** |
> | `{{TABLE_TOOL_CLI}}` | 文本 · 操作在线表格的**命令行工具名**；换工具就换这里 |

命令走 `{{TABLE_TOOL_CLI}}`（{{COLLAB_PLATFORM}}连接器）。执行前确认连接器已连接；协议要求：读写前先读子表/字段列表，参数名 `docid` 全小写。

## 取数

```bash
{{TABLE_TOOL_CLI}} smartsheet sheets list --json '{"docid": "<docid>"}'
{{TABLE_TOOL_CLI}} smartsheet records query --docid '<docid>' --sql 'SELECT `字段` FROM `子表` GROUP BY `字段` LIMIT 100'
{{TABLE_TOOL_CLI}} smartsheet fields list --json '{"docid": "<docid>", "sheet_title": "<子表>", "limit": 50}'
```

SQL 能力边界：**不支持** 子查询、窗口函数、UNION、COALESCE、CAST；**支持** GROUP BY / HAVING / COUNT(DISTINCT) / SUM / CASE WHEN / LIKE / DATE_FORMAT。
日期字段在 SQL 里是 Excel 序列号，分组统计必须用 `DATE_FORMAT(字段, "%Y-%m")`。
URL 字段返回 dict，取 `url` 或 `text`。

## 写入打标子表

```bash
{{TABLE_TOOL_CLI}} smartsheet sheets add --json '{"docid":"...","sheet_title":"{{BENCHMARK_GAME_C}}素材打标","fields":[...]}'
{{TABLE_TOOL_CLI}} smartsheet records add --json '{"docid":"...","sheet_title":"...","records":[{"values":{...}}]}'
{{TABLE_TOOL_CLI}} smartsheet views update --json '{"docid":"...","sheet_title":"...","type":"update","views":[{"view_id":"...","col_infos":[...]}]}'
```

- 单选/多选写入格式：`[{"text": "选项文本"}]`（不必传 id）
- 日期写 `"YYYY-MM-DD 00:00:00"`；百分比写小数（0.0123）
- **新建字段后必须设置列宽**（规范强制），`col_infos` 传 `field_title` + `width`

## 已知坑（都踩过）

| 坑 | 表现 / 解决 |
| --- | --- |
| 命令行超长 | `records update` 一次提交 {{SAMPLE_RECORDS}} 条报 `WinError 206`；按 **80 条/批**拆分提交 |
| 单次提交体积超限 | `{{DOC_TOOL_PAGE}} pages append` 报 `640463`；长表按 **25 行/块**拆成多个文件分批追加 |
| 图片缓存去重 | 同一张图第二次 Read 返回 "unchanged" 看不到内容；复制文件并在 JPEG 头插入 COM 段（0xFFFE + 2字节长度 + 内容）生成副本再读 |
| 内置数据表 | {{DOC_TOOL}}的表格要用 `{{DOC_TOOL_PAGE}} databases get` 拿内置库 docid，不要另建独立{{TABLE_TOOL}}，否则不挂在文档里 |
| 字段顺序 | 新字段只能追加到末尾，无法插入指定位置 |
| bash 反引号 | 在 bash 里生成 Markdown 时反引号会被命令替换吃掉；写 md 用 Write 工具 |
| 选项被覆盖 | `fields update` 传 `property_single_select` 时必须包含**全部**选项，否则旧选项丢失 |
| replace 后 id 失效 | `blocks update replace` 返回 `new_block_id`，旧 id 再用会静默失败（status=None）→ 重拉块列表 |
| mdx 百分号 | Python 格式化 mdx 时字面 `%` 要写成 `%%`，否则 `1.0%（占` 报错 |
| mdx 空锚点 | `[第六节](#)` 渲染成乱码「△」，提示文字不用空链接 |
| 表格解析 | 智能页 markdown 的表格是 HTML `<table>`，要用 `<tr><td>` 正则统计，不能用管道符正则 |

## {{DOC_TOOL}}

```bash
{{TABLE_TOOL_CLI}} {{DOC_TOOL_PAGE}} import --json '{"name":"标题","file_path":"绝对路径.md"}'     # 从零建文档
{{TABLE_TOOL_CLI}} {{DOC_TOOL_PAGE}} pages get --json '{"docid":"...","page_id":"...","content_type":"block"}'
{{TABLE_TOOL_CLI}} {{DOC_TOOL_PAGE}} pages append --json '{"docid":"...","page_id":"...","content_type":"markdown","file_path":"..."}'
{{TABLE_TOOL_CLI}} {{DOC_TOOL_PAGE}} blocks update --json '{"docid":"...","page_id":"...","method":"replace","block_id":"...","mdx":"..."}'
```

- `page_id`、`block_id` 必须从回包取，禁止构造
- 修改局部内容用 `blocks update`，**禁止**用 overwrite 做局部替换
- 输出给用户的链接格式：`URL?_fid=<docid>`

### 读取时的两种返回

| `content_type` | 内容位置 |
| --- | --- |
| `markdown` | `pages[0].content_file_inner`（字符串，可直接存 .md） |
| `block` | `pages[0].file_path`（本地 JSON 路径，内容是平铺块数组） |

块对象字段：`id` / `type`（`header_1`/`header_2`/`text`/`bulleted_list`/`numbered_list`/`unspecified`=表格）/ `parent_id` / `property.title.text`。
表格块常表现为 `unspecified`，且与 `header_3` 小标题交替出现，取 id 前务必打印 type + 文本核对。

### blocks update 三个方法

```bash
# 替换（返回 new_block_id，原 id 立即失效）
... "method":"replace","block_id":"<id>","mdx":"## 新内容"
# 插入
... "method":"insertAfter","block_id":"<id>","mdx":"..."      # 或 insertBefore
# 删除（数组批量）
... "method":"delete","block_ids":["<id1>","<id2>"]
# 追加到文档末尾
... "method":"append","mdx":"..."
```

⚠️ **replace 后必须重新拉块列表**：新插入/替换产生的 id 与旧 id 不同，用旧 id 继续操作会静默失败（status 为 None 且不报错）。
批量改文档时分脚本执行：先跑删除+替换，重拉块，再跑插入。

更多对齐/去旧的完整流程与校验清单见 `doc-sync.md`。
