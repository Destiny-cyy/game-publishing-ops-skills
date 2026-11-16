"""命令行入口：一条命令跑完 采集 → 聚类 → 出报告。

用法(在 tools/audience-insight 目录下):
  python -m wfci.cli collect      # 只采集({{COMMUNITY_VIDEO}}评论 + 游戏数据)
  python -m wfci.cli analyze      # 只聚类分析(需先采集)
  python -m wfci.cli report       # 生成 HTML 运营洞察报告
  python -m wfci.cli all          # 采集 + 分析 + 报告 一条龙
"""
import sys
import json
import datetime

from . import config
from . import collect_video, collect_game, collect_forum, analyze, report, export


def _log(m):
    print(m, flush=True)


def cmd_collect():
    vids, coms = collect_video.collect(_log)
    (config.DATA_DIR / "video_list.json").write_text(
        json.dumps(vids, ensure_ascii=False, indent=2), encoding="utf-8")
    (config.DATA_DIR / "video_comments.json").write_text(
        json.dumps(coms, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"[采集] {{COMMUNITY_VIDEO}}：视频 {len(vids)}，评论 {len(coms)}")
    game = collect_game.collect(_log)
    (config.DATA_DIR / "game_data.json").write_text(
        json.dumps(game, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("[采集] 游戏数据已存 game_data.json")
    # {{COMMUNITY_FORUM}}(需 Playwright+chromium)：帖子含官方分类标签，是{{COMMUNITY_VIDEO}}没有的诉求信号
    try:
        threads = collect_forum.collect(_log)
        (config.DATA_DIR / "forum_threads.json").write_text(
            json.dumps(threads, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"[采集] {{COMMUNITY_FORUM}}：帖子 {len(threads)}")
    except Exception as e:
        _log(f"[采集] {{COMMUNITY_FORUM}} 跳过({e})——需先安装 playwright+chromium，见 SKILL.md")


def cmd_analyze():
    r = analyze.run(_log)
    (config.OUT_DIR / "cluster_result.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("[分析] 结果已存 {{WORK_DIR}}/output/cluster_result.json")


def cmd_report():
    cluster = json.loads(
        (config.OUT_DIR / "cluster_result.json").read_text(encoding="utf-8"))
    game = {}
    gp = config.DATA_DIR / "game_data.json"
    if gp.exists():
        game = json.loads(gp.read_text(encoding="utf-8"))
    vp = config.DATA_DIR / "video_list.json"
    meta = json.loads(vp.read_text(encoding="utf-8")) if vp.exists() else []
    out = report.build(cluster, game, meta)
    path = config.OUT_DIR / f"{{GAME_CN}}玩家群体洞察_{datetime.date.today()}.html"
    path.write_text(out, encoding="utf-8")
    _log(f"[报告] 已生成 {path}")


def cmd_export():
    export.export(_log)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "collect":
        cmd_collect()
    elif cmd == "analyze":
        cmd_analyze()
    elif cmd == "report":
        cmd_report()
    elif cmd == "export":
        cmd_export()
    elif cmd == "all":
        cmd_collect()
        cmd_analyze()
        cmd_report()
    else:
        print("未知命令:", cmd)


if __name__ == "__main__":
    main()
