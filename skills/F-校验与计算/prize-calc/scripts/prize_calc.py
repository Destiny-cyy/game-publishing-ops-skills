#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
奖品表计算与约束校验 · v2.0 场景驱动。

吃掉两个坑：
  1. 改完单价忘了重算小计，渠道之和与总盘子对不上（准则坑 13）
  2. 奖品表维护两份导致数字打架（准则坑 5）——本脚本是唯一计算入口

v2.0（{{AS_OF_DATE}}）：价带、份数、权重顺序、同级容差、卡占比、盘子、渠道名单
全部从 profile 取。单渠道 / 积分制 / 平台奖励场景自动关闭不适用检查，
不再拿「{{CHANNEL_COUNT}}家{{CHANNEL_TYPE_A}} + 抽奖梯度」这一套去卡所有活动。

用法：
  python prize_calc.py prizes.csv --profile channel_prebook
  python prize_calc.py prizes.csv --profile community_cps
  python prize_calc.py --list-profiles
  python prize_calc.py prizes.csv --md out.md
  python prize_calc.py --demo
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_DIR = os.path.join(HERE, "..", "..", "..", "..", "_shared")
sys.path.insert(0, os.path.abspath(RULES_DIR))
from profile_loader import (load_rules, load_profile, list_profiles, scene_get)  # noqa: E402

FIELDS = ["渠道", "档位", "类型", "名称", "单价", "数量"]
TIER_HEAD = "头奖"
TIER_SECOND = "第二档"
SHARED_NAMES = {"{{CHANNEL_COUNT}}家", "共用", "全渠道", "公共", "全体"}

DEMO_ROWS = [
    # 以下为演示数值，非任何真实采买价；结构规则见 _shared/REDLINES.md 与场景档
    ["{{CHANNEL_A}}", "头奖", "手柄", "示例手柄 A", 700, 1],
    ["{{CHANNEL_A}}", "第二档", "键盘", "示例键盘 A", 300, 1],
    ["{{CHANNEL_B}}", "头奖", "键盘", "示例键盘 A", 600, 1],
    ["{{CHANNEL_B}}", "第二档", "音频", "示例音箱 A", 300, 2],
    ["{{CHANNEL_C}}", "头奖", "耳机", "示例耳机 A", 500, 1],
    ["{{CHANNEL_C}}", "第二档", "键盘", "示例键盘 B", 250, 1],
    ["{{CHANNEL_D}}", "头奖", "鼠标", "示例鼠标 A", 400, 1],
    ["{{CHANNEL_D}}", "第二档", "键盘", "示例键盘 B", 200, 2],
    ["{{CHANNEL_COUNT}}家", "平台卡", "卡", "平台充值卡 30 元", 30, 60],
    ["{{CHANNEL_COUNT}}家", "平台卡", "卡", "平台充值卡 60 元", 60, 18],
    ["{{CHANNEL_COUNT}}家", "平台卡", "卡", "平台充值卡 150 元", 150, 6],
]


def read_rows(path):
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [[r.get(k, "") for k in FIELDS] for r in data]
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        rows = [r for r in rd if r and r[0].strip()]
    if rows and rows[0][0].strip() == "渠道":
        rows = rows[1:]
    return rows


def _canon(name, prof):
    """渠道名归一：同一家可能写 {{CHANNEL_C}} / {{CHANNEL_C}} / {{CHANNEL_C}}{{CHANNEL_TYPE_A}}。别名在场景档里登记。"""
    if name in SHARED_NAMES:
        return name
    for c in prof.get("channels", []):
        opts = [c["name"]] + list(c.get("aliases", []) or [])
        if name in opts or name.lower() in [o.lower() for o in opts]:
            return c["name"]
    return name


