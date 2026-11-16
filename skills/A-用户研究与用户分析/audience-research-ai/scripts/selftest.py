"""一键自测：用最小虚构样本跑通全部脚本（纯标准库、不联网）。

先写这个自测，再让各工具通过它——用来确认「改坏了能立刻发现」。
运行：python selftest.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import data_contract
import segment
import theme_count
import sentiment_lexicon
import strategy_lint

S = HERE / "sample_data"
failures = []


def check(name, fn):
    try:
        fn()
        print("PASS", name)
    except Exception as e:
        print("FAIL", name, type(e).__name__, str(e)[:160])
        failures.append(name)


def t_contract():
    r = data_contract.run(S / "comments.csv")
    assert r["input_rows"] >= 5, "样本行数异常"
    assert r["valid_records"] >= 5, "有效记录过少"
    assert r["valid_records"] < r["input_rows"], "应能剔除重复/缺字段"
    kinds = {i["type"] for i in r["issues"]}
    assert "duplicate" in kinds, "应检出重复记录"
    assert "missing_field" in kinds, "应检出缺字段记录"
    assert r["dedup_rule"] == "user_tag + text"


def t_segment():
    r = segment.run(S / "profiles.csv", by="server_line", cross_by="device", do_rfm=True)
    assert r["rows"] >= 5, "样本行数异常"
    assert r["freq"], "频次表为空"
    assert r["cross"], "交叉表为空"
    assert r["rfm_lite"]["groups"], "分层结果为空"
    assert "cut_points" in r["rfm_lite"]


def t_theme():
    r = theme_count.run(S / "comments.csv", S / "lexicon.csv")
    assert r["rows"] >= 5
    assert r["themes"], "主题统计为空"
    assert r["matched_rows"] >= 1, "应有命中的记录"
    assert "limitation" in r, "必须写明方法局限"


def t_sentiment():
    r = sentiment_lexicon.run(S / "comments.csv", S / "lexicon.csv")
    assert r["rows"] >= 5
    assert set(r["summary"]) <= {"pos", "neg", "neutral", "mixed"}
    assert "limitation" in r, "必须写明方法局限"
    assert sum(r["summary"].values()) == r["rows"]


def t_lint():
    r = strategy_lint.run(S / "strategies.csv")
    assert r["total"] >= 4, "策略样本过少"
    assert r["blocked"] >= 1, "应能拦住至少一条不合规策略"
    assert r["passed"] >= 3, "合规策略应能放行"
    reasons = " ".join(x["reason"] for x in r["issues"])
    assert "五元组缺项" in reasons, "应检出五元组缺项"


def t_no_network_imports():
    banned = {"requests", "urllib", "http.client", "socket", "httpx", "aiohttp"}
    for mod in (data_contract, segment, theme_count, sentiment_lexicon, strategy_lint):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for b in banned:
            assert ("import " + b) not in src, "{} 含网络依赖 {}".format(mod.__name__, b)


def main():
    tests = [
        ("data_contract 入场校验", t_contract),
        ("segment 频次/交叉/分层", t_segment),
        ("theme_count 主题词频", t_theme),
        ("sentiment_lexicon 情感统计", t_sentiment),
        ("strategy_lint 策略体检", t_lint),
        ("零网络依赖", t_no_network_imports),
    ]
    for name, fn in tests:
        check(name, fn)
    print("-" * 40)
    print("RESULT: {}/{} passed".format(len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
