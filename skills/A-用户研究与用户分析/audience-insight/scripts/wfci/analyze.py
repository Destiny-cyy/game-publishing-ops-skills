"""聚类分析：对玩家评论做中文分词 → TF-IDF 向量化 → KMeans 分群 → 关键词画像。
轻量经典方案(秒级出结果、结果可解释)。预留语义升级接口(见 embed_upgrade 注释)。
"""
import json
import re
from collections import Counter

import jieba
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

from . import config

# 预编译：去URL/表情
_RE_URL = re.compile(r"https?://\S+|www\.\S+")
_RE_EMOJI = re.compile(r"\[[^\]]{1,8}\]")          # {{COMMUNITY_VIDEO}}表情 [doge] 之类


def clean_text(t):
    t = _RE_URL.sub(" ", t or "")
    t = _RE_EMOJI.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tokenize(t):
    """中文分词 + 停用词过滤 + 去单字。"""
    toks = []
    for w in jieba.cut(clean_text(t)):
        w = w.strip()
        if len(w) < 2:                 # 去单字(中文单字信息量低)
            continue
        if w in config.STOPWORDS:
            continue
        if re.fullmatch(r"[\d\W_]+", w):
            continue
        toks.append(w)
    return toks


def load_comments():
    """从采集结果读评论，返回清洗后的文本列表 + 元信息。
    同时合并 {{COMMUNITY_VIDEO}}评论 + {{COMMUNITY_FORUM}} 帖子(标题+正文)，来源记在 source 字段。"""
    items = []
    seen = set()

    def _add(txt, user, like, source, extra=None):
        txt = clean_text(txt or "")
        if len(txt) < config.MIN_TEXT_LEN:
            return
        key = txt[:40]
        if key in seen:                # 去重(复制粘贴刷屏)
            return
        seen.add(key)
        it = {"text": txt, "user": user, "like": like, "source": source}
        if extra:
            it.update(extra)
        items.append(it)

    # ---- {{COMMUNITY_VIDEO}}评论 ----
    bp = config.DATA_DIR / "video_comments.json"
    if bp.exists():
        for c in json.loads(bp.read_text(encoding="utf-8")):
            _add(c.get("text"), c.get("user"), c.get("like", 0), "{{COMMUNITY_VIDEO_HOST}}",
                 {"aid": c.get("aid")})
    # ---- {{COMMUNITY_FORUM}} 帖子(标题+正文合并，带官方分类标签) ----
    np_ = config.DATA_DIR / "forum_threads.json"
    if np_.exists():
        for t in json.loads(np_.read_text(encoding="utf-8")):
            body = t.get("text", "")
            # 标题信息量大，拼进文本一起聚类；标签单列供报告统计
            txt = (t.get("title", "") + " " + body).strip()
            _add(txt, t.get("author", "{{COMMUNITY_FORUM}}用户"), 0, "community_forum",
                 {"tag": t.get("tag", ""), "tid": t.get("tid")})

    if not items:
        raise FileNotFoundError("无数据。先运行采集：python -m wfci.cli collect")
    return items


def cluster(items, k=None):
    """TF-IDF + KMeans。返回 (labels, vectorizer, kmeans, terms)。"""
    k = k or config.CLUSTER_K
    corpus = [" ".join(tokenize(it["text"])) for it in items]
    # 过滤掉分词后为空的样本
    keep = [i for i, c in enumerate(corpus) if c.strip()]
    items = [items[i] for i in keep]
    corpus = [corpus[i] for i in keep]
    if len(items) < k:
        raise ValueError(f"有效样本 {len(items)} 少于簇数 {k}，先多采点数据")

    vec = TfidfVectorizer(max_features=3000, min_df=2, max_df=0.6)
    X = vec.fit_transform(corpus)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    terms = np.array(vec.get_feature_names_out())
    return items, km.labels_, vec, km, terms


def cluster_profiles(items, labels, vec, km, terms, top_n=None):
    """为每个簇生成画像：关键词、样本量、高赞代表评论、情感粗判。"""
    top_n = top_n or config.TOP_N_KEYWORDS
    profiles = []
    for ci in range(km.n_clusters):
        idx = [i for i, l in enumerate(labels) if l == ci]
        if not idx:
            continue
        # 簇中心关键词
        center = km.cluster_centers_[ci]
        top_terms = terms[np.argsort(center)[::-1][:top_n]].tolist()
        # 该簇高赞评论(代表声音)
        members = sorted((items[i] for i in idx),
                         key=lambda x: x["like"], reverse=True)
        samples = [m["text"][:60] for m in members[:5]]
        # 高频词(更直观)
        word_freq = Counter()
        for m in members:
            word_freq.update(tokenize(m["text"]))
        profiles.append({
            "cluster": ci,
            "size": len(idx),
            "share_pct": round(100.0 * len(idx) / len(labels), 1),
            "top_keywords": top_terms,
            "top_words": word_freq.most_common(15),
            "avg_like": round(sum(m["like"] for m in members) / len(members), 1),
            "sample_comments": samples,
        })
    profiles.sort(key=lambda p: p["size"], reverse=True)
    return profiles


# ---- 语义升级接口(预留，默认关闭) ----
# 如需语义向量聚类，请单独选择许可证兼容的实现与模型，并评估下载体积、
# 推理成本和数据传输边界；本模板默认只使用本地 TF-IDF。
def embed_upgrade_available():
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def run(progress_cb=None):
    items = load_comments()
    if progress_cb:
        progress_cb(f"[分析] 有效样本 {len(items)} 条，开始聚类…")
    items, labels, vec, km, terms = cluster(items)
    profiles = cluster_profiles(items, labels, vec, km, terms)
    # 来源分布 + {{COMMUNITY_FORUM}}官方标签分布({{COMMUNITY_FORUM}}独有价值)
    src = Counter(it.get("source", "?") for it in items)
    tag_dist = Counter(it.get("tag") for it in items
                       if it.get("source") == "community_forum" and it.get("tag"))
    if progress_cb:
        progress_cb(f"[分析] 完成，得到 {len(profiles)} 个玩家群体")
    return {"n_samples": len(items), "n_clusters": len(profiles),
            "profiles": profiles,
            "source_dist": dict(src),
            "forum_tag_dist": dict(tag_dist.most_common())}


if __name__ == "__main__":
    import sys
    r = run(lambda m: print(m))
    (config.OUT_DIR / "cluster_result.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    for p in r["profiles"]:
        print(f"\n◆ 群体{p['cluster']}  {p['size']}人({p['share_pct']}%)  均赞{p['avg_like']}")
        print("  关键词:", " / ".join(p["top_keywords"][:8]))
