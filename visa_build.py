#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
签证担保标记生成器 —— 生成 data/visa.json 供 fetch_jobs.py 使用

数据来源：
  data/h1b_employers_fy26q3.json  美国劳工部 LCA 披露数据 FY2026 Q1-Q3 累计
                                  （2025-10 ~ 2026-06 全部获认证 H-1B 申请，
                                  按法定雇主名归一化名计数）

匹配规则（保守优先，宁标「未核」不误标）：
  1. 人工审核覆写表 CURATED（323 家投递清单公司，逐家人工复核过误匹配）
     -> 结果可信，直接采用 yes / no / warn
  2. 其余公司自动匹配：
     a. 强匹配：雇主名以公司名开头（允许后接 INC/LLC/CORP 等后缀）-> auto(可信)
     b. 弱匹配：仅子串命中且实体数 <= 10 且公司名 >= 6 字符 -> auto(待复核)
     c. 其余一律 unknown，不猜测

注意：H-1B 有记录 ≠ 接受 CPT/OPT 实习生，最终判定以 JD 原文为准
（搜 permanent basis / CPT / OPT）。
"""

import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

SUFFIX = re.compile(
    r"\s+(INC|INCORPORATED|LLC|LLP|LP|CORP|CORPORATION|CO|COMPANY|LTD|"
    r"LIMITED|HOLDINGS?|GROUP|PLC|GMBH|AG|SE|SA|S A|PBC|PTY|USA|US)\s*$",
    re.IGNORECASE)

NORM_RE = re.compile(r"[&.,\-']")


def norm(s):
    s = s.upper()
    s = NORM_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_suffix(name):
    """反复去掉结尾的公司后缀词，如 'Volaren Inc' -> 'VOLAREN'。"""
    prev = None
    cur = name.strip()
    while prev != cur:
        prev = cur
        cur = SUFFIX.sub("", cur).strip()
    if cur.startswith("THE "):
        cur = cur[4:]
    return cur


# 知名公司别名：法定雇主名与品牌名差异大，自动规则匹配不上
ALIASES = {
    "SPACEX": "SPACE EXPLORATION TECHNOLOGIES",
    "HEBBIA AI": "HEBBIA",
}

# 通用英文单词公司名：自动匹配噪声大，一律降级为「未核」，不猜测
DEMOTE = {"CAPITAL", "NORTH", "QUANTUM", "SWIFT", "LIGHT", "SLATE", "TERRA",
          "MARBLE", "LAVA", "WONDER", "BRAIN", "IMPACT", "CLARA", "MODAL"}


# ---- 人工审核覆写表：归一化公司名 -> 判定 --------------------------
# yes=有H-1B担保记录  no=本季度无记录  warn=存疑待复核
# 本表由人工复核产生，默认读仓库内 data/visa_curated.json；
# 也可用环境变量 VISA_CURATED 指向外部覆写文件。
CURATED_SRC = os.environ.get(
    "VISA_CURATED", os.path.join(DATA, "visa_curated.json"))


def load_curated():
    """读人工审核覆写表 {公司名: {v, note}}，转成归一化名 -> v。"""
    out = {}
    if not os.path.exists(CURATED_SRC):
        return out
    raw = json.load(open(CURATED_SRC, encoding="utf-8"))
    for name, rec in raw.items():
        base = re.sub(r"\s*[★⭐]\s*$", "", name).strip()
        out[norm(base)] = rec.get("v", "unknown")
    return out


# ---- 自动匹配 ------------------------------------------------------

def auto_status(name_core, employer_keys, employer_counts):
    """返回 (status, count)。status: auto / unknown。"""
    if not name_core or len(name_core) < 3:
        return "unknown", 0
    # a. 强匹配：key 以公司名开头（容忍 0-2 个词的后缀尾巴已在上游剥掉）
    strong = [k for k in employer_keys if k.startswith(name_core + " ") or k == name_core]
    if strong:
        return "auto", sum(employer_counts[k] for k in strong)
    # b. 弱匹配：子串命中
    subs = [k for k in employer_keys if name_core in k]
    if subs and len(subs) <= 10 and len(name_core) >= 6:
        return "auto", sum(employer_counts[k] for k in subs)
    return "unknown", 0


def main():
    h1b_path = os.path.join(DATA, "h1b_employers_fy26q3.json")
    if not os.path.exists(h1b_path):
        print("!! 缺少 %s，请先放入劳工部雇主统计文件" % h1b_path)
        raise SystemExit(1)
    h1b = json.load(open(h1b_path, encoding="utf-8"))  # 归一化雇主名 -> 认证数
    keys = sorted(h1b.keys())
    counts = h1b

    curated = load_curated()

    # 从当日快照收集所有公司名
    snap_path = os.path.join(DATA, "jobs.json")
    snap = json.load(open(snap_path, encoding="utf-8"))
    board_names = sorted({j["company"] for j in snap["jobs"]})

    vmap = {}
    n_cur, n_auto, n_unk = 0, 0, 0
    for name in board_names:
        nk = norm(name)
        core = strip_suffix(nk)
        core = ALIASES.get(core, core)
        if core in DEMOTE:
            vmap[nk] = {"s": "unknown", "n": 0, "via": ""}
            n_unk += 1
        elif nk in curated:
            vmap[nk] = {"s": curated[nk], "n": 0, "via": "curated"}
            n_cur += 1
        elif core in curated:
            vmap[nk] = {"s": curated[core], "n": 0, "via": "curated"}
            n_cur += 1
        else:
            st, cnt = auto_status(core, keys, counts)
            if st == "auto":
                vmap[nk] = {"s": "auto", "n": cnt, "via": "auto"}
                n_auto += 1
            else:
                vmap[nk] = {"s": "unknown", "n": 0, "via": ""}
                n_unk += 1

    out = {
        "updated": "2026-10-13",
        "source": "US DOL LCA Disclosure FY2026 Q1-Q3 (H-1B certified), "
                  "2025-10 ~ 2026-06",
        "note": "有记录≠接受CPT/OPT实习生；无记录≠一定不担保；以JD原文为准",
        "map": vmap,
    }
    with open(os.path.join(DATA, "visa.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    print("visa.json: 公司 %d 家（人工 %d / 自动 %d / 未核 %d）"
          % (len(vmap), n_cur, n_auto, n_unk))


if __name__ == "__main__":
    main()
