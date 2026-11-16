# -*- coding: utf-8 -*-
"""从一个 JSON spec 一键生成{{COLLAB_PLATFORM}}在线表格（数据 + 合并 + 样式 + 边框 + 尺寸 + 验收）。

用法：
    python build_sheet.py --spec spec.json

spec 结构（见下方 EXAMPLE，也可 --dump-example 打印）：

{
  "doc_name": "表名",
  "sheet_name": "子表名",           # 可选
  "docid": "",                      # 可选：填了就复用已有表
  "grid": [[...]],                  # 完整网格，第一行 = A1 起
  "merges": ["A1:K1"],              # 合并范围
  "header_row": 4,                  # 表头行号（1-based）
  "data_last_row": 20,              # 数据末行号
  "last_col": "K",                  # 末列字母
  "band_row": 3,                    # 分类条行号（必须在表格样式范围之外）
  "note_rows": [2, 32],             # L5 备注类行（说明行 / 备注行）
  "col_widths": {"A": 130},
  "row_heights": {"1": 80, "5:20": 54}
}

执行顺序严格遵守 table-structure.md：
写数据 → 合并 → 表格样式(表头行起) → 字体样式 → 表格样式 update 边框
→ L5 内部边框 → 整体外边框 → 尺寸 → 验收
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from table_client import TableClient, BLUE  # noqa: E402

EXAMPLE = {
    "doc_name": "示例 · 资源需求表",
    "sheet_name": "资源需求表",
    "grid": [
        ["标题", "", ""],
        ["说明行", "", ""],
        ["一、需求", "", "三、交付"],
        ["字段A", "字段B", "字段C"],
        ["值1", "值2", "值3"],
    ],
    "merges": ["A1:C1", "A2:C2", "A3:B3"],
    "header_row": 4,
    "data_last_row": 5,
    "last_col": "C",
    "band_row": 3,
    "note_rows": [2],
    "col_widths": {"A": 150, "B": 200, "C": 150},
    "row_heights": {"1": 80, "2": 34, "3": 36, "4": 44, "5": 54},
}


def build(spec):
    last = spec["last_col"]
    header_row = spec["header_row"]
    data_last = spec["data_last_row"]

    if spec.get("docid"):
        ws = TableClient(spec["docid"], spec.get("sheet_id") or TableClient.first_sheet_id(spec["docid"]))
        print("复用已有表:", ws.docid, "sheet:", ws.sheet)
    else:
        ws = TableClient.create(spec["doc_name"], spec.get("sheet_name"))
        if spec.get("sheet_name"):
            ws.rename(spec["sheet_name"])

    nrows = len(spec["grid"])
    ncols = max(len(r) for r in spec["grid"])

    print("=== 1. 写数据 ===")
    ok, _ = ws.write(f"A1:{last}{nrows}", spec["grid"])
    print("  ", "OK" if ok else "FAIL")

    print("=== 2. 合并 ===")
    for r, okm in ws.merge(spec.get("merges", [])):
        print("  ", r, "OK" if okm else "FAIL")

    # 表格样式范围：从表头行开始，避开分类条行
    ts_range = f"A{header_row}:{last}{data_last}"
    print(f"=== 3. 表格样式 {ts_range} ===")
    ok, sid = ws.table_style_add(ts_range)
    print("  ", "OK" if ok else "FAIL", "tab_style_id:", sid)

    print("=== 4. 字体样式 ===")
    L = last
    styles = [
        (f"A1:{L}1", dict(font_size=18, bold=True, font_color=BLUE["l1_fg"],
                          bg_color=BLUE["l1_bg"], horizontal_align="center", vertical_align="center")),
    ]
    if spec.get("band_row"):
        b = spec["band_row"]
        styles.append((f"A{b}:{L}{b}", dict(font_size=12, bold=True, font_color=BLUE["band_fg"],
                                            bg_color=BLUE["band_bg"], horizontal_align="center",
                                            vertical_align="center")))
    styles.append((f"A{header_row}:{L}{header_row}",
                   dict(font_size=10, bold=True, font_color=BLUE["header_fg"],
                        horizontal_align="center", vertical_align="center", wrap=True)))
    if data_last > header_row:
        styles.append((f"A{header_row + 1}:{L}{data_last}",
                       dict(font_size=10, horizontal_align="center", vertical_align="center", wrap=True)))
    for r in spec.get("note_rows", []):
        styles.append((f"A{r}:{L}{r}",
                       dict(font_size=10, font_color=BLUE["note_fg"], bg_color=BLUE["note_bg"],
                            horizontal_align="left", vertical_align="center", wrap=True)))
    for rng, kw in styles:
        ok, _ = ws.style(rng, **kw)
        print("  ", rng, "OK" if ok else "FAIL")

    print("=== 5. 表格样式 update（边框色） ===")
    if sid:
        ok, _ = ws.table_style_update(sid)
        print("  ", "OK" if ok else "FAIL")

    print("=== 6. 边框 ===")
    for r in spec.get("note_rows", []):
        ok, _ = ws.border(f"A{r}:{L}{r}", ["inner_horizontal", "inner_vertical"])
        print("   L5", r, "OK" if ok else "FAIL")
    ok, out = ws.border(f"A1:{L}{nrows}", ["outer"])
    print("   整体外边框", "OK" if ok else "FAIL")

    print("=== 7. 尺寸 ===")
    if spec.get("col_widths"):
        ok, _ = ws.cols(spec["col_widths"])
        print("   列宽", "OK" if ok else "FAIL")
    if spec.get("row_heights"):
        ok, _ = ws.rows(spec["row_heights"])
        print("   行高", "OK" if ok else "FAIL")

    print("=== 8. 验收 ===")
    got = ws.merges(f"A1:{last}{nrows + 5}")
    want = set(spec.get("merges", []))
    missing = want - set(got)
    print("   合并 期望", len(want), "实际", len(got), "缺失:", missing or "无")
    ts = ws.table_style_list()
    print("   表格样式:", [(t.get("range"), t.get("has_header")) for t in ts])
    info = ws.info()
    print("   行高:", info.get("row_heights"))
    print("   列宽:", info.get("col_widths"))

    print("\n表格 URL: {{DOC_URL_PREFIX}}" + ws.docid)
    return ws


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec")
    ap.add_argument("--dump-example", action="store_true")
    a = ap.parse_args()

    if a.dump_example:
        print(json.dumps(EXAMPLE, ensure_ascii=False, indent=2))
        return
    if not a.spec:
        ap.error("需要 --spec 或 --dump-example")
    with open(a.spec, encoding="utf-8") as f:
        build(json.load(f))


if __name__ == "__main__":
    main()
