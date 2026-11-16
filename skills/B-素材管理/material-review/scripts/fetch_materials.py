#!/usr/bin/env python3
"""拉取投放素材原表数据并下载唯一创意图。

用法:
  python fetch_materials.py --docid s3_xxx --sheet {{BENCHMARK_GAME_C}}素材往期 --out-dir ./data

产出:
  <out-dir>/master.csv       主表(rowid,素材ID,投放日期,用户分层,广告位置,广告标题,广告描述,图片链接,视频链接,曝光UV,点击UV)
  <out-dir>/素材图/<rowid>.jpg   按图片链接去重后的唯一创意图

注意: 原表只读，本脚本只读取不写入。
"""
import argparse
import concurrent.futures
import csv
import json
import os
import subprocess
import urllib.request


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def fetch_rows(docid, sheet):
    sql = (
        "SELECT `s_material_id`, DATE_FORMAT(`投放日期`, \"%Y-%m-%d\") AS `投放日期`, "
        "`广告类型`, `广告位置`, `广告标题`, `广告描述`, `图片链接`, `视频链接`, "
        "`曝光UV`, `点击UV` FROM `%s` ORDER BY `投放日期` ASC LIMIT 5000" % sheet
    )
    r = run(["{{TABLE_TOOL_CLI}}", "smartsheet", "records", "query", "--docid", docid, "--sql", sql])
    j = json.loads(r.stdout)
    vals = j["values"]
    rows = (json.loads(vals[0]) if isinstance(vals[0], str) else vals[0])["rows"]
    return rows


def url_of(v):
    if isinstance(v, dict):
        return v.get("url") or v.get("text") or ""
    return v or ""


def download(item, img_dir):
    rid, u = item
    path = os.path.join(img_dir, "%s.jpg" % rid)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return rid, "skip"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Referer": "{{PLATFORM_SITE}}"})
    try:
        data = urllib.request.urlopen(req, timeout=30).read()
        with open(path, "wb") as f:
            f.write(data)
        return rid, "ok"
    except Exception as e:
        return rid, "ERR %s" % e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docid", required=True)
    ap.add_argument("--sheet", required=True, help="原表子表名称（只读）")
    ap.add_argument("--out-dir", default="./data")
    ap.add_argument("--img-dir", default=None, help="图片目录，默认 <out-dir>/素材图")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    img_dir = args.img_dir or os.path.join(args.out_dir, "素材图")
    os.makedirs(img_dir, exist_ok=True)

    rows = fetch_rows(args.docid, args.sheet)
    out = []
    for i, r in enumerate(rows, 1):
        out.append({
            "rowid": i,
            "s_material_id": str(r.get("s_material_id") or ""),
            "投放日期": r.get("投放日期") or "",
            "用户分层": r.get("广告类型") or "",
            "广告位置": r.get("广告位置") or "",
            "广告标题": r.get("广告标题") or "",
            "广告描述": r.get("广告描述") or "",
            "图片链接": url_of(r.get("图片链接")),
            "视频链接": url_of(r.get("视频链接")),
            "曝光UV": r.get("曝光UV") or 0,
            "点击UV": r.get("点击UV") or 0,
        })

    master = os.path.join(args.out_dir, "master.csv")
    with open(master, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    seen, uniq = set(), []
    for r in out:
        if r["图片链接"] and r["图片链接"] not in seen:
            seen.add(r["图片链接"])
            uniq.append((r["rowid"], r["图片链接"]))

    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda it: download(it, img_dir), uniq))
    errs = [r for r in res if r[1] not in ("ok", "skip")]

    print("记录数 %d | 唯一图 %d | 下载失败 %d" % (len(out), len(uniq), len(errs)))
    print("主表: %s" % master)
    print("图片: %s" % img_dir)
    if errs:
        print("失败明细: %s" % errs[:10])


if __name__ == "__main__":
    main()