def calc(rows, rules, prof):
    excluded_types = set(scene_get(prof, "prize.exclude_types", []) or [])
    excluded_count = 0
    items = []
    for r in rows:
        if len(r) < 6:
            continue
        ch, tier, typ, name = r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip()
        if typ in excluded_types or tier in excluded_types:
            excluded_count += 1
            continue  # 例：CDK 是已购库存，准则规定不列支、不进渠道汇总
        try:
            price = float(str(r[4]).replace("¥", "").replace(",", "").strip())
            qty = int(str(r[5]).strip())
        except ValueError:
            continue
        items.append({"渠道": _canon(ch, prof), "档位": tier, "类型": typ, "名称": name,
                      "单价": price, "数量": qty, "总价值": round(price * qty, 2)})

    checks = []
    if excluded_count:
        checks.append(("INFO", "SCOPE-01",
                       "按本场景口径排除 %d 行 %s（已购库存，不列支）"
                       % (excluded_count, "/".join(sorted(excluded_types)))))

    # 1. 渠道小计与总盘子（共用行单独列，不参与单渠道权重）
    subs, shared_total = {}, 0.0
    for it in items:
        if it["渠道"] in SHARED_NAMES:
            shared_total += it["总价值"]
        else:
            subs[it["渠道"]] = subs.get(it["渠道"], 0) + it["总价值"]
    total = round(sum(it["总价值"] for it in items), 2)

    # ---- 场景派生参数 ----
    prize = prof.get("prize", {})
    tiers_on = prize.get("model") == "lottery_tiers"
    structure = prize.get("structure", {}) or {}
    bands = prize.get("bands", {}) or {}
    exceptions = prize.get("exceptions", []) or []
    exc_text = " ".join(str(e.get("item", "")) for e in exceptions)

    head_items = [i for i in items if i["档位"] == TIER_HEAD]
    sec_items = [i for i in items if i["档位"] == TIER_SECOND]
    head_qty = sum(i["数量"] for i in head_items)
    sec_qty = sum(i["数量"] for i in sec_items)

    # 2. 份数结构：只在梯度型奖池且场景要求时检查
    if tiers_on and structure.get("second_gt_head") and head_items and sec_items:
        if sec_qty <= head_qty:
            checks.append(("ERROR", "PRIZE-01",
                           "第二档份数 %d 未大于头奖份数 %d（本场景要求钩子密度优先）"
                           % (sec_qty, head_qty)))
        else:
            checks.append(("OK", "PRIZE-01",
                           "份数结构 头奖 %d / 第二档 %d，符合" % (head_qty, sec_qty)))
    elif not tiers_on:
        checks.append(("INFO", "PRIZE-01",
                       "奖池模型为 %s，份数梯度检查不适用，已跳过" % prize.get("model")))

    # 3. 价带：由场景给；登记在案的例外降级 INFO（现行方案 {{CHANNEL_D}} {{BUDGET_AMOUNT}} 就是这种）
    if tiers_on and structure.get("check_bands"):
        for tier, key, code, level in ((TIER_HEAD, "头奖", "PRIZE-02", "ERROR"),
                                       (TIER_SECOND, "第二档", "PRIZE-03", "WARN")):
            band = bands.get(key)
            if not band:
                continue
            for i in (head_items if tier == TIER_HEAD else sec_items):
                if not (band[0] <= i["单价"] <= band[1]):
                    is_exc = exc_text and any(s in exc_text for s in (i["名称"][:6], "¥%.0f" % i["单价"]))
                    checks.append(("INFO" if is_exc else level, code,
                                   "%s「%s」单价 ¥%.0f 在价带 ¥%s~%s 之外%s"
                                   % (tier, i["名称"], i["单价"], band[0], band[1],
                                      "；已在场景档登记例外，确认理由写进方案" if is_exc
                                      else "——吸引力靠换品类/加份数，不靠加单价")))

    # 4. 卡占比下限：盘子变了先看结构，不是只砍卡
    cmin = structure.get("card_ratio_min")
    if tiers_on and cmin is not None and total:
        card_total = sum(i["总价值"] for i in items
                         if "卡" in i["档位"] or "卡" in i["类型"])
        ratio = card_total / total
        if ratio < cmin:
            checks.append(("ERROR", "PRIZE-06",
                           "卡占比 %.1f%% 低于本场景下限 %.0f%%——先查结构，别先砍卡"
                           % (ratio * 100, cmin * 100)))
        else:
            checks.append(("OK", "PRIZE-06", "卡占比 %.1f%% ≥ %.0f%%" % (ratio * 100, cmin * 100)))

    # 5. 每渠道头奖件数
    hmin = structure.get("head_per_channel_min")
    if tiers_on and hmin:
        head_by_ch = {}
        for i in head_items:
            head_by_ch[i["渠道"]] = head_by_ch.get(i["渠道"], 0) + i["数量"]
        need = [c["name"] for c in prof.get("channels", []) if c.get("head_prize")]
        missing = [c for c in need if head_by_ch.get(c, 0) < hmin]
        if missing:
            checks.append(("ERROR", "PRIZE-07",
                           "渠道缺少头奖（本场景要求每渠道 ≥%d 件）：%s"
                           % (hmin, "、".join(missing))))
        else:
            checks.append(("OK", "PRIZE-07", "每渠道头奖 ≥%d 件" % hmin))

    # 6. 权重：启用才查；顺序长度可变；同级＝差额 ≤tolerance（不再精确等额）
    w = prof.get("weight", {}) or {}
    if tiers_on and w.get("enabled"):
        order = [c for c in w.get("order", []) if c in subs]
        pairs = {frozenset(p) for p in w.get("equal_pairs", []) if len(p) == 2}
        tol = w.get("tolerance", rules.get("fallbacks", {}).get("weight_tolerance", 100))
        if len(order) >= 2 and all(c in subs for c in w.get("order", [])):
            order = list(w["order"])
            bad = []
            for a, b in zip(order, order[1:]):
                if frozenset((a, b)) in pairs:
                    if abs(subs[a] - subs[b]) > tol:
                        bad.append("%s 与 %s 差额 ¥%.0f > ¥%s" % (a, b, abs(subs[a] - subs[b]), tol))
                elif subs[a] <= subs[b]:
                    bad.append("%s ¥%.0f 未高于 %s ¥%.0f" % (a, subs[a], b, subs[b]))
            if bad:
                checks.append(("WARN", "PRIZE-04/05",
                               "渠道金额权重不符（同级判定＝差额 ≤¥%s）：%s" % (tol, "；".join(bad))))
            else:
                checks.append(("OK", "PRIZE-04/05",
                               "渠道金额权重符合 %s（同级容差 ¥%s）" % (" ＞ ".join(order), tol)))
        else:
            checks.append(("INFO", "PRIZE-04/05", "权重渠道未在表内出现齐，跳过金额权重校验"))

        # 头奖份数权重：仅当份数不完全相同时检查
        hw = {}
        for i in head_items:
            hw[i["渠道"]] = hw.get(i["渠道"], 0) + i["数量"]
        if order and all(c in hw for c in order) and len(set(hw[c] for c in order)) > 1:
            bad = []
            for a, b in zip(order, order[1:]):
                if frozenset((a, b)) in pairs:
                    if hw[a] != hw[b]:
                        bad.append("%s %d vs %s %d" % (a, hw[a], b, hw[b]))
                elif hw[a] <= hw[b]:
                    bad.append("%s %d 未高于 %s %d" % (a, hw[a], b, hw[b]))
            if bad:
                checks.append(("WARN", "PRIZE-04b", "头奖份数权重不符：%s" % "；".join(bad)))
    else:
        checks.append(("INFO", "PRIZE-04/05",
                       "本场景未启用渠道权重排序（%s），权重校验已跳过" %
                       ("单渠道/无梯度" if not w.get("enabled") else "非梯度奖池")))

    # 7. 总盘子：阈值与参考带由场景给，没给就不判
    budget = prof.get("budget", {}) or {}
    over = budget.get("over_requires_reason")
    if over and total > over:
        band = budget.get("reference_band") or [None, None]
        checks.append(("WARN", "BUDGET-01",
                       "总额 ¥%.0f 超过本场景阈值 ¥%s（参考带 %s~%s），需给理由"
                       % (total, over, band[0], band[1])))
    elif over:
        checks.append(("OK", "BUDGET-01", "总额 ¥%.0f 在本场景阈值内" % total))
    else:
        checks.append(("INFO", "BUDGET-01", "本场景未设总额阈值，跳过预算带校验"))

    return items, subs, shared_total, total, checks


