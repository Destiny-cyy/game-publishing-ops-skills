#!/usr/bin/env python3
"""新建打标子表 → 分批写记录 → 设列宽 → 回读校验。

用法:
  python write_smarttable.py --docid s3_xxx --sheet {{BENCHMARK_GAME_C}}素材打标 \
      --csv ./data/tagged.csv [--options ./options.json] [--batch 50]

options.json 描述字段与单选/多选选项（缺省用 {{GAME_CN}} 标签体系 v2）:
  {"fields":[{"title":"画风","type":"single_select","options":["暗黑写实CG",...]},
             {"title":"画面元素","type":"select","options":[...]},
             {"title":"素材ID","type":"text"}]}

CSV 列名需与字段 title 对应；多选列用 '+' 分隔多个值。
已知限制: 单次提交命令行过长会报 WinError 206，故按 --batch 分批（默认 50）。
"""
import argparse
import csv
import json
import subprocess
import time

DEFAULT_FIELDS = [
    {"title": "素材ID", "type": "text", "width": 160},
    {"title": "投放日期", "type": "date_time", "width": 120},
    {"title": "用户分层", "type": "single_select", "width": 160,
     "options": ["新进投放", "号码包投放", "老用户投放", "标签投放"]},
    {"title": "广告位置", "type": "single_select", "width": 160, "options": []},
    {"title": "节点", "type": "single_select", "width": 120,
     "options": ["040档期", "050档期", "周年庆", "日常"]},
    {"title": "画风", "type": "single_select", "width": 160,
     "options": ["暗黑写实CG", "写实风", "手绘概念原画", "平面撞色风", "彩绘玻璃风", "国风", "装备UI展示", "卡通萌系"]},
    {"title": "画面元素", "type": "select", "width": 240,
     "options": ["单角色立绘", "多角色拼条", "角色战斗", "BOSS怪物", "场景风景", "游戏内地图", "装备道具", "萌系吉祥物", "大字文案", "实机"]},
    {"title": "福利呈现", "type": "single_select", "width": 160,
     "options": ["堆叠式", "独立圈圈式", "单品聚焦", "大字福利文案", "无福利"]},
    {"title": "视觉描述", "type": "text", "width": 400},
    {"title": "打标置信度", "type": "single_select", "width": 120, "options": ["高", "中", "低"]},
    {"title": "曝光UV", "type": "number", "width": 160},
    {"title": "点击UV", "type": "number", "width": 160},
    {"title": "点击率", "type": "percentage", "width": 120},
]

PROP = {
    "single_select": lambda o: {"property_single_select": {"is_quick_add": False,
                                                           "options": [{"text": t, "style": 3} for t in o]}},
    "select": lambda o: {"property_select": {"is_quick_add": False,
                                             "options": [{"text": t, "style": 10} for t in o]}},
    "date_time": lambda o: {"property_date_time": {"format": "yyyy-mm-dd", "auto_fill": False}},
    "number": lambda o: {"property_number": {"decimal_places": 0, "use_separate": True}},
    "percentage": lambda o: {"property_percentage": {"decimal_places": 2, "use_separate": False}},
    "text": lambda o: {},
}


def call(args):
    r = subprocess.run(["{{TABLE_TOOL_CLI}}"] + args, capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"errcode": -1, "raw": r.stdout[:300]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docid", required=True)
    ap.add_argument("--sheet", required=True, help="新建子表名称")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--options", default=None)
    ap.add_argument("--batch", type=int, default=50)
    args = ap.parse_args()

    fields = json.load(open(args.options, encoding="utf-8"))["fields"] if args.options else DEFAULT_FIELDS
    rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))

    payload = {"docid": args.docid, "sheet_title": args.sheet, "fields": []}
    for f in fields:
        item = {"field_title": f["title"], "field_type": f["type"]}
        item.update(PROP.get(f["type"], lambda o: {})(f.get("options", [])))
        payload["fields"].append(item)
    j = call(["smartsheet", "sheets", "add", "--json", json.dumps(payload, ensure_ascii=False)])
    print("建表 errcode=%s 字段数=%s" % (j.get("errcode"), len(j.get("fields", []))))
    if j.get("errcode") != 0:
        print(json.dumps(j)[:500])
        return

    types = {f["title"]: f["type"] for f in fields}

    def rec(r):
        v = {}
        for f in fields:
            t, name = f["type"], f["title"]
            raw = r.get(name, "")
            if t == "single_select":
                v[name] = [{"text": raw}] if raw else []
            elif t == "select":
                v[name] = [{"text": x} for x in raw.split("+") if x]
            elif t in ("number", "percentage"):
                v[name] = float(raw or 0)
            elif t == "date_time":
                v[name] = (raw or "") + " 00:00:00" if raw else ""
            else:
                v[name] = raw
        if "点击率" in v and r.get("曝光UV"):
            try:
                v["点击率"] = float(r.get("点击UV") or 0) / float(r["曝光UV"])
            except ZeroDivisionError:
                pass
        return {"values": v}

    ok, errs = 0, []
    for i in range(0, len(rows), args.batch):
        p = {"docid": args.docid, "sheet_title": args.sheet,
             "records": [rec(r) for r in rows[i:i + args.batch]]}
        j = call(["smartsheet", "records", "add", "--json", json.dumps(p, ensure_ascii=False)])
        if j.get("errcode") == 0:
            ok += len(p["records"])
        else:
            errs.append((i, str(j)[:200]))
        time.sleep(0.3)
    print("写入 %d 条 | 失败 %s" % (ok, errs))

    v = call(["smartsheet", "views", "list", "--json",
              json.dumps({"docid": args.docid, "sheet_title": args.sheet, "limit": 5}, ensure_ascii=False)])
    views = v.get("views", [])
    if views:
        ci = [{"field_title": f["title"], "width": f.get("width", 160)} for f in fields]
        p = {"docid": args.docid, "sheet_title": args.sheet, "type": "update",
             "views": [{"view_id": views[0]["view_id"], "col_infos": ci}]}
        j = call(["smartsheet", "views", "update", "--json", json.dumps(p, ensure_ascii=False)])
        print("列宽 errcode=%s" % j.get("errcode"))

    chk = call(["smartsheet", "records", "query", "--docid", args.docid,
                "--sql", "SELECT COUNT(*) AS n FROM `%s`" % args.sheet])
    try:
        n = (json.loads(chk["values"][0]) if isinstance(chk["values"][0], str) else chk["values"][0])["rows"][0]["n"]
    except Exception:
        n = "?"
    print("校验记录数: %s（应为 %d）" % (n, len(rows)))


if __name__ == "__main__":
    main()
