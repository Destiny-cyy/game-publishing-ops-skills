"""字面主题词频与共现（纯标准库，非语义主题模型）。

对应维度 ⑤ 主题痛点。只按使用者自填的词典做匹配，
同义/近义说法必须人工合并，反讽与黑话脚本判不了。
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def load_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_lexicon(path):
    """词典 CSV 至少含 term / theme 两列。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {
            (r.get("term") or "").strip(): (r.get("theme") or "").strip()
            for r in csv.DictReader(f)
            if (r.get("term") or "").strip() and (r.get("theme") or "").strip()
        }


def count_themes(rows, lexicon, text_col="text"):
    themes, pairs = Counter(), Counter()
    matched = 0
    for r in rows:
        text = r.get(text_col) or ""
        hits = sorted({theme for term, theme in lexicon.items() if term and term in text})
        if hits:
            matched += 1
        for t in hits:
            themes[t] += 1
        for i in range(len(hits)):
            for j in range(i + 1, len(hits)):
                pairs[(hits[i], hits[j])] += 1
    total = len(rows)
    return {
        "rows": total,
        "matched_rows": matched,
        "themes": dict(themes.most_common()),
        "co_occurrence": [
            {"pair": list(k), "count": v} for k, v in pairs.most_common()
        ],
        "limitation": "词典法字面匹配，不等于语义主题模型；同义说法需人工合并",
        "note": "频次不等于优先级，还要看影响面与严重度（见 references/02 维度⑤）",
    }


def run(input_path, lexicon_path, text_col="text"):
    rows = load_rows(input_path)
    lex = load_lexicon(lexicon_path)
    return count_themes(rows, lex, text_col)


def main():
    ap = argparse.ArgumentParser(description="主题词频与共现")
    ap.add_argument("--input", required=True)
    ap.add_argument("--lexicon", required=True)
    ap.add_argument("--text-col", default="text")
    ap.add_argument("--out", default="out/themes.json")
    a = ap.parse_args()
    result = run(a.input, a.lexicon, a.text_col)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("theme_count: {} rows, {} themes -> {}".format(
        result["rows"], len(result["themes"]), a.out))


if __name__ == "__main__":
    main()
