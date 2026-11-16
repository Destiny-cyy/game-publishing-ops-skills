#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
方案出稿体检：扫方案（md / html），输出违反准则的问题清单。

v2.0（{{AS_OF_DATE}}）改为场景驱动：
  - 硬红线（内容/数据纪律/交付）全局恒真，任何场景都查
  - 渠道、指标、价带、份数、排期锚点、风险、脱敏词全部从 profile 取
  - 换业务背景/平台＝换一个 --profile，不再拿一个方案的参数套所有方案

用法：
  python lint_plan.py <方案.html> --profile channel_prebook
  python lint_plan.py <方案.html> <执行与风险.md>      # 多文件一起（锚点互认）
  python lint_plan.py <文件> --profile community_cps    # {{CHANNEL_E}}场景
  python lint_plan.py --list-profiles                   # 看有哪些场景档
  python lint_plan.py <文件> --summary / --only error / --external

退出码：0 = 通过（无 ERROR）；1 = 有 ERROR；2 = 出错
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_DIR = os.path.join(HERE, "..", "..", "..", "..", "_shared")
sys.path.insert(0, os.path.abspath(RULES_DIR))
from profile_loader import (load_rules, load_profile, list_profiles, scene_get)  # noqa: E402

TAG_RE = re.compile(r"<[^>]+>")
SRC_RE = re.compile(r'src="([^"]+)"')
PRICE_RE = re.compile(r"¥\s?([\d,]+)")
COUNT_RE = re.compile(r"(头奖|第二档)[^0-9]{0,40}?(\d+)\s*份")

LEVEL_ORDER = {"ERROR": 0, "WARN": 1, "INFO": 2}

# 出现在这些词附近的命中，属于「规则说明语境」，不是真的用了红线词
NEG_CTX = ("不写", "禁止", "不得", "严禁", "避免", "红线", "不可比", "不可",
           "不作", "不许", "别写", "禁用", "不用", "不能", "不要", "勿",
           "替代原", "已废弃", "作废",
           "不合计", "不得相加", "严禁相加", "单列", "分渠道", "不作合计",
           "一律分", "口径不可比", "不作验收")


def strip_tags(line):
    return TAG_RE.sub(" ", line)


