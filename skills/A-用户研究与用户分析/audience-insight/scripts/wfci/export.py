"""洞察 → 渠道方案对接：把 cluster_result.json 转成机器可读的人群事实，
供 _shared 场景档(profiles/*.json) 的 reality.audience_facts 使用。

设计原则(踩坑总结)：
- 产出「待确认 diff」而非静默覆盖 profile——重采后新旧值并列，人工确认再回写。
- 人群事实只认原始聚类字段(cluster/size/share_pct/top_keywords)，打法文本仅供参考
  (与准则 0.2 对齐：报告里的人群名/打法是模板生成，不作验收依据)。
- 每份导出带元数据(时点/样本量/关键词集/K值)，供口径溯源与 plan-lint 引用。

用法：python -m wfci.cli export
产出：{{WORK_DIR}}/output/audience_export_<date>.json (机器可读) + 终端打印待确认 diff
"""
import json
import datetime
import difflib

from . import config
from . import analyze, report


def _build_audience_facts(cluster_result):
    """把聚类结果转成 profile 兼容的 audience_facts 列表。"""
    facts = []
    for p in sorted(cluster_result["profiles"],
                    key=lambda x: x["size"], reverse=True):
        name, need, goal, play, sub = report._match_playbook(p["top_keywords"])
        facts.append({
            "cluster": p["cluster"],
            "label": name,
            "share_pct": p["share_pct"],
            "size": p["size"],
            "goal": goal,
            "keywords": "/".join(p["top_keywords"][:7]),
            # guard 由规则生成：占比最大的群体提醒别误当拉新、拉新声量小别夸大
            "guard": _auto_guard(p, name, goal),
        })
    # 目标声量合计
    share = {}
    for f in facts:
        share[f["goal"]] = round(share.get(f["goal"], 0) + f["share_pct"], 1)
    return facts, share


def _auto_guard(p, name, goal):
    """按数据特征自动生成护栏(避免把声量当人口、把小群体夸大)。"""
    guards = []
    if p["share_pct"] == max(x["share_pct"] for x in _ALL_PROFILES):
        if goal != "拉新":
            guards.append(f"{name}声量最大，但它是{goal}不是拉新，别写成拉新主力")
    if goal == "拉新" and p["share_pct"] < 10:
        guards.append(f"拉新声量仅{p['share_pct']}%，不能声称「萌新是最大群体」")
    if not guards:
        guards.append(f"{name}占讨论声量{p['share_pct']}%(非人口比例)")
    return "；".join(guards)


_ALL_PROFILES = []   # 供 _auto_guard 判断最大群体(在 export 时填充)


def export(progress_cb=None):
    """主入口：读 cluster_result → 生成 audience_facts + 待确认 diff。"""
    global _ALL_PROFILES
    src = config.OUT_DIR / "cluster_result.json"
    if not src.exists():
        raise FileNotFoundError("先跑 analyze 生成 cluster_result.json")
    cr = json.loads(src.read_text(encoding="utf-8"))
    _ALL_PROFILES = cr["profiles"]

    facts, share = _build_audience_facts(cr)
    today = str(datetime.date.today())

    out = {
        "meta": {
            "exported_at": today,
            "source": f"skills/A-用户研究与用户分析/audience-insight/output/cluster_result.json"
                      f"（{cr['n_samples']} 条，{cr['n_clusters']} 簇，{today}）",
            "n_samples": cr["n_samples"],
            "n_clusters": cr["n_clusters"],
            "cluster_k": config.CLUSTER_K,
            "source_dist": cr.get("source_dist", {}),
            "note": "讨论声量占比，非人口比例；回流玩家公开社区声量天然小。"
                    "引用须标样本量与时点。打法文本仅供参考，正式人群事实以本文件 cluster/size/share_pct 为准。",
        },
        "group_share_pct": share,
        "audience_facts": facts,
        "playbook_guard": _top_guards(facts),
    }

    # 落盘(带日期，不覆盖历史)
    path = config.OUT_DIR / f"audience_export_{today}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    if progress_cb:
        progress_cb(f"[导出] 机器可读人群事实 → {path}")

    # 生成与现有 profile 的待确认 diff
    diff = _diff_against_profile(out, progress_cb)
    return out, diff


def _top_guards(facts):
    """汇总全局护栏(给 plan-lint 的 REALITY-02 用)。"""
    guards = []
    top = facts[0] if facts else None
    if top and top["goal"] != "拉新":
        guards.append(f"别把「{top['label']}」写成拉新主力——它是{top['goal']}群体")
    laxin = [f for f in facts if f["goal"] == "拉新"]
    if laxin and laxin[0]["share_pct"] < 10:
        guards.append(f"拉新声量仅 {laxin[0]['share_pct']}%，不能声称「萌新是最大群体」")
    guards.append("人群四层 CTR 是 {{GAME_CN}} 实测 B 级，引用须标「参考值，待使用方项目验证」")
    return guards


def _diff_against_profile(new_out, progress_cb=None):
    """对比现有场景档 profile 里的 audience_facts，产出待确认差异。
    不静默覆盖——只打印新旧并列，人工确认后再回写 profile。"""
    profile_path = (config.PROJECT_DIR if hasattr(config, "PROJECT_DIR")
                    else config.TOOL_DIR.parent.parent) / \
        "_shared/profiles/channel_prebook.json"
    if not profile_path.exists():
        if progress_cb:
            progress_cb("[导出] 未找到 channel_prebook.json，跳过 diff")
        return None
    old = json.loads(profile_path.read_text(encoding="utf-8"))
    old_facts = {f["cluster"]: f for f in old.get("reality", {}).get("audience_facts", [])}
    new_facts = {f["cluster"]: f for f in new_out["audience_facts"]}

    changes = []
    for cid in sorted(set(old_facts) | set(new_facts)):
        o, n = old_facts.get(cid), new_facts.get(cid)
        if o and n:
            if abs(o.get("share_pct", 0) - n.get("share_pct", 0)) > 0.5 \
               or o.get("label") != n.get("label"):
                changes.append(f"  簇{cid} {o.get('label')}({o.get('share_pct')}%) "
                               f"→ {n.get('label')}({n.get('share_pct')}%)")
        elif n and not o:
            changes.append(f"  簇{cid} [新增] {n.get('label')}({n.get('share_pct')}%)")
        elif o and not n:
            changes.append(f"  簇{cid} [消失] {o.get('label')}({o.get('share_pct')}%)")

    diff = {
        "profile": str(profile_path.relative_to(config.TOOL_DIR.parent.parent))
        if profile_path.is_relative_to(config.TOOL_DIR.parent.parent)
        else str(profile_path),
        "has_changes": bool(changes),
        "changes": changes,
        "hint": "以上为重采后与场景档的差异。确认无误后手动回写 profile 的 reality.audience_facts，"
                "勿静默覆盖(旧值可能是上一期基线)。",
    }
    if progress_cb:
        if changes:
            progress_cb("[导出] ⚠️ 与现有场景档存在差异(待人工确认，未自动回写)：")
            for c in changes:
                progress_cb(c)
        else:
            progress_cb("[导出] 与现有场景档一致，无需回写")
    return diff


if __name__ == "__main__":
    export(lambda m: print(m))
