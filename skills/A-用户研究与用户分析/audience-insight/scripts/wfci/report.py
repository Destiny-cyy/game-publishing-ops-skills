"""生成 HTML 运营洞察报告：把聚类结果 + 游戏数据 + 视频热度整合成可视化页面。
纯静态单文件(内联CSS)，可直接外发。遵循项目 html 外发公约：无外部依赖。
"""
import html
import datetime
from . import config

# 通用玩家主题 → 运营动作映射。使用前应按目标游戏词表审阅和扩展。
# 每条：触发关键词 → (人群名, 核心需求, 拉新/回流/留存归属, 建议动作)
OPS_PLAYBOOK = {
    "新手": ("新用户", "入门引导与首日体验", "拉新",
             "完善落地页引导、入门内容和低门槛任务，并验证首日关键路径"),
    "入门": ("新用户", "入门引导与目标感", "拉新",
             "提供从零开始的内容入口，并减少首次体验中的流程阻碍"),
    "攻略": ("内容需求用户", "可执行的玩法与流程说明", "留存",
             "按问题类型制作攻略内容，并用搜索和完成数据验证是否解决问题"),
    "回归": ("回流用户", "版本变化与低门槛回归", "回流",
             "提供版本速览、回归路径和适度激励，并记录召回后的留存"),
    "版本": ("版本关注用户", "版本变化和新内容信息", "回流",
             "按节点提供版本信息和内容导航，避免把声量直接等同于转化"),
    "角色": ("角色偏好用户", "角色信息与养成选择", "留存",
             "提供角色主题内容和用户创作活动，结论须按实际游戏系统校正"),
    "养成": ("成长效率用户", "成长路径与资源效率", "留存",
             "提供成长路径说明并识别资源卡点，不直接承诺未核实的补偿"),
    "战斗": ("玩法深度用户", "玩法策略和操作提升", "留存",
             "提供进阶玩法内容和可验证的挑战活动"),
    "活动": ("活动/福利党", "游戏内活动福利(触达敏感)",
             "拉新", "①福利预告/限时活动提醒内容位；②福利型活动覆盖泛用户"),
    "社交": ("社交/公会党", "组队/公会/找搭子(留存粘性)",
             "留存", "①公会招募/组队活动(粘性最强)；②渠道做公会道场活动聚拢公会"),
    "付费": ("付费关注用户", "价值感、价格与权益透明度", "留存",
             "解释权益与规则，监测投诉和退款信号，不把付费直接等同于忠诚"),
    "问题": ("体验受阻用户", "故障、流程或理解障碍", "留存",
             "将问题分级并回传责任方，提供状态更新和可复现证据"),
    "流失": ("流失风险用户", "流失原因与召回条件", "回流",
             "先研究流失原因，再测试低成本召回动作并跟踪回流留存"),
}

# 强人群信号词：明确指向某类玩家，命中权重 ×2，
# 用以压过「版本」等泛化主题词，保证人群名与 top_keywords 对得上。
STRONG_SIGNALS = {"新手", "入门", "回归", "流失", "攻略", "问题"}
STRONG_WEIGHT = 2


