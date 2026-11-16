"""轻量分群：频次表 / 交叉表 / 分位数式分层（纯标准库，非机器学习聚类）。

对应维度 ② 行为分群。判据透明、别人拿同一份数据能复算。
样本小于 20 的组会标 '样本不足'，只给方向性结论。
"""
import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

MISSING = "(缺失)"
SMALL_GROUP = 20


def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def freq(rows, by):
    return dict(Counter((r.get(by) or "").strip() or MISSING for r in rows))


def cross(rows, a, b):
    table = defaultdict(Counter)
    for r in rows:
        ka = (r.get(a) or "").strip() or MISSING
        kb = (r.get(b) or "").strip() or MISSING
        table[ka][kb] += 1
    return {k: dict(v) for k, v in table.items()}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rfm_lite(rows, recency="recency_days", frequency="freq", value="value"):
    """按中位数把三个数值列各切高/低两档，交叉成群。"""
    cuts = {}
    for col in (recency, frequency, value):
        nums = sorted(v for v in (_to_float(r.get(col)) for r in rows) if v is not None)
        cuts[col] = float(statistics.median(nums)) if nums else None
    if any(v is None for v in cuts.values()):
        return {"cut_points": cuts, "groups": {}, "note": "数值列不足，无法分层"}
    groups = Counter()
    for r in rows:
        rc, fr, va = (_to_float(r.get(c)) for c in (recency, frequency, value))
        if None in (rc, fr, va):
            groups["(数据不足)"] += 1
            continue
        tag = (
            ("近" if rc <= cuts[recency] else "远")
            + ("·高频" if fr >= cuts[frequency] else "·低频")
            + ("·高值" if va >= cuts[value] else "·低值")
        )
        groups[tag] += 1
    flagged = [g for g, n in groups.items() if n < SMALL_GROUP]
    return {
        "cut_points": cuts,
        "groups": dict(groups),
        "small_groups": flagged,
        "small_group_policy": "样本不足，只给方向性结论",
        "method": "中位数切分（近似 RFM），不是聚类算法",
    }


def run(input_path, by="server_line", cross_by=None, do_rfm=False):
    rows = load(input_path)
    result = {
        "rows": len(rows),
        "freq_by": by,
        "freq": freq(rows, by),
        "note": "占比须写明分母；讨论声量不等于人口比例",
    }
    if cross_by:
        result["cross"] = cross(rows, by, cross_by)
    if do_rfm:
        result["rfm_lite"] = rfm_lite(rows)
    return result


def main():
    ap = argparse.ArgumentParser(description="轻量分群统计")
    ap.add_argument("--input", required=True)
    ap.add_argument("--by", default="server_line")
    ap.add_argument("--cross-by", default=None)
    ap.add_argument("--rfm", action="store_true", help="额外跑分位数分层")
    ap.add_argument("--out", default="out/segments.json")
    a = ap.parse_args()
    result = run(a.input, a.by, a.cross_by, a.rfm)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("segment: {} rows, {} groups -> {}".format(
        result["rows"], len(result["freq"]), a.out))


if __name__ == "__main__":
    main()
