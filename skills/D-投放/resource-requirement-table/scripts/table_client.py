# -*- coding: utf-8 -*-
"""{{COLLAB_PLATFORM}}在线表格操作封装。

统一管理 {{TABLE_TOOL_CLI}} 调用：建表、写数据、合并、表格样式、字体样式、边框、尺寸、验收。
所有方法返回 (ok: bool, raw: str)。

用法：
    from table_client import TableClient
    ws = TableClient.create("表名", "子表名")
    ws.write("A1:K20", grid)
    ws.merge(["A1:K1", "A2:K2"])
    ...
"""
import json
import subprocess

BLUE = {
    "l1_bg": "FF267EF0",
    "l1_fg": "FFFFFFFF",
    "band_bg": "FF184785",
    "band_fg": "FFFFFFFF",
    "header_fill": "#D4E5FC",
    "header_fg": "FF184785",
    "band1": "#FFFFFF",
    "band2": "#E4F9FE",
    "note_bg": "FFF0F1F1",
    "note_fg": "FF6D7176",
    "border": "#85888C",
    "border_ff": "FF85888C",
}


class TableClient:
    def __init__(self, docid, sheet_id):
        self.docid = docid
        self.sheet = sheet_id

    # ---------- 底层 ----------
    @staticmethod
    def _cli(args, payload=None, log=True):
        cmd = ["{{TABLE_TOOL_CLI}}"] + args
        if payload is not None:
            cmd += ["--json", json.dumps(payload, ensure_ascii=False)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        out = (r.stdout or "") + (r.stderr or "")
        ok = '"errcode": 0' in out
        if log and not ok:
            print("  [FAIL]", " ".join(args[:3]), out.strip()[-200:])
        return ok, out

    # ---------- 建表 ----------
    @classmethod
    def create(cls, doc_name, sheet_title=None):
        ok, out = cls._cli(["doc", "create"], {
            "doc_type": "sheet",
            "doc_name": doc_name,
            **({"sheet_title": sheet_title} if sheet_title else {}),
        })
        if not ok:
            raise RuntimeError("建表失败: " + out[-300:])
        data = json.loads(out)
        docid = data.get("docid")
        print("新建表格 docid:", docid)
        print("URL:", data.get("url"))
        return cls(docid, cls.first_sheet_id(docid))

    @staticmethod
    def first_sheet_id(docid):
        ok, out = TableClient._cli(["sheet", "workbook", "get"], {"docid": docid}, log=False)
        data = json.loads(out)
        sheets = data.get("sheets") or data.get("sheet_list") or []
        if not sheets:
            raise RuntimeError("拿不到子表: " + out[-300:])
        return sheets[0].get("sheet_id")

    def rename(self, name):
        return self._cli(["sheet", "subsheets", "rename"],
                         {"docid": self.docid, "sheet": self.sheet, "name": name})

    # ---------- 数据 ----------
    def write(self, range_, cells):
        return self._cli(["sheet", "cells", "batchset"],
                         {"docid": self.docid, "sheet": self.sheet,
                          "range": range_, "cells": cells})

    def read(self, range_, csv=True):
        return self._cli(["sheet", "cells", "get"],
                         {"docid": self.docid, "sheet": self.sheet,
                          "range": range_, "csv": csv}, log=False)

    # ---------- 合并 ----------
    def merge(self, ranges):
        results = []
        for r in ranges:
            ok, _ = self._cli(["sheet", "merge", "set"],
                              {"docid": self.docid, "sheet": self.sheet,
                               "range": r, "merge_type": "all"})
            results.append((r, ok))
        return results

    def unmerge(self, ranges):
        results = []
        for r in ranges:
            ok, _ = self._cli(["sheet", "merge", "clear"],
                              {"docid": self.docid, "sheet": self.sheet,
                               "range": r, "yes": True})
            results.append((r, ok))
        return results

    def merges(self, range_="A1:AZ200"):
        ok, out = self._cli(["sheet", "merge", "get"],
                            {"docid": self.docid, "sheet": self.sheet,
                             "range": range_}, log=False)
        try:
            return json.loads(out).get("merges", [])
        except Exception:
            return []

    # ---------- 表格样式 ----------
    def table_style_add(self, range_, header_row=True, filter_button=True, theme=BLUE):
        ok, out = self._cli(["sheet", "table", "style", "add"], {
            "docid": self.docid, "sheet": self.sheet, "range": range_,
            "header_row": header_row, "first_column": False, "last_column": False,
            "filter_button": filter_button,
            "header_fill_color": theme["header_fill"],
            "band_fill_color": theme["band1"],
            "second_band_fill_color": theme["band2"],
            "row_band_border_color": theme["border"],
            "column_band_border_color": theme["border"],
            "outer_border_color": theme["border"],
        })
        try:
            sid = json.loads(out).get("tab_style_id")
        except Exception:
            sid = None
        return ok, sid

    def table_style_update(self, tab_style_id, header_row=True, filter_button=True, theme=BLUE):
        return self._cli(["sheet", "table", "style", "update"], {
            "docid": self.docid, "sheet": self.sheet, "tab_style_id": str(tab_style_id),
            "header_row": header_row, "first_column": False, "last_column": False,
            "filter_button": filter_button,
            "header_fill_color": theme["header_fill"],
            "band_fill_color": theme["band1"],
            "second_band_fill_color": theme["band2"],
            "row_band_border_color": theme["border"],
            "column_band_border_color": theme["border"],
            "outer_border_color": theme["border"],
        })

    def table_style_delete(self, tab_style_id):
        return self._cli(["sheet", "table", "style", "delete"],
                         {"docid": self.docid, "sheet": self.sheet,
                          "tab_style_id": str(tab_style_id), "yes": True})

    def table_style_list(self):
        ok, out = self._cli(["sheet", "table", "style", "list"],
                            {"docid": self.docid, "sheet": self.sheet}, log=False)
        try:
            return json.loads(out).get("tab_styles") or json.loads(out).get("styles") or []
        except Exception:
            return []

    # ---------- 字体样式 ----------
    def style(self, range_, **kw):
        payload = {"docid": self.docid, "sheet": self.sheet, "range": range_}
        payload.update(kw)
        return self._cli(["sheet", "style", "set"], payload)

    # ---------- 边框 ----------
    def border(self, range_, positions, theme=BLUE):
        return self._cli(["sheet", "border", "set"], {
            "docid": self.docid, "sheet": self.sheet, "range": range_,
            "positions": positions, "style": "thin", "color": theme["border_ff"],
        })

    # ---------- 尺寸 ----------
    def cols(self, col_widths, range_="A:Z"):
        return self._cli(["sheet", "dims", "resize"],
                         {"docid": self.docid, "sheet": self.sheet,
                          "range": range_, "col_widths": col_widths})

    def rows(self, row_heights, range_="1:200"):
        return self._cli(["sheet", "dims", "resize"],
                         {"docid": self.docid, "sheet": self.sheet,
                          "range": range_, "row_heights": row_heights})

    # ---------- 验收 ----------
    def info(self, include=("merges", "row_heights", "col_widths")):
        ok, out = self._cli(["sheet", "info", "get"],
                            {"docid": self.docid, "sheet": self.sheet,
                             "include": list(include)}, log=False)
        try:
            return json.loads(out)
        except Exception:
            return {}
