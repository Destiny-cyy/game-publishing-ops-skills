"""可配置的视频社区适配器模板。

使用方须填写公开 API 端点，并按目标平台响应结构调整字段映射。
"""
import re
import time
import json
import html
import requests

from . import config


def _make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120 Safari/537.36",
    })
    return s


def _clean(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def search_videos(session, keyword, max_videos):
    """按关键词搜索视频，返回视频元信息列表。"""
    out, pn = [], 1
    while len(out) < max_videos:
        r = session.get(
            config.COMMUNITY_VIDEO_BASE + config.COMMUNITY_VIDEO_SEARCH_PATH,
            params={"keyword": keyword, "page": pn},
            timeout=15,
        )
        r.raise_for_status()
        res = r.json().get("items") or []
        if not res:
            break
        for it in res:
            out.append({
                "aid": str(it.get("id")),
                "title": _clean(it.get("title")),
                "play": it.get("view_count") or 0,
                "reply": it.get("comment_count") or 0,
                "like": it.get("like_count") or 0,
                "pubdate": it.get("published_at"),
                "author": it.get("author"),
                "keyword": keyword,
            })
            if len(out) >= max_videos:
                break
        pn += 1
        time.sleep(config.REQUEST_INTERVAL)
    return out


def fetch_comments(session, aid, max_comments, max_pages):
    """抓取一个视频的评论区(一级评论)，返回评论列表。"""
    out, pn = [], 1
    while pn <= max_pages and len(out) < max_comments:
        r = session.get(
            config.COMMUNITY_VIDEO_BASE + config.COMMUNITY_VIDEO_COMMENTS_PATH,
            params={"content_id": aid, "page": pn, "page_size": 20},
            timeout=15,
        )
        r.raise_for_status()
        reps = r.json().get("items") or []
        if not reps:
            break
        for c in reps:
            out.append({
                "aid": str(aid),
                "user": c.get("author") or "",
                "text": c.get("text") or "",
                "like": c.get("like_count", 0),
                "ctime": c.get("published_at"),
                "reply_count": c.get("reply_count", 0),
            })
            if len(out) >= max_comments:
                break
        pn += 1
        time.sleep(config.REQUEST_INTERVAL)
    return out


def collect(progress_cb=None):
    """主入口：采集所有关键词的视频与评论。返回 (videos, comments)。"""
    s = _make_session()
    all_videos, seen_aid = [], set()
    all_comments = []

    for kw in config.SEARCH_KEYWORDS:
        vids = search_videos(s, kw, config.MAX_VIDEOS_PER_KEYWORD)
        if progress_cb:
            progress_cb(f"[{{COMMUNITY_VIDEO}}] 关键词「{kw}」搜到 {len(vids)} 个视频")
        for v in vids:
            if v["aid"] in seen_aid:
                continue
            seen_aid.add(v["aid"])
            all_videos.append(v)
            # 只对评论数>0的视频抓评论
            if v["reply"] > 0:
                cs = fetch_comments(s, v["aid"],
                                    config.MAX_COMMENTS_PER_VIDEO,
                                    config.MAX_REPLIES_PAGES)
                all_comments.extend(cs)
                if progress_cb:
                    progress_cb(f"      └ {v['title'][:24]}… 采到 {len(cs)} 条评论")
                time.sleep(config.REQUEST_INTERVAL)

    return all_videos, all_comments


if __name__ == "__main__":
    vids, coms = collect(lambda m: print(m))
    (config.DATA_DIR / "video_list.json").write_text(
        json.dumps(vids, ensure_ascii=False, indent=2), encoding="utf-8")
    (config.DATA_DIR / "video_comments.json").write_text(
        json.dumps(coms, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成：视频 {len(vids)}，评论 {len(coms)}")