def lint(paths, external=False, profile_name=None):
    rules = load_rules()
    prof = load_profile(rules, profile_name)
    # 现实边界线（硬红线）：来自 rules.json 的 reality_guard，任何场景恒查
    reality = rules.get("reality_guard", {}) or {}
    reality_claims = reality.get("forbidden_claims", []) or []
    voice_exempt = reality.get("voice_ratio_exempt", []) or []
    _vr = reality.get("voice_ratio_pattern")
    voice_ratio_re = re.compile(_vr) if _vr else None
    docs = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            docs.append((os.path.basename(p), f.read()))

    issues = []

    def add(level, code, where, msg, snippet=""):
        issues.append({"level": level, "code": code, "where": where,
                       "msg": msg, "snippet": snippet[:130]})

    # ---- 场景派生参数（不再写死） ----
    channels = prof.get("channels", [])
    no_participation = [c["name"] for c in channels if c.get("no_participation_kpi")]
    # 注意：「能做一键入库动作」≠「能回传入库人数」。{{CHANNEL_TYPE_A}}能做动作但统计不到结果，
    # {{CHANNEL_E}}这类有 CPS 的才回传得了。只认 can_report_install 标志，避免误放宽。
    can_report_install = any(c.get("can_report_install") for c in channels)
    node_type = scene_get(prof, "node.type")
    prize_on = scene_get(prof, "prize.model") == "lottery_tiers"
    check_bands = bool(scene_get(prof, "prize.structure.check_bands", False))
    head_band = scene_get(prof, "prize.bands.头奖")
    exceptions = scene_get(prof, "prize.exceptions", []) or []
    exception_prices = {int(e["price"]) for e in exceptions if e.get("price") is not None}
    exceptions_text = " ".join(str(e.get("item", "")) + str(e.get("why", "")) for e in exceptions)

    forbidden = scene_get(prof, "metrics.forbidden", []) or []
    noncomparable = scene_get(prof, "metrics.noncomparable", []) or []
    redline_words = rules.get("redline_words", {})
    prebooking_words = scene_get(prof, "metrics.prebooking_false_claim", []) or []
    if node_type == "预约期":
        redline_words = dict(redline_words)
        redline_words["prebooking_false_claim"] = prebooking_words

    for name, raw in docs:
        for i, rawline in enumerate(raw.split("\n"), 1):
            line = strip_tags(rawline)
            loc = "%s:%d" % (name, i)

            # 1. 外部图片引用（硬红线：外发会裂图）
            for ref in SRC_RE.findall(rawline):
                if not ref.startswith(("data:", "http:", "https:", "//")):
                    is_self_contained = "自包含" in name
                    level = "ERROR" if (is_self_contained or external) else "WARN"
                    tail = "" if not is_self_contained else "（本文件名为自包含版）"
                    add(level, "DELIVERY-01", loc,
                        "外部图片引用，单独发送对方看不到%s：%s%s"
                        % (tail, ref,
                           "" if level == "ERROR" else "　→ 外发前跑 {{可选工具·HTML自包含}}"),
                        line.strip())

            # 2. 违禁指标（按场景：某渠道能回传该指标时，这条禁用不适用）
            for fm in forbidden:
                if fm["pattern"] not in line:
                    continue
                applies = fm.get("applies_to", "all")
                if applies != "all":
                    if fm.get("unless_any_channel_can_report") == "install" and can_report_install:
                        continue  # 本场景有渠道能回传入库人数，这条禁用不适用
                    if fm.get("only_if_node_type") and fm["only_if_node_type"] != node_type:
                        continue
                if any(k in line for k in fm.get("allow_if_near", [])) or \
                   any(n in line for n in NEG_CTX):
                    add("INFO", "METRIC-01", loc,
                        "「%s」出现在解释/否定语境，确认不是当验收指标用"
                        % fm["pattern"], line.strip())
                else:
                    add(fm.get("level", "warn").upper(), "METRIC-01", loc,
                        "出现违禁指标「%s」：%s" % (fm["pattern"], fm.get("why", "")),
                        line.strip())

            # 3. 跨口径相加（硬纪律）
            if re.search(r"合计|总计|相加|汇总|总曝光|全渠道", line):
                for m in noncomparable:
                    if m in line:
                        if any(n in line for n in NEG_CTX):
                            continue
                        add("WARN", "METRIC-02", loc,
                            "疑似把不可比口径「%s」做合计——各家定义不同，严禁相加" % m,
                            line.strip())
                        break

            # 4. 红线词（硬红线 + 节点相关的预约期禁用词）
            for key, words in redline_words.items():
                if key in ("server_mix", "note") or not isinstance(words, list):
                    continue
                for w in words:
                    if w in line:
                        label = {"pay_to_win": "付费变强类表述",
                                 "official_tone": "官方腔",
                                 "prebooking_false_claim": "预约期写成版本已上线"}.get(key, key)
                        if any(n in line for n in NEG_CTX):
                            add("INFO", "RED-NEG", loc,
                                "%s「%s」出现在否定语境（应在说明规则），跳过"
                                % (label, w), line.strip())
                        else:
                            add("ERROR", "RED-%s" % key.upper(), loc,
                                "%s：「%s」" % (label, w), line.strip())

            # 5. 服线混淆（硬红线）
            sm = redline_words.get("server_mix", [])
            if len(sm) == 2 and sm[0] in line and sm[1] in line:
                if not re.search(r"不互通|区分|差异|两套|并行|不可混淆", line):
                    add("WARN", "RED-SERVER", loc,
                        "同一句同时出现{{SERVER_LINE_B}}与{{SERVER_LINE_A}}，确认没有混淆", line.strip())

            # 6. 被按参与规模考核的渠道（名单来自 profile，不再写死 {{CHANNEL_A}}）
            for ch in no_participation:
                if ch in line and re.search(r"参与人数|参与规模", line) and \
                   re.search(r"目标|KPI|考核|验收", line) and \
                   not any(n in line for n in NEG_CTX):
                    add("WARN", "CHANNEL-01", loc,
                        "%s 是触达盘、活动页承接弱，本场景规定不以参与规模考核" % ch,
                        line.strip())

            # 7. 现实边界线（硬红线，全局恒查，见准则 0.2）
            for fc in reality_claims:
                if fc["pattern"] not in line:
                    continue
                if any(n in line for n in NEG_CTX):
                    add("INFO", "REALITY-01", loc,
                        "「%s」出现在解释/否定语境，确认不是当方案承诺用" % fc["pattern"],
                        line.strip())
                else:
                    add(fc.get("level", "warn").upper(), "REALITY-01", loc,
                        "脱离游戏实际的表述「%s」：%s" % (fc["pattern"], fc.get("why", "")),
                        line.strip())

            if voice_ratio_re and voice_ratio_re.search(line) and \
                    not any(w in line for w in voice_exempt):
                add("WARN", "REALITY-02", loc,
                    "疑似把「讨论声量占比」写成人口比例——须带「声量/讨论」限定（准则 0.2）",
                    line.strip())

    # ---- 全文级检查 ----
    all_text = "\n".join(strip_tags(r) for _, r in docs)

    # 排期锚点：由场景决定要哪些（无 {{APPROVAL_PARTY}}审批 → 不要求 T-45）
    for anchor in scene_get(prof, "schedule.anchors", []) or []:
        if anchor not in all_text:
            hint = "{{APPROVAL_PARTY}}审批" if anchor == "T-45" else "档期锁定 / 联调 / 验收（见场景档）"
            add("WARN", "SCHED-01", "全文",
                "未出现排期锚点 %s（%s）。若排期已外置到独立 md，把它一起传入本脚本"
                % (anchor, hint))

    # 版本延期预案：只有以版本日为时间锚点的场景才要求
    if scene_get(prof, "schedule.needs_version_delay_risk", False) and "延期" not in all_text:
        add("WARN", "RISK-01", "全文",
            "未见「版本延期预案」——本场景以版本日为时间锚点，延期则全盘失效")

    # 奖品结构：只在抽奖梯度型奖池场景下检查
    if prize_on and scene_get(prof, "prize.structure.second_gt_head", False):
        counts = {}
        for m in COUNT_RE.finditer(all_text):
            counts.setdefault(m.group(1), []).append(int(m.group(2)))
        if "头奖" in counts and "第二档" in counts:
            h, s = max(counts["头奖"]), max(counts["第二档"])
            if s <= h:
                add("ERROR", "PRIZE-01", "全文",
                    "第二档份数（%d）未大于头奖份数（%d）——本场景要求钩子密度优先" % (s, h))
            else:
                add("INFO", "PRIZE-01", "全文",
                    "份数结构：头奖 %d / 第二档 %d，符合" % (h, s))

    # 价带：由场景给，允许登记在案的例外降级为 INFO
    if prize_on and check_bands and head_band:
        over = sorted({p for p in (int(x.replace(",", "")) for x in PRICE_RE.findall(all_text))
                       if head_band[1] < p <= 2000})
        exc_hit = [p for p in over if p in exception_prices]
        other = [p for p in over if p not in exception_prices]
        if exc_hit:
            add("INFO", "PRIZE-02", "全文",
                "单价 %s 超出头奖价带，但已在本场景档登记例外，确认理由写进方案"
                % "、".join("¥%d" % p for p in exc_hit),
                exceptions_text.strip()[:130])
        if other:
            add("WARN", "PRIZE-02", "全文",
                "单价落在头奖价带（¥%s~%s）之上：%s——吸引力靠换品类/加份数，不靠加单价"
                % (head_band[0], head_band[1],
                   "、".join("¥%d" % p for p in other[:6])))

    # 脱敏词表随外发对象变
    if external:
        hits = [k for k in (scene_get(prof, "delivery.desensitize_keywords", []) or [])
                if k in all_text]
        if hits:
            add("INFO", "DESENS-01", "全文",
                "含内部数据关键词：%s——本场景外发对象是「%s」，确认是否需要脱敏"
                % ("、".join(hits), scene_get(prof, "delivery.audience", "内部")))

    issues.sort(key=lambda x: (LEVEL_ORDER[x["level"]], x["where"]))
    return issues, prof