def _match_playbook(keywords):
    """按『逐词精确包含』打分选最贴切的群体。
    返回 (人群名, 核心需求, 运营目标, 渠道资源打法, 次要目标或None)。
    对每个 playbook key，统计有多少个 top_keyword 包含该 key 就计多少分
    (同一个词对同一个 key 最多计 1 分)，不再拼接字符串后做子串计数。
    强人群信号词权重 ×2；同分时取触发词在 top_keywords 中最靠前的人群
    (列表越靠前越代表该簇主题)，保证结果确定且名称与关键词一致。"""
    name_score = {}      # 人群名 -> 加权累计命中分
    name_first = {}      # 人群名 -> 其触发词在 keywords 中最早出现的位置
    name_val = {}        # 人群名 -> 该人群的 (name, need, goal, play)
    for kw, val in OPS_PLAYBOOK.items():
        w = STRONG_WEIGHT if kw in STRONG_SIGNALS else 1
        for i, tk in enumerate(keywords):
            if kw in tk:                 # 逐词精确包含判断，非子串计数
                nm = val[0]
                name_score[nm] = name_score.get(nm, 0) + w
                name_first[nm] = min(name_first.get(nm, i), i)
                name_val.setdefault(nm, val)
    if not name_score:
        return ("综合讨论群体", "讨论主题分散，泛用户触达", "拉新",
                "通用福利型活动覆盖泛用户，用资源位+CDK做广覆盖", None)
    # 主人群 = 加权分最高者；同分取关键词最靠前者(人群与目标绑定，不错配)
    best_name = max(name_score,
                    key=lambda nm: (name_score[nm], -name_first[nm]))
    val = name_val[best_name]
    main_goal = val[2]
    # 次要目标 = 其余命中人群里分最高者的目标(与主目标不同才记)
    sub_goal = None
    others = [(nm, sc) for nm, sc in name_score.items()
              if nm != best_name and name_val[nm][2] != main_goal]
    if others:
        sub_goal = name_val[max(others, key=lambda x: x[1])[0]][2]
    return val[0], val[1], main_goal, val[3], sub_goal


def _esc(s):
    return html.escape(str(s))


