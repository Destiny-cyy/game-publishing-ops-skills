"""策略清单体检（纯标准库）：五元组 / 三档 / 依据编号 / 等级门槛 / 红线词。

对应工作流阶段 5。只查结构与词表，查不了语义与事实；
红队审查与人工复核仍然必需。
"""
import argparse
import csv
import json
from pathlib import Path

FIVE = ("audience", "touchpoint", "action", "timing", "metric")
TIERS = {"可立即执行", "需验证", "仅观测"}
LEVELS = {"A", "B", "C"}
DEFAULT_REDLINES = (
    "氪金变强", "充值提升战力", "付费领先", "碾压", "战力领先",
    "敬请期待", "官方高度重视", "官方指定", "唯一合作", "权威发布",
    "数据互通", "跨服继承", "同账号通用",
    "版本已上线", "现已开放", "全新版本",
)


def load_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_redlines(path=None):
    if not path:
        return list(DEFAULT_REDLINES)
    return [l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def lint(rows, redlines=None):
    words = redlines if redlines is not None else load_redlines()
    issues = []
    for i, r in enumerate(rows, 1):
        sid = (r.get("id") or "").strip() or "row{}".format(i)
        for col in FIVE:
            if not (r.get(col) or "").strip():
                issues.append({"id": sid, "level": "block", "reason": "五元组缺项: {}".format(col)})
        if not (r.get("insight_id") or "").strip():
            issues.append({"id": sid, "level": "block", "reason": "缺依据的洞察编号"})
        tier = (r.get("tier") or "").strip()
        if tier not in TIERS:
            issues.append({"id": sid, "level": "block", "reason": "三档未标或取值非法: {}".format(tier)})
        level = (r.get("evidence_level") or "").strip().upper()
        if level not in LEVELS:
            issues.append({"id": sid, "level": "block", "reason": "证据等级非法: {}".format(level)})
        if level == "C" and tier == "可立即执行":
            issues.append({"id": sid, "level": "block", "reason": "C 级推测不得标为可立即执行"})
        if not (r.get("metric_denominator") or "").strip():
            issues.append({"id": sid, "level": "warn", "reason": "指标未写分母"})
        if not (r.get("validation") or "").strip():
            issues.append({"id": sid, "level": "warn", "reason": "缺验证方式"})
        blob = "{} {}".format(r.get("action") or "", r.get("timing") or "")
        for w in words:
            if w and w in blob:
                issues.append({"id": sid, "level": "block", "reason": "命中红线词: {}".format(w)})
    blocked_ids = {x["id"] for x in issues if x["level"] == "block"}
    return {
        "total": len(rows),
        "passed": len(rows) - len(blocked_ids),
        "blocked": len(blocked_ids),
        "issues": issues,
        "note": "只查结构与词表，语义与事实仍须红队 + 人工复核",
    }


def run(input_path, redlines_path=None):
    return lint(load_rows(input_path), load_redlines(redlines_path))


def main():
    ap = argparse.ArgumentParser(description="策略清单体检")
    ap.add_argument("--input", required=True)
    ap.add_argument("--redlines", default=None, help="可选：每行一个红线词的 txt")
    ap.add_argument("--out", default="out/lint.json")
    a = ap.parse_args()
    result = run(a.input, a.redlines)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("strategy_lint: {}/{} passed, {} blocked -> {}".format(
        result["passed"], result["total"], result["blocked"], a.out))
    return 1 if result["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
