"""词典法情感倾向统计（纯标准库，只反映字面，不等于真实态度）。

对应维度 ④ 态度情感。反讽、黑话、玩梗必须人工复核。
情绪强度不等于持该意见的人数，不得写成人口比例。
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

VALID = {"pos", "neg"}


def load_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_lexicon(path):
    """词典 CSV 至少含 term / polarity 两列，polarity 为 pos 或 neg。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {
            (r.get("term") or "").strip(): (r.get("polarity") or "").strip()
            for r in csv.DictReader(f)
            if (r.get("term") or "").strip()
            and (r.get("polarity") or "").strip() in VALID
        }


def score(rows, lexicon, text_col="text"):
    by_record, overall = [], Counter()
    for r in rows:
        text = r.get(text_col) or ""
        pos = sum(1 for t, p in lexicon.items() if p == "pos" and t and t in text)
        neg = sum(1 for t, p in lexicon.items() if p == "neg" and t and t in text)
        label = "mixed" if pos and neg else ("pos" if pos else ("neg" if neg else "neutral"))
        overall[label] += 1
        by_record.append({"id": r.get("id", ""), "pos_hits": pos, "neg_hits": neg, "label": label})
    total = len(rows)
    return {
        "rows": total,
        "summary": dict(overall),
        "summary_pct": {k: round(v * 100 / total, 1) for k, v in overall.items()} if total else {},
        "by_record": by_record,
        "limitation": "词典法只反映字面；反讽/黑话需人工复核；情绪强度≠人数，声量≠人口比例",
        "note": "结论卡里必须写明本方法局限（见 references/02 维度④）",
    }


def run(input_path, lexicon_path, text_col="text"):
    return score(load_rows(input_path), load_lexicon(lexicon_path), text_col)


def main():
    ap = argparse.ArgumentParser(description="词典法情感统计")
    ap.add_argument("--input", required=True)
    ap.add_argument("--lexicon", required=True)
    ap.add_argument("--text-col", default="text")
    ap.add_argument("--out", default="out/sentiment.json")
    a = ap.parse_args()
    result = run(a.input, a.lexicon, a.text_col)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("sentiment: {} rows, {} -> {}".format(result["rows"], result["summary"], a.out))


if __name__ == "__main__":
    main()