def main():
    ap = argparse.ArgumentParser(description="方案出稿体检（场景驱动）")
    ap.add_argument("files", nargs="*", help="方案文件（.md / .html），可多个")
    ap.add_argument("--profile", help="场景档 id 或 json 路径，缺省用 rules.json 的 default_profile")
    ap.add_argument("--list-profiles", action="store_true", help="列出可用场景档并退出")
    ap.add_argument("--summary", action="store_true", help="只看摘要")
    ap.add_argument("--only", choices=["error", "warn", "info"], help="只看某一级")
    ap.add_argument("--external", action="store_true", help="外发模式，加查脱敏")
    args = ap.parse_args()

    if args.list_profiles:
        r = load_rules()
        print("可用场景档（默认：%s）" % r.get("default_profile"))
        for pid, pname, parent in list_profiles():
            p = load_profile(r, pid)
            print("  %-28s %-40s extends=%-24s 渠道=%d 奖池=%s" % (
                pid, pname, parent or "-", len(p.get("channels", [])),
                scene_get(p, "prize.model", "-")))
        return 0

    if not args.files:
        ap.error("请给至少一个方案文件，或用 --list-profiles")
    for f in args.files:
        if not os.path.exists(f):
            print("找不到文件：%s" % f)
            return 2

    try:
        issues, prof = lint(args.files, args.external, args.profile)
    except (FileNotFoundError, ValueError) as e:
        print("场景档加载失败：%s" % e)
        return 2

    if args.only:
        issues = [x for x in issues if x["level"] == args.only.upper()]

    print("体检：%s" % " + ".join(os.path.basename(f) for f in args.files))
    print("场景档：%s（%s）%s" % (prof["id"], prof.get("name", ""),
                               "　【外发模式】" if args.external else ""))
    print("=" * 60)

    if not issues:
        print("未发现问题。")
        return 0

    if not args.summary:
        cur = None
        for it in issues:
            if it["level"] != cur:
                cur = it["level"]
                print("\n[%s]" % cur)
            print("  %-14s %-26s %s" % (it["code"], it["where"], it["msg"]))
            if it["snippet"]:
                print("                 » %s" % it["snippet"])

    n = {lv: sum(1 for x in issues if x["level"] == lv)
         for lv in ("ERROR", "WARN", "INFO")}
    print("\n" + "=" * 60)
    print("摘要：ERROR %d / WARN %d / INFO %d" % (n["ERROR"], n["WARN"], n["INFO"]))
    print("结论：%s" % ("有硬伤，先修 ERROR 再出稿"
                       if n["ERROR"] else "可出稿，WARN 逐条确认"))
    return 1 if n["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main())