def render(items, subs, shared_total, total, checks, prof):
    out = ["场景档：%s（%s）" % (prof["id"], prof.get("name", "")), ""]
    out.append("| 渠道 | 档位 | 类型 | 名称 | 单价 | 数量 | 总价值 |")
    out.append("|---|---|---|---|---:|---:|---:|")
    last_ch = None
    for it in items:
        ch = it["渠道"] if it["渠道"] != last_ch else ""
        last_ch = it["渠道"]
        out.append("| %s | %s | %s | %s | ¥%.0f | %d | ¥%.2f |"
                   % (ch, it["档位"], it["类型"], it["名称"],
                      it["单价"], it["数量"], it["总价值"]))
    for ch, v in subs.items():
        out.append("| **%s 小计** | | | | | | **¥%.2f** |" % (ch, v))
    if shared_total:
        out.append("| **共用/卡池** | | | | | | **¥%.2f** |" % shared_total)
    out.append("| **合计** | | | | | | **¥%.2f** |" % total)
    out += ["", "### 校验"]
    for lv, code, msg in checks:
        mark = {"OK": "✅", "WARN": "⚠️", "ERROR": "❌"}.get(lv, "·")
        out.append("- %s **%s** %s" % (mark, code, msg))
    return "\n".join(out)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(description="奖品表计算与校验（场景驱动）")
    ap.add_argument("file", nargs="?", help="CSV 或 JSON 奖品清单")
    ap.add_argument("--profile", help="场景档 id 或 json 路径，缺省用 rules.json 的 default_profile")
    ap.add_argument("--list-profiles", action="store_true", help="列出可用场景档并退出")
    ap.add_argument("--md", help="结果写入 markdown 文件")
    ap.add_argument("--demo", action="store_true", help="跑内置示例")
    args = ap.parse_args()

    try:
        rules = load_rules()
        prof = load_profile(rules, args.profile)
    except (FileNotFoundError, ValueError) as e:
        print("场景档加载失败：%s" % e)
        return 2

    if args.list_profiles:
        print("可用场景档（默认：%s）" % rules.get("default_profile"))
        for pid, pname, parent in list_profiles():
            p = load_profile(rules, pid)
            print("  %-28s %-40s extends=%-24s 奖池=%s 权重=%s" % (
                pid, pname, parent or "-", scene_get(p, "prize.model", "-"),
                "开" if scene_get(p, "weight.enabled", False) else "关"))
        return 0

    if args.demo:
        rows, src = DEMO_ROWS, "内置示例"
    elif args.file and os.path.exists(args.file):
        rows, src = read_rows(args.file), os.path.basename(args.file)
    else:
        print("请给一个 CSV/JSON 文件，或用 --demo 跑示例")
        return 2

    items, subs, shared_total, total, checks = calc(rows, rules, prof)
    report = render(items, subs, shared_total, total, checks, prof)
    print("奖品表：%s（%d 行）" % (src, len(items)))
    if args.demo:
        print("※ 示例数据，仅演示计算与校验，不是当期实际奖品表")
    print("=" * 60)
    print(report)
    print("\n" + "=" * 60)
    print("总额：¥%.2f" % total)
    for ch, v in subs.items():
        print("  %s：¥%.2f" % (ch, v))
    errs = [c for c in checks if c[0] == "ERROR"]
    print("结论：%s" % ("❌ 有 %d 项硬伤" % len(errs) if errs else "✅ 可进方案"))

    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write("# 奖品表（由 prize-calc 生成）\n\n")
            f.write(report)
        print("已写入：%s" % args.md)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
