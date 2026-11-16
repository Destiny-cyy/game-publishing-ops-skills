"""数据入场校验：四类数据统一成标准记录（纯标准库、不联网）。

对应工作流阶段 2。只做格式统一、必填校验、去重、缺口统计，
不做任何语义判断，也不推断缺失内容。
"""
import argparse
import csv
import json
from pathlib import Path

REQUIRED = ("id", "source", "text", "user_tag", "timestamp")
DEDUP_RULE = "user_tag + text"


def load_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize(rows):
    """返回 (有效记录, 问题清单)。缺失单独计一类，不填 0。"""
    seen = set()
    out, issues = [], []
    for i, row in enumerate(rows, 1):
        rec = {k: (row.get(k) or "").strip() for k in REQUIRED}
        missing = [k for k in REQUIRED if not rec[k]]
        if missing:
            issues.append({"row": i, "type": "missing_field", "fields": missing})
            continue
        key = (rec["user_tag"], rec["text"])
        if key in seen:
            issues.append({"row": i, "type": "duplicate", "rule": DEDUP_RULE})
            continue
        seen.add(key)
        rec["extra"] = {
            k: (v or "").strip()
            for k, v in row.items()
            if k not in REQUIRED and (v or "").strip()
        }
        out.append(rec)
    return out, issues


def build_report(rows, records, issues):
    by_source = {}
    for r in records:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    return {
        "input_rows": len(rows),
        "valid_records": len(records),
        "dropped": len(rows) - len(records),
        "by_source": by_source,
        "dedup_rule": DEDUP_RULE,
        "missing_value_policy": "缺失单独计一类，不填 0、不填'无'",
        "note": "口径不同的来源请分列统计，不要合并后算总占比",
        "issues": issues,
        "records": records,
    }


def run(input_path):
    rows = load_rows(input_path)
    records, issues = normalize(rows)
    return build_report(rows, records, issues)


def main():
    ap = argparse.ArgumentParser(description="数据入场校验")
    ap.add_argument("--input", required=True, help="输入 CSV 路径")
    ap.add_argument("--out", default="out/contract.json", help="输出 JSON 路径")
    a = ap.parse_args()
    report = run(a.input)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("contract: {}/{} valid, {} issues -> {}".format(
        report["valid_records"], report["input_rows"], len(report["issues"]), a.out))


if __name__ == "__main__":
    main()
