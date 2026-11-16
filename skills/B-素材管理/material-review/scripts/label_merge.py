#!/usr/bin/env python3
"""合并各批 AI 看图打标结果，按"图→投放记录"回填，生成打标 CSV。

用法:
  python label_merge.py --labels-dir ./data --pattern 'labels_b*.json' \
      --master ./data/master.csv --out ./data/tagged.csv \
      --node-rule ./node_rules.json

labels 目录中的 JSON 由子智能体逐张看图产出，格式:
  [{"img":"21","style":"手绘概念原画","elements":"场景风景","benefit":"无福利","desc":"...","conf":"高"}]

node_rules.json（可选）定义节点判定规则:
  {"keywords": {"周年庆": ["周年"]}, "ranges": {"050档期": ["{{AS_OF_DATE}}","{{AS_OF_DATE}}"], "040档期": ["{{AS_OF_DATE}}","{{AS_OF_DATE}}"]}, "default": "日常"}
"""
import argparse
import csv
import glob
import json
import os


def load_labels(labels_dir, pattern):
    merged = {}
    for p in sorted(glob.glob(os.path.join(labels_dir, pattern))):
        for x in json.load(open(p, encoding="utf-8")):
            merged[str(x["img"])] = x
    return merged


def make_node_fn(rules):
    rules = rules or {}
    kw = rules.get("keywords", {})
    ranges = rules.get("ranges", {})
    default = rules.get("default", "日常")

    def node(row):
        text = (row.get("广告标题") or "") + " " + (row.get("广告描述") or "")
        for name, words in kw.items():
            for w in words:
                if w in text:
                    return name
        d = row.get("投放日期") or ""
        for name, (s, e) in ranges.items():
            if s <= d <= e:
                return name
        return default
    return node


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels-dir", default="./data")
    ap.add_argument("--pattern", default="labels_b*.json")
    ap.add_argument("--master", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--node-rule", default=None)
    args = ap.parse_args()

    labels = load_labels(args.labels_dir, args.pattern)
    rows = list(csv.DictReader(open(args.master, encoding="utf-8-sig")))

    rep = {}
    seen = set()
    for r in rows:
        u = r["图片链接"]
        if u and u not in seen:
            seen.add(u)
            rep[u] = r["rowid"]
    row_by_id = {r["rowid"]: r for r in rows}

    rules = json.load(open(args.node_rule, encoding="utf-8")) if args.node_rule else None
    node_fn = make_node_fn(rules)

    out, miss = [], 0
    for r in rows:
        rid = rep.get(r["图片链接"])
        L = labels.get(str(rid), {}) if rid else {}
        if not L:
            miss += 1
        out.append({
            "s_material_id": r["s_material_id"],
            "投放日期": r["投放日期"],
            "用户分层": r["用户分层"],
            "广告位置": r["广告位置"],
            "节点": node_fn(r),
            "画风": L.get("style", ""),
            "画面元素": L.get("elements", ""),
            "福利呈现": L.get("benefit", ""),
            "视觉描述": L.get("desc", ""),
            "置信度": L.get("conf", ""),
            "曝光UV": r["曝光UV"],
            "点击UV": r["点击UV"],
        })

    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    err = sum(1 for o in out if o["画风"] == "ERROR")
    print("标签条目 %d | 输出记录 %d | 未匹配 %d | ERROR %d" % (len(labels), len(out), miss, err))
    print("输出: %s" % args.out)


if __name__ == "__main__":
    main()
