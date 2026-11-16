"""可配置的论坛页面适配器模板。

默认通过浏览器读取公开页面。使用方须填写板块代号，并按目标页面结构调整
URL、选择器与字段映射；不得绕过登录、权限或访问控制。
"""
import re
import time
import html
import json

from . import config

FORUM_SECTION = config.COMMUNITY_FORUM_SECTION
FORUM_HOST = config.COMMUNITY_FORUM_BASE
MAX_LIST_PAGES = 3                 # 抓几页帖子列表(每页约30帖)
MAX_THREADS = 40                   # 最多抓多少个帖子的正文
REQUEST_PAUSE = 1.5                # 页面间隔(秒)，防风控

# {{COMMUNITY_FORUM}} 帖子标题前的分类标签，如 [吐槽]/[求助]/[攻略]
_TAG = re.compile(r"^\[([^\]]{1,6})\]")


def _clean(t):
    return html.unescape(re.sub(r"\s+", " ", t or "")).strip()


def _make_page():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 Chrome/120 Safari/537.36",
        locale="zh-CN",
    )
    page = ctx.new_page()
    return pw, browser, page


def _wait_ready(page, timeout=20000):
    """等待公开帖子列表渲染完成。"""
    try:
        page.wait_for_selector("article[data-thread-id]", timeout=timeout)
    except Exception:
        pass  # 即使超时也返回当前内容，由调用方判断


def collect(progress_cb=None):
    """主入口：返回 threads 列表，每项含 {tid, title, tag, text}。"""
    pw, browser, page = _make_page()
    threads = []
    try:
        # ---- 1. 抓帖子列表(多页) ----
        list_items = []
        for pn in range(1, MAX_LIST_PAGES + 1):
            url = f"{FORUM_HOST}/threads?section={FORUM_SECTION}&page={pn}"
            if progress_cb:
                progress_cb(f"[{{COMMUNITY_FORUM}}] 打开列表页 {pn}: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            _wait_ready(page)
            time.sleep(REQUEST_PAUSE)
            html_src = page.content()
            items = _parse_list(html_src)
            if progress_cb:
                progress_cb(f"[{{COMMUNITY_FORUM}}]   第{pn}页解析到 {len(items)} 帖")
            list_items.extend(items)
            if len(list_items) >= MAX_THREADS:
                break

        # 去重(置顶帖会跨页重复)
        seen, uniq = set(), []
        for it in list_items:
            if it["tid"] in seen:
                continue
            seen.add(it["tid"])
            uniq.append(it)
        list_items = uniq[:MAX_THREADS]

        # ---- 2. 逐帖抓正文 ----
        for it in list_items:
            try:
                body = _fetch_thread_body(page, it["tid"])
                it["text"] = body
            except Exception as e:
                it["text"] = ""
                if progress_cb:
                    progress_cb(f"[{{COMMUNITY_FORUM}}]   帖{it['tid']}正文失败: {e}")
            threads.append(it)
            if progress_cb:
                progress_cb(f"[{{COMMUNITY_FORUM}}] ✓ {it.get('tag','')}{it['title'][:22]}…")
            time.sleep(REQUEST_PAUSE)
    finally:
        browser.close()
        pw.stop()
    return threads


def _parse_list(html_src):
    """解析通用帖子卡片；接入时按目标公开页面调整选择器。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_src, "html.parser")
    out, seen = [], set()
    for node in soup.select("article[data-thread-id]"):
        tid = str(node.get("data-thread-id") or "").strip()
        if tid in seen:
            continue
        title_node = node.select_one(".thread-title")
        title = _clean(title_node.get_text()) if title_node else ""
        if not tid or len(title) < 2:
            continue
        seen.add(tid)
        tag = str(node.get("data-tag") or "").strip()
        out.append({"tid": tid, "title": title, "tag": tag})
    return out


def _fetch_thread_body(page, tid):
    """打开单帖，取首楼正文文本。"""
    page.goto(f"{FORUM_HOST}/threads/{tid}", wait_until="domcontentloaded",
              timeout=30000)
    _wait_ready(page, timeout=15000)
    time.sleep(0.8)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page.content(), "html.parser")
    node = soup.select_one("article[data-post-body]")
    return _clean(node.get_text()) if node else ""


if __name__ == "__main__":
    ts = collect(lambda m: print(m))
    (config.DATA_DIR / "forum_threads.json").write_text(
        json.dumps(ts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成：{{COMMUNITY_FORUM}} 帖子 {len(ts)}")
