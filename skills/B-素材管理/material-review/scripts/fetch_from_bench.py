#!/usr/bin/env python3
"""从 wf_raw.json 生成主表 CSV 并下载唯一创意图。"""
import csv, json, os, concurrent.futures, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(BASE, "素材图")
os.makedirs(IMG, exist_ok=True)

d = json.load(open(os.path.join(BASE, "wf_raw.json"), encoding="utf-8"))
vals = d["values"]
rows = (json.loads(vals[0]) if isinstance(vals[0], str) else vals[0])["rows"]

def url_of(v):
    if isinstance(v, dict):
        return v.get("url") or v.get("text") or ""
    return v or ""

out = []
for i, r in enumerate(rows, 1):
    out.append({
        "rowid": i,
        "s_material_id": str(r.get("s_material_id") or ""),
        "投放日期": r.get("d") or "",
        "广告标题": r.get("广告标题") or "",
        "广告描述": r.get("广告描述") or "",
        "图片链接": url_of(r.get("图片链接")),
        "视频链接": url_of(r.get("视频链接")),
        "曝光UV": r.get("曝光UV") or 0,
        "点击UV": r.get("点击UV") or 0,
    })

with open(os.path.join(BASE, "master.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

seen, uniq = set(), []
for r in out:
    if r["图片链接"] and r["图片链接"] not in seen:
        seen.add(r["图片链接"])
        uniq.append((r["rowid"], r["图片链接"]))

def download(item):
    rid, u = item
    path = os.path.join(IMG, "%s.jpg" % rid)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return rid, "skip"
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Referer": "{{PLATFORM_SITE}}"})
    try:
        data = urllib.request.urlopen(req, timeout=30).read()
        open(path, "wb").write(data)
        return rid, "ok"
    except Exception as e:
        return rid, "ERR %s" % e

with concurrent.futures.ThreadPoolExecutor(8) as ex:
    res = list(ex.map(download, uniq))
errs = [r for r in res if r[1] not in ("ok", "skip")]
print("记录数 %d | 唯一图 %d | 下载失败 %d" % (len(out), len(uniq), len(errs)))
if errs:
    print("失败:", errs[:10])
