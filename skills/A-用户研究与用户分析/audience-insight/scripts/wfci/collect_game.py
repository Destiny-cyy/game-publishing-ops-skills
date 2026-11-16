"""可选的通用游戏数据摘要适配器。

默认关闭。使用方须自行提供符合约定的摘要端点，并确认数据访问授权。
"""
import json
import requests

from . import config


def _get(path):
    r = requests.get(config.GAME_API_BASE + path, timeout=30,
                     headers={"User-Agent": f"audience-insight/{__import__('wfci').__version__}"})
    r.raise_for_status()
    return r.json()


def _brief_summary(d):
    """将通用摘要端点压成报告使用的稳定字段。"""
    events = d.get("active_events", [])
    event_count = len(events) if isinstance(events, (list, dict)) else events
    news = d.get("news", [])
    return {
        "timestamp": d.get("timestamp"),
        "version": d.get("version"),
        "active_events": event_count or 0,
        "news_headlines": [
            n.get("title") if isinstance(n, dict) else str(n)
            for n in news[:8]
        ],
    }


def collect(progress_cb=None):
    """采集游戏数据，返回 dict。"""
    if not config.GAME_API_ENABLED:
        if progress_cb:
            progress_cb("[游戏] 通用 API 适配器未启用，跳过游戏侧摘要")
        return {"summary": {"disabled": True}}

    try:
        raw = _get(config.GAME_API_SUMMARY_PATH)
        summary = _brief_summary(raw)
        if progress_cb:
            progress_cb(f"[游戏] 摘要 OK，版本 {summary.get('version') or '未提供'}")
        return {"summary": summary}
    except Exception as e:
        if progress_cb:
            progress_cb(f"[游戏] 摘要失败: {e}")
        return {"summary": {"error": str(e)}}


if __name__ == "__main__":
    d = collect(lambda m: print(m))
    (config.DATA_DIR / "game_data.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print("游戏数据已存 game_data.json")
