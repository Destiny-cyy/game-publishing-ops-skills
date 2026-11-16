"""全局配置：路径、关键词、平台参数。改这里即可调整工具行为。"""
from pathlib import Path

# ---- 路径 ----
PKG_DIR = Path(__file__).resolve().parent
TOOL_DIR = PKG_DIR.parent
PROJECT_DIR = TOOL_DIR.parent.parent          # 项目根(export 对接 profile 用)
DATA_DIR = TOOL_DIR / "data"                  # 原始/中间数据
OUT_DIR = TOOL_DIR / "output"                 # 报告/图表产出
for _d in (DATA_DIR, OUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---- 采集目标 ----
# 玩家讨论关键词模板。按目标游戏的真实用语和研究问题调整后再采集。
SEARCH_KEYWORDS = [
    "{{GAME_CN}}", "{{GAME_KEYWORD}}", "{{GAME_CN}}攻略", "{{GAME_CN}}新手", "{{GAME_KEYWORD}}版本",
    "{{GAME_CN}}活动", "{{GAME_CN}}养成", "{{GAME_KEYWORD}}回归", "{{GAME_CN}}社交",
]

# 采集量由目标平台公开接口能力和研究设计共同决定。
MAX_VIDEOS_PER_KEYWORD = 20
MAX_COMMENTS_PER_VIDEO = 20
MAX_REPLIES_PAGES = 2
REQUEST_INTERVAL = 1.2      # 请求间隔(秒)，防风控

# ---- 社区数据适配器 ----
# 以下端点是配置模板。替换占位符并按目标平台公开 API 调整字段映射后再启用。
COMMUNITY_VIDEO_BASE = "https://{{COMMUNITY_VIDEO_API_HOST}}"
COMMUNITY_VIDEO_SEARCH_PATH = "{{COMMUNITY_VIDEO_SEARCH_PATH}}"
COMMUNITY_VIDEO_COMMENTS_PATH = "{{COMMUNITY_VIDEO_COMMENTS_PATH}}"
COMMUNITY_FORUM_BASE = "https://{{COMMUNITY_FORUM_HOST}}"
COMMUNITY_FORUM_SECTION = "{{COMMUNITY_FORUM_SECTION}}"

# ---- 可选游戏数据 API 适配器 ----
# 默认关闭，避免把任何具体游戏 API 当成通用能力。启用前实现一个返回
# version / active_events / news 的摘要端点，并确认平台条款与访问授权。
GAME_API_ENABLED = False
GAME_API_BASE = "https://api.{{GAME_DATA_API_HOST}}"
GAME_API_SUMMARY_PATH = "/summary"

# ---- 聚类参数 ----
CLUSTER_K = 7                # KMeans 簇数(玩家分群数)
MIN_TEXT_LEN = 6             # 短于此字数的文本丢弃
TOP_N_KEYWORDS = 12          # 每簇展示关键词数

# ---- 停用词(中文常见虚词 + 无信息量高频词) ----
# 原则：只停"确定无主题信息"的词。拿不准的别停(可能正是玩家诉求词)。
# 注：单字(的/了/是…)不必列，tokenize 里 len(w)<2 已过滤；纯数字(233/666)由正则过滤。
STOPWORDS = set("""
我们 你们 他们 这样 那样 因为 所以 如果 虽然 但是 然后 现在
可以 可能 应该 需要 觉得 知道 希望 喜欢 时候 事情 谢谢
哈哈 呵呵 emmm up主 视频 网友 楼主 回复 点赞
没有 不能 还有 这么 自己 还是 就是 真的 感觉 回来 加个 已经 出来 一下 一点
有点 非常 其实 而且 不过 或者 只是 只有 只要 除了 之前 之后 以后 一直 一定
一样 不如 不要 不是 不会 不了 直接 简单 完全 特别 基本
一种 一切 这些 那些 这种 那种 为什么
哪里 怎么样 怎么办 多少 多久 大家 别人 人家
以前 过去 将来 目前 后来 刚才 刚刚 马上 立刻 突然 终于
确实 当然 也许 大概 差不多 应当 必须 肯定
是的 好的 行了 来了 去了 有了 到了 看了 拿了 打了 用了 做了
各位 兄弟 老哥 集美 阿婆主 婆主 作者 楼上 楼下
以为 认为 看到 听说 据说 意思
可是 然而 因此 于是 尽管
游戏 视频 de up 一个 这个 是不是 发现 东西
""".split())