def build(cluster, game, videos):
    n_samples = cluster.get("n_samples", 0)
    n_clusters = cluster.get("n_clusters", 0)
    profiles = cluster.get("profiles", [])
    src = cluster.get("source_dist", {})
    tag_dist = cluster.get("forum_tag_dist", {})
    # 统一口径说明：报告内所有占比均为讨论声量占比，非人口比例
    sample_note = f"讨论声量占比，非人口比例，样本 {n_samples} 条"

    # {{COMMUNITY_FORUM}} 官方分类标签分布(玩家诉求类型)——{{COMMUNITY_FORUM}}独有，{{COMMUNITY_VIDEO}}没有
    forum_html = ""
    if tag_dist:
        total_tags = sum(tag_dist.values()) or 1
        bars = "".join(
            f"<div class='trow'><span class='tname'>{_esc(t)}</span>"
            f"<span class='tbar'><span style='width:{round(100*c/total_tags)}%'></span></span>"
            f"<span class='tnum'>{c} ({round(100*c/total_tags)}%)</span></div>"
            for t, c in tag_dist.items())
        forum_html = f"""
        <div class="card">
          <h3>🏷️ {{COMMUNITY_FORUM}} 帖子诉求分类 <span class="muted">(官方标签，玩家诉求类型)</span></h3>
          <p class="muted">{{COMMUNITY_FORUM}} 帖子自带官方分类标签，直接反映玩家在"求助/吐槽/攻略/讨论"什么。
          这是 {{COMMUNITY_VIDEO}}没有的信号——求助多=痛点、吐槽多=风险、攻略多=内容需求。</p>
          {bars}
        </div>"""

    # 视频热度Top
    vids_sorted = sorted(videos, key=lambda v: v.get("play", 0), reverse=True)[:8]
    vid_rows = "".join(
        f"<tr><td>{_esc(v['title'][:38])}</td><td>{v.get('play',0):,}</td>"
        f"<td>{v.get('reply',0):,}</td></tr>"
        for v in vids_sorted)

    # 可选游戏数据摘要
    ws = (game or {}).get("summary", {})
    game_html = ""
    if ws and not ws.get("disabled") and not ws.get("error"):
        news = ws.get("news_headlines") or []
        game_html = f"""
        <div class="card">
          <h3>🎮 游戏侧摘要 <span class="muted">(可选通用 API 适配器)</span></h3>
          <p>当前版本：<b>{_esc(ws.get('version','?'))}</b> ｜
             活动事件 {_esc(ws.get('active_events',0))}</p>
          <p class="muted">近期公开信息：</p>
          <ul>{''.join(f'<li>{_esc(n)}</li>' for n in news[:5])}</ul>
        </div>"""

    # ---- 运营决策核心：给每个群体配 (需求/目标/渠道打法)，按目标分组 ----
    GOAL_ORDER = ["拉新", "回流", "留存"]
    GOAL_META = {
        "拉新": ("🚀 拉新（获取新玩家/潜在用户）", "#2563eb",
                 "把没玩过/刚听说的人拉进来。渠道重点：落地页引导、预约/一键入库任务、新人礼包、入门内容位。"),
        "回流": ("🔄 回流（召回流失/回坑玩家）", "#d97706",
                 "把不玩的人拉回来。渠道重点：回坑礼包、版本速览、低门槛回归奖励、新版本钩子。"),
        "留存": ("💎 留存（留住现有玩家）", "#16a34a",
                 "改善现有用户的内容、成长与社交体验，并用留存指标验证运营动作。"),
    }
    # 每个群体解析出三要素(+次要目标)
    enriched = []
    for p in profiles:
        name, need, goal, play, sub = _match_playbook(p["top_keywords"])
        enriched.append({"p": p, "name": name, "need": need,
                         "goal": goal, "play": play, "sub": sub})

    # ---- TLDR 动态结论(重采后自动更新，不写死) ----
    tldr_lines = []
    # 1. 最大声量群体(动态取最大簇，不写死人群组合与占比这类硬编码断言)
    if enriched:
        top = max(enriched, key=lambda x: x["p"]["size"])
        tldr_lines.append(
            f"<b>讨论声量最大的群体是「{top['name']}」(占 {top['p']['share_pct']}%)</b> "
            f"→ 核心需求：{top['need']}；对应运营目标「{top['goal']}」，按该目标配渠道资源。")
    # 2. {{COMMUNITY_FORUM}} 官方分类标签 Top(真实计算，不写死某标签居首的硬编码断言；
    #    分母为标签计数总和，不是 {{COMMUNITY_FORUM}} 帖子数)
    if tag_dist:
        tt = sorted(tag_dist.items(), key=lambda x: x[1], reverse=True)
        top_tag, top_n = tt[0]
        total_tag = sum(tag_dist.values()) or 1
        tag_hint = {"求助": "玩家痛点集中，是渠道活动最该切的点",
                    "吐槽": "存在不满情绪，需关注风险并做口碑维护",
                    "攻略": "内容需求强，可做攻略型内容位",
                    "讨论": "话题活跃，适合做互动型活动",
                    "{{SERVER_LINE_A}}": "{{SERVER_LINE_A}}相关帖子数量居首，反映该板块讨论集中"}.get(
            top_tag, "反映玩家当前主要诉求方向")
        others = "、".join(f"{t}({c})" for t, c in tt[1:4])
        tldr_lines.append(
            f"<b>{{COMMUNITY_FORUM}}官方分类标签中「{top_tag}」最多({top_n}/{total_tag}个标签)</b> "
            f"→ {tag_hint}。其余：{others}。")
    # 3. 各运营目标声量分布
    gc = {}
    for e in enriched:
        gc[e["goal"]] = gc.get(e["goal"], 0) + e["p"]["share_pct"]
    if gc:
        dist = "、".join(f"{g}{round(v,1)}%" for g, v in
                        sorted(gc.items(), key=lambda x: x[1], reverse=True))
        tldr_lines.append(
            f"<b>运营目标讨论声量占比分布：{dist}</b> → 按占比分配渠道资源预算。")

    # 决策总览表(按占比排序)
    overview_rows = ""
    for e in sorted(enriched, key=lambda x: x["p"]["size"], reverse=True):
        p = e["p"]
        gcolor = GOAL_META[e["goal"]][1]
        sub_html = (f" <span class='muted'>+次:{_esc(e['sub'])}</span>"
                    if e["sub"] else "")
        overview_rows += (
            f"<tr><td><b>{_esc(e['name'])}</b><br><span class='muted'>"
            f"{p['share_pct']}% · {p['size']}条</span></td>"
            f"<td>{_esc(e['need'])}</td>"
            f"<td><span class='goal' style='background:{gcolor}'>{_esc(e['goal'])}</span>{sub_html}</td>"
            f"<td>{_esc(e['play'])}</td></tr>")

    # 按目标分组的可执行方案卡片(主目标计入，次要目标也以轻量形式出现)
    goal_sections = ""
    for goal in GOAL_ORDER:
        group = [e for e in enriched if e["goal"] == goal]
        # 次要目标命中此组的群体，追加为轻量条目
        sub_only = [e for e in enriched
                    if e["goal"] != goal and e["sub"] == goal]
        if not group and not sub_only:
            continue
        gtitle, gcolor, gdesc = GOAL_META[goal]
        # 该目标下的群体按占比降序
        group.sort(key=lambda x: x["p"]["size"], reverse=True)
        total_share = round(sum(e["p"]["share_pct"] for e in group), 1)
        items_html = ""
        for e in group:
            p = e["p"]
            kws = " ".join(f"<span class='tag'>{_esc(k)}</span>"
                           for k in p["top_keywords"][:6])
            samples = "".join(f"<li>「{_esc(s)}」</li>"
                              for s in p["sample_comments"][:2])
            items_html += f"""
            <div class="gitem">
              <div class="ghead"><b>{_esc(e['name'])}</b>
                <span class="muted">{p['share_pct']}% · {p['size']}条 · 均赞{p['avg_like']}</span></div>
              <div class="tags">{kws}</div>
              <p class="need"><b>玩家需求：</b>{_esc(e['need'])}</p>
              <div class="play"><b>📐 渠道资源活动打法：</b>{_esc(e['play'])}</div>
              <ul class="samples">{samples}</ul>
            </div>"""
        # 次要目标命中的群体：轻量提示(它们主目标是别的，但也能服务本目标)
        if sub_only:
            sub_list = "、".join(
                f"{_esc(e['name'])}({e['p']['share_pct']}%)"
                for e in sorted(sub_only, key=lambda x: x["p"]["size"], reverse=True))
            items_html += (
                f"<p class='muted' style='margin-top:12px'>↳ 另有 <b>{sub_list}</b> "
                f"群体也可顺带服务本目标(其主目标见对应分组)。</p>")
        goal_sections += f"""
        <div class="card">
          <h3 style="border-left:4px solid {gcolor};padding-left:10px">{_esc(gtitle)}
            <span class="muted">合计声量 {total_share}%</span></h3>
          <p class="muted">{_esc(gdesc)}</p>
          {items_html}
        </div>"""

    today = datetime.date.today()
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{GAME_CN}} 玩家需求洞察 × 渠道运营决策</title>
<style>
  body{{font-family:"Microsoft YaHei",-apple-system,sans-serif;margin:0;background:#f4f6fa;color:#1f2733;line-height:1.7}}
  .wrap{{max-width:1000px;margin:0 auto;padding:32px 20px}}
  h1{{font-size:26px;margin:0 0 4px}}
  .sub{{color:#6b7684;margin-bottom:24px}}
  .summary{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}}
  .stat{{background:#fff;border-radius:12px;padding:14px 18px;flex:1;min-width:120px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
  .stat .n{{font-size:26px;font-weight:700;color:#2563eb}}
  .stat .l{{color:#6b7684;font-size:13px}}
  .card{{background:#fff;border-radius:12px;padding:20px 22px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
  .card h3{{margin:0 0 10px}}
  .muted{{color:#6b7684;font-size:13px}}
  table{{width:100%;border-collapse:collapse;font-size:13.5px}}
  th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid #eef0f4;vertical-align:top}}
  th{{color:#6b7684;font-weight:600;background:#f8fafc}}
  .goal{{display:inline-block;color:#fff;border-radius:6px;padding:2px 10px;font-size:12px;font-weight:600}}
  .tags{{margin:8px 0}}
  .tag{{display:inline-block;background:#eef2ff;color:#4338ca;border-radius:6px;padding:2px 9px;margin:2px 4px 2px 0;font-size:12px}}
  .gitem{{border-top:1px solid #f0f2f6;padding:14px 0}}
  .gitem:first-child{{border-top:none}}
  .ghead{{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap}}
  .need{{font-size:14px;margin:6px 0}}
  .play{{background:#f0f9f4;border-radius:8px;padding:10px 14px;margin:8px 0;font-size:14px}}
  .samples{{color:#6b7684;font-size:13px;margin:6px 0 0}}
  .tldr{{background:linear-gradient(135deg,#eef2ff,#f0f9f4);border-radius:12px;padding:18px 22px;margin-bottom:20px;border:1px solid #e0e7ff}}
  .tldr h3{{margin:0 0 8px;color:#3730a3}}
  .tldr ol{{margin:8px 0 0;padding-left:20px;font-size:14px}}
  .tldr li{{margin:4px 0}}
  .trow{{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:14px}}
  .tname{{width:64px;color:#4338ca;font-weight:600;text-align:right}}
  .tbar{{flex:1;background:#eef0f4;border-radius:5px;height:16px;overflow:hidden}}
  .tbar span{{display:block;height:100%;background:linear-gradient(90deg,#6366f1,#4338ca)}}
  .tnum{{width:88px;color:#6b7684;font-size:13px}}
  .foot{{color:#9aa4b2;font-size:12px;margin-top:28px;text-align:center}}
  details{{margin-top:8px}}
  summary{{cursor:pointer;color:#2563eb;font-size:14px}}
</style></head>
<body><div class="wrap">
  <h1>{{GAME_CN}} 玩家需求洞察 × 渠道运营决策</h1>
  <div class="sub">数据来源：{{COMMUNITY_VIDEO}}评论 {src.get('{{COMMUNITY_VIDEO_HOST}}',0)}条 + {{COMMUNITY_FORUM}}帖子 {src.get('community_forum',0)}条 + {{GAME_DATA_API}}官方游戏数据 ｜ 生成日期 {today} ｜ {sample_note}</div>

  <div class="summary">
    <div class="stat"><div class="n">{n_samples}</div><div class="l">有效样本</div></div>
    <div class="stat"><div class="n">{n_clusters}</div><div class="l">玩家群体</div></div>
    <div class="stat"><div class="n">{len(videos)}</div><div class="l">相关视频</div></div>
    <div class="stat"><div class="n">3</div><div class="l">运营目标(拉新/回流/留存)</div></div>
  </div>

  <div class="tldr">
    <h3>📋 一页看懂：运营该怎么做</h3>
    <ol>
      {''.join(f'<li>{ln}</li>' for ln in tldr_lines)}
      <li><b>渠道资源活动主线</b>：拉新、回流、留存分别使用独立目标和指标；动作由当前平台能力与真实人群证据决定。</li>
    </ol>
    <p class="muted" style="margin-top:10px">⚠️ 全文占比均为<b>讨论声量占比，非人口比例，样本 {n_samples} 条</b>；目标归属按讨论关键词自动判定，回流/拉新声量占比受聚类粒度影响，是<b>方向参考</b>而非精确人口比例。回流玩家在公开社区天然声量小(不太发弹幕)，实际召回要靠定向触达而非社区内容。</p>
  </div>

  <div class="card">
    <h3>🎯 运营决策总览表 <span class="muted">(玩家需求 → 目标 → 渠道资源打法 ｜ 占比为{sample_note})</span></h3>
    <table>
      <tr><th style="width:16%">玩家群体</th><th style="width:22%">核心需求</th><th style="width:10%">运营目标</th><th>渠道资源活动打法</th></tr>
      {overview_rows}
    </table>
  </div>

  <h2 style="font-size:20px;margin:28px 0 12px">按运营目标拆解的可执行方案 <span class="muted" style="font-size:13px;font-weight:400">(各组「合计声量」为{sample_note})</span></h2>
  {goal_sections}

  <details class="card">
    <summary>📊 数据附录：游戏侧状态 / {{COMMUNITY_FORUM}}诉求标签 / 热门视频（点开查看）</summary>
    {game_html}
    {forum_html}
    <div style="margin-top:16px">
      <h3>🔥 热门相关视频 <span class="muted">(播放量Top8)</span></h3>
      <table><tr><th>标题</th><th>播放</th><th>评论</th></tr>{vid_rows}</table>
    </div>
  </details>

  <div class="foot">本报告由 audience-insight 工具自动生成 · 占比=讨论声量占比，非人口比例，样本 {n_samples} 条 · 数据仅供运营策略参考 · 请遵守各平台条款</div>
</div></body></html>"""
