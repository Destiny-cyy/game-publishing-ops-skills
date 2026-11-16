#!/usr/bin/env python3
"""按标签重命名素材图：编号_画风-元素(用+连接)-福利_素材ID.jpg

用法:
  python rename_images.py --map ./data/tagged.csv --dir ./素材图            # 预览(dry-run)
  python rename_images.py --map ./data/tagged.csv --dir ./素材图 --apply     # 实际执行
  python rename_images.py --map ./data/tagged.csv --dir ./素材图 --apply --out name_map.csv

默认先 dry-run 打印变更数量、重名检查与样例，确认无误再加 --apply。
文件名用 '+' 连接多选元素（'/' 是 Windows 非法字符）。
"""
import argparse
import csv
import os


def build(row, no):
    els = (row["画面元素"] or "未标注").replace("+", "+")
    return "%03d_%s-%s-%s_%s.jpg" % (
        no, row["画风"] or "未标注", els, row["福利呈现"] or "未标注", row["s_material_id"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, help="打标 CSV（含 s_material_id/画风/画面元素/福利呈现）")
    ap.add_argument("--dir", required=True, help="素材图目录（当前文件名为 <编号>.jpg）")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default=None, help="输出 旧名→新名 映射 CSV")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.map, encoding="utf-8-sig")))
    seen, plan = set(), []
    for r in rows:
        key = r["s_material_id"]
        if key in seen:
            continue
        seen.add(key)
        cur = os.path.join(args.dir, "%s.jpg" % r.get("编号", r.get("rowid", "")))
        if not os.path.exists(cur):
            continue
        new = build(r, int(os.path.basename(cur).split(".")[0]))
        plan.append((cur, os.path.join(args.dir, new), new))

    names = [p[2] for p in plan]
    dup = len(names) - len(set(names))
    illegal = [n for n in names if any(c in n for c in '\\/:*?"<>|')]
    print("计划 %d 个 | 重名 %d | 非法字符 %d | 最长 %d 字符" % (
        len(plan), dup, illegal and len(illegal) or 0, max(len(n) for n in names)))
    for p in plan[:10]:
        print("  %s -> %s" % (os.path.basename(p[0]), p[2]))

    if dup or illegal:
        print("存在问题，已中止。")
        return

    if not args.apply:
        print("\n(dry-run) 确认无误后加 --apply 执行")
        return

    done, errs = 0, []
    for cur, tgt, new in plan:
        if os.path.basename(cur) == new:
            continue
        if os.path.exists(tgt):
            errs.append(("exists", new))
            continue
        os.rename(cur, tgt)
        done += 1
    print("已重命名 %d | 错误 %s | 目录文件数 %d" % (done, errs, len(os.listdir(args.dir))))

    if args.out:
        with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["原文件名", "新文件名", "素材ID"])
            for cur, tgt, new in plan:
                w.writerow([os.path.basename(cur), new, new.rsplit("_", 1)[-1].replace(".jpg", "")])
        print("映射表: %s" % args.out)


if __name__ == "__main__":
    main()
