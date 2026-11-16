#!/usr/bin/env python3
"""大盘 Benchmark：游戏级 + 素材级 双口径（通用版，参数化目标游戏与对标游戏）。

用法:
  python benchmark.py --data-dir ./data --target {{GAME_CN}} \
      --peers {{BENCHMARK_GAME_A}},{{BENCHMARK_GAME_A}} --months 2026-07,2026-08,2026-09,2026-10

输入（--data-dir 下）:
  bench.json           游戏×月聚合 {rows:[{g,m,imp,clk}]}（来自 smartsheet 大盘表 GROUP BY 游戏名,月）
  bench_materials.json 单条素材明细 {g,imp,clk[,m]}（曝光≥10w 的素材）

输出: benchmark.json（游戏级月度/全周期、素材级全周期，含中位/排名/分位）
注意: 排名/分位属扎心数据，仅供内部参考，不写进对外报告（见 analysis-playbook.md 叙事原则）。
"""
import argparse, json, os, statistics

def load_json(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict) and "values" in d:
        vals = d["values"]
        return (json.loads(vals[0]) if isinstance(vals[0], str) else vals[0])["rows"]
    return d

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="./data")
    ap.add_argument("--target", required=True, help="目标游戏名（如 {{GAME_CN}}）")
    ap.add_argument("--peers", default="", help="对标游戏，逗号分隔（如 {{BENCHMARK_GAME_A}},{{BENCHMARK_GAME_A}}）")
    ap.add_argument("--months", default="2026-07,2026-08,2026-09,2026-10")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    TARGET = args.target
    PEERS = [x for x in args.peers.split(",") if x]
    months = [m for m in args.months.split(",") if m]
    out_path = args.out or os.path.join(args.data_dir, "benchmark.json")

    g_rows = load_json(os.path.join(args.data_dir, "bench.json"))
    res = {"目标": TARGET, "对标": PEERS, "游戏级月度": {}}

    # 游戏级月度
    for m in months:
        gm = {r["g"]: {"imp": r["imp"], "clk": r["clk"], "ctr": r["clk"] / r["imp"] * 100}
              for r in g_rows if r["m"] == m}
        ranked = sorted(gm.items(), key=lambda kv: -kv[1]["ctr"])
        med = statistics.median([v["ctr"] for v in gm.values()])
        entry = {"中位": med, "游戏数": len(gm)}
        for g in [TARGET] + PEERS:
            if g in gm:
                rank = [i + 1 for i, (k, _) in enumerate(ranked) if k == g][0]
                entry[g] = {"ctr": gm[g]["ctr"], "rank": rank, "total": len(gm),
                            "pct": round((1 - rank / len(gm)) * 100), "imp": gm[g]["imp"]}
        res["游戏级月度"][m] = entry

    # 游戏级全周期
    allg = {}
    for r in g_rows:
        a = allg.setdefault(r["g"], [0, 0])
        a[0] += r["imp"]; a[1] += r["clk"]
    allr = {g: {"ctr": c / i * 100, "imp": i} for g, (i, c) in allg.items()}
    ranked = sorted(allr.items(), key=lambda kv: -kv[1]["ctr"])
    med = statistics.median([v["ctr"] for v in allr.values()])
    res["游戏级全周期"] = {"中位": med, "游戏数": len(allr)}
    for g in [TARGET] + PEERS:
        if g in allr:
            rank = [i + 1 for i, (k, _) in enumerate(ranked) if k == g][0]
            res["游戏级全周期"][g] = {"ctr": allr[g]["ctr"], "rank": rank, "total": len(allr),
                                  "pct": round((1 - rank / len(allr)) * 100), "imp": allr[g]["imp"]}

    # 素材级全周期（曝光≥10w）
    mpath = os.path.join(args.data_dir, "bench_materials.json")
    if os.path.exists(mpath):
        m_rows = load_json(mpath)
        byg = {}
        for r in m_rows:
            byg.setdefault(r["g"], []).append(r["clk"] / r["imp"] * 100)
        allv = sorted(r["clk"] / r["imp"] * 100 for r in m_rows)
        res["素材级全周期"] = {"中位": statistics.median(allv), "素材数": len(m_rows)}
        for g in [TARGET] + PEERS:
            if g in byg:
                vals = byg[g]
                g_med = statistics.median(vals)
                below = sum(1 for v in allv if v <= g_med)
                hi = sum(1 for v in vals if v >= 1.0)
                res["素材级全周期"][g] = {"中位": g_med, "n": len(vals),
                                      "分位": round(below / len(allv) * 100),
                                      "≥1%占比": round(hi / len(vals) * 100)}

    json.dump(res, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("已写出:", out_path)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:3500])

if __name__ == "__main__":
    main()
