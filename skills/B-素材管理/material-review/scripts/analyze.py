#!/usr/bin/env python3
"""六维度曝光加权 CTR 分析 + 大盘 Benchmark 排名（只读，不改表）。

用法:
  python analyze.py --docid s3_xxx --sheet {{BENCHMARK_GAME_C}}素材打标 \
      [--bench-docid s3_yyy --bench-sheet {{PLATFORM_A}}素材 --game {{GAME_CN}}]

维度: 画风 / 福利呈现 / 节点 / 用户分层 / 画面元素(多选LIKE) / 月度趋势
"""
import argparse
import json
import subprocess


def query(docid, sqls):
    cmd = ["{{TABLE_TOOL_CLI}}", "smartsheet", "records", "query", "--docid", docid]
    for s in sqls:
        cmd += ["--sql", s]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    j = json.loads(r.stdout)
    return [(json.loads(v) if isinstance(v, str) else v)["rows"] for v in j["values"]]


def agg_sql(sheet, dim):
    return ('SELECT `%s` AS k, COUNT(*) AS n, SUM(`曝光UV`) AS imp, SUM(`点击UV`) AS clk '
            'FROM `%s` GROUP BY `%s` ORDER BY `imp` DESC LIMIT 100' % (dim, sheet, dim))


def show(title, rows):
    print("=== %s ===" % title)
    for r in rows:
        imp = r.get("imp") or 0
        clk = r.get("clk") or 0
        ctr = clk / imp * 100 if imp else 0
        flag = "  (样本不足)" if (r.get("n") or 0) < 20 else ""
        print("  %-14s 样本%-4s 曝光%.0fw  CTR %.2f%%%s" % (
            r.get("k") or "(空)", r.get("n"), imp / 10000, ctr, flag))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docid", required=True)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--elements", default="单角色立绘,多角色拼条,角色战斗,BOSS怪物,场景风景,游戏内地图,装备道具,萌系吉祥物,大字文案,实机")
    ap.add_argument("--bench-docid", default=None)
    ap.add_argument("--bench-sheet", default=None)
    ap.add_argument("--game", default="{{GAME_CN}}")
    args = ap.parse_args()

    dims = ["画风", "福利呈现", "节点", "用户分层"]
    res = query(args.docid, [agg_sql(args.sheet, d) for d in dims])
    for d, rows in zip(dims, res):
        show(d, rows)

    els = [e for e in args.elements.split(",") if e]
    sqls = ['SELECT "%s" AS k, COUNT(*) AS n, SUM(`曝光UV`) AS imp, SUM(`点击UV`) AS clk FROM `%s` '
            'WHERE `画面元素` LIKE "%%%s%%"' % (e, args.sheet, e) for e in els]
    elres = query(args.docid, sqls)
    show("画面元素(多选LIKE口径，组间重叠)", [r[0] for r in elres if r])

    trend = query(args.docid, ['SELECT DATE_FORMAT(`投放日期`, "%%Y-%%m") AS k, COUNT(*) AS n, '
                               'SUM(`曝光UV`) AS imp, SUM(`点击UV`) AS clk FROM `%s` '
                               'GROUP BY DATE_FORMAT(`投放日期`, "%%Y-%%m") ORDER BY k LIMIT 24' % args.sheet])
    show("月度趋势", trend[0])

    if args.bench_docid and args.bench_sheet:
        rows = query(args.bench_docid, [
            'SELECT `游戏名` AS g, DATE_FORMAT(`投放日期`, "%%Y-%%m") AS m, SUM(`曝光UV`) AS imp, '
            'SUM(`点击UV`) AS clk FROM `%s` GROUP BY `游戏名`, DATE_FORMAT(`投放日期`, "%%Y-%%m") LIMIT 2000'
            % args.bench_sheet])[0]
        bym = {}
        for r in rows:
            imp, clk = r.get("imp") or 0, r.get("clk") or 0
            if imp > 0:
                bym.setdefault(r["m"], []).append((r["g"], imp, clk, clk / imp * 100))
        print("=== 大盘 Benchmark ===")
        for m in sorted(bym):
            arr = sorted(bym[m], key=lambda x: -x[3])
            n = len(arr)
            hit = [(i + 1, a) for i, a in enumerate(arr) if a[0] == args.game]
            if hit:
                rank, (_, imp, clk, ctr) = hit[0]
                print("  %s  CTR %.2f%%  排名 %d/%d  中位 %.2f%%  top25线 %.2f%%" % (
                    m, ctr, rank, n, arr[n // 2][3], arr[n // 4][3]))
            else:
                print("  %s  未找到 %s（当月 %d 款游戏）" % (m, args.game, n))


if __name__ == "__main__":
    main()
