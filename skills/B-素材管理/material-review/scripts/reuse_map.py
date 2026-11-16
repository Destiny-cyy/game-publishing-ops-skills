#!/usr/bin/env python3
"""素材复用与衰减分析：投放记录 → 唯一创意图，算复用次数与效率衰减（只读，不改表）。

背景：一张创意图会被多条投放记录复用（不同人群/日期/广告位各记一行）。
按「第 N 次复用」分档看 CTR 中位，能判断"老图反复投"是否还有效。

用法:
  python reuse_map.py --master ./data/master.csv \
      --tagged ./data/tagged.csv --out ./data/reuse_map.csv

输入:
  --master  主表 CSV（fetch_materials.py 产出），需含：素材ID / 图片链接 / 曝光UV / 点击UV / 用户分层
  --tagged  打标 CSV（label_merge.py 产出，可选）用于带出 画风 / 福利呈现，缺失则留空

产出:
  <out>  每张唯一图一行：代表素材ID / 画风 / 福利呈现 / 复用次数 / 同图素材ID / 同图用户分层 /
          同图各条CTR / 同图加权CTR(%) / 同图总曝光 / 同图总点击 / 原图链接
  控制台  复用分档 × 中位CTR × 合计曝光 的衰减表
"""
import argparse
import csv
import statistics
import sys
from collections import OrderedDict

io_enc = "utf-8"


def pick(fieldnames, *keys):
    """按关键字容错取列名：优先完全匹配，其次包含匹配。"""
    for k in keys:
        if k in fieldnames:
            return k
    for k in keys:
        for f in fieldnames:
            if k in f:
                return f
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", required=True)
    ap.add_argument("--tagged", default=None)
    ap.add_argument("--out", default="./data/reuse_map.csv")
    ap.add_argument("--min-imp", type=int, default=0, help="忽略曝光低于该值的投放记录")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.master, encoding="utf-8-sig")))
    if not rows:
        sys.exit("主表为空")

    # 注意：fetch_materials.py 产出的主表用英文列名 s_material_id，广告类型即用户分层
    c_id = pick(rows[0].keys(), "素材ID", "素材id", "s_material_id", "material")
    c_img = pick(rows[0].keys(), "图片链接", "原图链接", "图片")
    c_imp = pick(rows[0].keys(), "曝光UV", "曝光")
    c_clk = pick(rows[0].keys(), "点击UV", "点击")
    c_seg = pick(rows[0].keys(), "用户分层", "广告类型", "分层")
    for name, col in [("素材ID", c_id), ("图片链接", c_img), ("曝光UV", c_imp), ("点击UV", c_clk)]:
        if not col:
            sys.exit("主表缺少列：%s（现有：%s）" % (name, ",".join(rows[0].keys())))

    # 打标信息（可选）
    tag = {}
    if args.tagged:
        trs = list(csv.DictReader(open(args.tagged, encoding="utf-8-sig")))
        t_id = pick(trs[0].keys(), "素材ID", "素材id", "s_material_id", "material") if trs else None
        for t in trs:
            tid = t.get(t_id) if t_id else None
            if tid:
                tag[str(tid).strip()] = t

    # 按图片链接聚合
    groups = OrderedDict()
    for r in rows:
        imp = float(r[c_imp] or 0)
        if imp < args.min_imp:
            continue
        key = (r[c_img] or "").strip()
        if not key:
            continue
        groups.setdefault(key, []).append(r)

    out = []
    for i, (img, recs) in enumerate(groups.items(), 1):
        imp = sum(float(r[c_imp] or 0) for r in recs)
        clk = sum(float(r[c_clk] or 0) for r in recs)
        ctr = clk / imp * 100 if imp else 0
        rep = recs[0]
        t = tag.get(str(rep[c_id]).strip(), {})
        out.append({
            "": i,
            "代表素材ID": rep[c_id],
            "画风": t.get("画风", ""),
            "福利呈现": t.get("福利呈现", ""),
            "复用次数": len(recs),
            "同图素材ID": "/".join(str(r[c_id]) for r in recs),
            "同图用户分层": "/".join(str(r.get(c_seg, "")) for r in recs) if c_seg else "",
            "同图各条CTR": "/".join(
                "%.2f%%" % (float(r[c_clk] or 0) / float(r[c_imp] or 1) * 100) for r in recs),
            "同图加权CTR": round(ctr, 2),
            "同图总曝光": int(imp),
            "同图总点击": int(clk),
            "原图链接": img,
        })

    cols = list(out[0].keys())
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print("已写出 %s：%d 张唯一图（来自 %d 条投放记录）" % (args.out, len(out), len(rows)))

    # 分档衰减
    print("\n=== 复用分档 × 效率 ===")
    print("  %-10s %-8s %-12s %-12s" % ("复用次数", "张数", "中位CTR", "合计曝光"))
    buckets = {}
    for r in out:
        k = r["复用次数"] if r["复用次数"] <= 3 else "4+"
        buckets.setdefault(k, []).append(r)
    for k in sorted(buckets, key=lambda x: (isinstance(x, str), x)):
        g = buckets[k]
        med = statistics.median([x["同图加权CTR"] for x in g])
        imp = sum(x["同图总曝光"] for x in g)
        flag = "  (样本极小，仅参考)" if len(g) < 10 else ""
        print("  %-10s %-8d %-12s %-12s%s" % (
            "%s 次" % k, len(g), "%.2f%%" % med, "%.0fw" % (imp / 10000), flag))

    low = [x for x in out if x["复用次数"] >= 3]
    if low:
        imp_low = sum(x["同图总曝光"] for x in low)
        imp_all = sum(x["同图总曝光"] for x in out)
        print("\n  复用≥3 次的图：%d 张，占曝光 %.0f%%（%.0fw）" % (
            len(low), imp_low / imp_all * 100 if imp_all else 0, imp_low / 10000))


if __name__ == "__main__":
    main()
