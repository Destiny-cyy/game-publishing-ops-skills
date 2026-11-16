#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
场景配置（profile）加载器 · 给 plan-lint / prize-calc / {{可选工具·表格读取}} 共用。

规则分三层：
  1. rules.json  —— 硬红线（全局恒真，任何场景都不许改）
  2. profiles/*.json —— 场景参数（渠道、平台、节点、预算、奖池、任务、口径、排期）
  3. 历史基线 —— 只作参照，写在 profile 的 note / baseline_ref 里，不作硬指标

profile 支持 extends 继承（可多级），子档只写差异项；dict 递归合并，list 与标量直接覆盖。
这样换业务背景＝换一个档，而不是改脚本或改全局规则。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(HERE, "rules.json")
PROFILES_DIR = os.path.join(HERE, "profiles")


def load_rules(path=None):
    with open(path or RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _deep_merge(base, child):
    out = dict(base)
    for k, v in child.items():
        if k == "extends":
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_profile_file(profile_id):
    p = os.path.join(PROFILES_DIR, profile_id + ".json")
    if not os.path.exists(p):
        raise FileNotFoundError("找不到场景档：%s（目录 %s）" % (profile_id, PROFILES_DIR))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_profile(rules=None, name=None, _seen=None):
    """name 可以是档 id、绝对路径，或 None（用 rules.default_profile）。"""
    rules = rules or load_rules()
    name = name or rules.get("default_profile", "base")
    _seen = _seen or set()

    if os.path.isabs(name) or os.path.sep in name or name.endswith(".json"):
        path = name if os.path.isabs(name) else os.path.join(HERE, name)
        with open(path, encoding="utf-8") as f:
            prof = json.load(f)
    else:
        if name in _seen:
            raise ValueError("场景档 extends 成环：%s" % name)
        _seen.add(name)
        prof = _read_profile_file(name)

    parent_id = prof.get("extends")
    if parent_id:
        parent = load_profile(rules, parent_id, _seen)
        prof = _deep_merge(parent, prof)

    prof.setdefault("id", name)
    # 硬红线不允许被任何场景档覆盖，强制回填
    prof["_hard_rules"] = rules.get("layers", {}).get("hard", {}).get("items", [])
    return prof


def list_profiles():
    if not os.path.isdir(PROFILES_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(PROFILES_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(PROFILES_DIR, fn), encoding="utf-8") as f:
            d = json.load(f)
        out.append((d.get("id", fn[:-5]), d.get("name", ""), d.get("extends", "")))
    return out


def scene_get(prof, dotted, default=None):
    """按点路径取场景参数，缺字段时返回 default（不抛异常）。"""
    cur = prof
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur or cur[part] is None:
            return default
        cur = cur[part]
    return cur


if __name__ == "__main__":
    r = load_rules()
    print("rules v%s  mode=%s  default=%s" % (r["version"], r["mode"], r["default_profile"]))
    for pid, pname, parent in list_profiles():
        p = load_profile(r, pid)
        print("  %-28s %-38s extends=%-24s channels=%d prize_model=%s" % (
            pid, pname, parent or "-", len(p.get("channels", [])),
            scene_get(p, "prize.model", "-")))
