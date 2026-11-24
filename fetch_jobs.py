#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2027 岗位看板 — 数据扫描脚本

数据来源（每日扫描）:
  https://github.com/speedyapply/2027-SWE-College-Jobs
  https://github.com/speedyapply/2027-AI-College-Jobs

产出:
  data/jobs.json      当日快照
  data/history.json   历史累计（用于识别"新增岗位 / 已下架"）
  data/raw/*.md       原始 markdown 留档
  index.html          静态看板（可直接打开 / 部署）

零第三方依赖，只用 Python 标准库。
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
RAW = os.path.join(DATA, "raw")

REPOS = [
    {
        "key": "SWE",
        "name": "2027-SWE-College-Jobs",
        "title": "软件工程 / SWE",
        "url": "https://github.com/speedyapply/2027-SWE-College-Jobs",
    },
    {
        "key": "AI",
        "name": "2027-AI-College-Jobs",
        "title": "人工智能 / AI-ML",
        "url": "https://github.com/speedyapply/2027-AI-College-Jobs",
    },
]

# 文件名 -> (岗位类型, 地区)
FILE_MAP = {
    "README.md": ("intern", "USA"),        # 美国实习
    "INTERN_INTL.md": ("intern", "INTL"),  # 国际实习
    "NEW_GRAD_USA.md": ("grad", "USA"),    # 美国正式（New Grad）
    "NEW_GRAD_INTL.md": ("grad", "INTL"),  # 国际正式（New Grad）
}

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) job-board-daily-scan/1.0"
TODAY = datetime.date.today()


# ---------------------------------------------------------------- 抓取

def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    return ""


def download_all():
    os.makedirs(RAW, exist_ok=True)
    got = {}
    for repo in REPOS:
        for fname in FILE_MAP:
            url = "https://raw.githubusercontent.com/speedyapply/%s/main/%s" % (repo["name"], fname)
            try:
                text = fetch(url)
            except Exception as e:
                print("  !! 下载失败 %s/%s: %s" % (repo["name"], fname, e), file=sys.stderr)
                # 保留上一份原始文件兜底
                bak = os.path.join(RAW, "%s__%s" % (repo["key"], fname))
                if os.path.exists(bak):
                    text = open(bak, encoding="utf-8").read()
                else:
                    continue
            with open(os.path.join(RAW, "%s__%s" % (repo["key"], fname)), "w", encoding="utf-8") as f:
                f.write(text)
            got[(repo["key"], fname)] = text
            print("  ok  %-8s %-16s %7d bytes" % (repo["key"], fname, len(text)))
    return got


# ---------------------------------------------------------------- 解析

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def strip_html(s):
    s = TAG_RE.sub("", s)
    s = s.replace("&amp;", "&").replace("&nbsp;", " ")
    return WS_RE.sub(" ", s).strip()


def is_row(line):
    # 只排除 markdown 表格分隔行（如 |---|---|）。注意不能用 "---" in line，
    # 因为岗位标题里含 "2027" 等内容会被误杀。
    if not line.startswith("|") or line.count("|") < 5:
        return False
    if re.match(r"^\|[\s:\-|]+\|$", line):   # 纯分隔行
        return False
    return "Company" not in line


# 上游把「付钱让普通人在家录视频给 AI 模型做训练数据」的数据采集零工放进了
# NEW_GRAD_USA.md，导致它被当成正式技术岗（它被归为"正式"是因为我的分类逻辑
# 对"不匹配关键词"的岗位默认继承文件类型）。
# 这里用精确词组排除，刻意不匹配 "Robotics Data Collection" 这类真实实习标题。
NOISE_POSITION_RE = re.compile(r"recording\s+videos?\b", re.I)
NOISE_HITS = []

INTERN_KW = ["intern", "co-op", "coop", "internship", "trainee", "practicum", "工作实习"]
GRAD_KW = [
    "new grad", "newgrad", "new graduate", "new-grad", "entry level", "entry-level",
    "full time", "full-time", "fulltime", "graduate engineer", "software engineer i",
    "sde i", "engineer i", "associate engineer", "junior engineer", "应届",
]
PHD_KW = ["phd", "ph.d", "doctoral", "doctorate", "研究生"]
HS_KW = ["high school", "highschool"]


def parse_table(text, track, default_type, default_region):
    """把一个 markdown 文件解析成 job 列表。

    表头有两种：6 列（含 Salary）和 5 列（无 Salary）。以实际读到的表头
    列名为准来定位 Salary / Location，避免用固定偏移导致两列错位。
    """
    jobs = []
    tier = "Other"
    cols = ["company", "position", "location", "salary", "posting", "age"]
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            h = strip_html(line[4:]).lower()
            if "faang" in h:
                tier = "FAANG+"
            elif "quant" in h:
                tier = "Quant"
            else:
                tier = "Other"
            continue

        # 表头行：以表头切换列定义
        if line.startswith("|") and "Company" in line and "Position" in line:
            head = [strip_html(c).strip().lower() for c in line.strip("|").split("|")]
            cols = []
            for hcell in head:
                if hcell.startswith("company"):
                    cols.append("company")
                elif hcell.startswith("position"):
                    cols.append("position")
                elif hcell.startswith("location"):
                    cols.append("location")
                elif hcell.startswith("salary"):
                    cols.append("salary")
                elif hcell.startswith("posting"):
                    cols.append("posting")
                else:
                    cols.append(hcell.split()[0] if hcell else "_")
            continue

        if not is_row(line):
            continue

        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != len(cols):
            continue

        row = dict(zip(cols, cells))

        m = re.search(r'href="([^"]+)"', row.get("posting", ""))
        if not m:
            continue
        url = m.group(1).split("?gh_jid=")[0]

        company = strip_html(row.get("company", ""))
        position = strip_html(row.get("position", ""))
        if not company or not position:
            continue

        # 剔除数据采集零工（付钱录视频给模型做训练数据），不是软件工程岗
        if NOISE_POSITION_RE.search(position):
            NOISE_HITS.append((company, position))
            continue

        location = strip_html(row.get("location", ""))
        salary = strip_html(row.get("salary", ""))
        age_txt = strip_html(row.get("age", "")) or strip_html(cells[-1])
        m_age = re.match(r"(\d+)\s*d", age_txt)
        age_days = int(m_age.group(1)) if m_age else None

        pos_low = position.lower()
        if any(k in pos_low for k in INTERN_KW):
            jtype = "intern"
        elif any(k in pos_low for k in GRAD_KW):
            jtype = "grad"
        else:
            jtype = default_type

        tags = []
        if any(k in pos_low for k in PHD_KW):
            tags.append("phd")
        if any(k in pos_low for k in HS_KW):
            tags.append("high_school")
        if "remote" in location.lower():
            tags.append("remote")
        if any(k in pos_low for k in ["co-op", "coop"]):
            tags.append("co-op")
        if re.search(r"summer\s*2027", pos_low):
            tags.append("summer2027")
        if re.search(r"(fall|jan|january)\s*2027", pos_low):
            tags.append("fall2027")
        if re.search(r"winter\s*2027", pos_low):
            tags.append("winter2027")

        salary_num = None
        salary_unit = ""
        ms = re.search(r"\$\s*([\d,]+(?:\.\d+)?)\s*(k|/hr|hr|/hour)?", salary)
        if ms:
            salary_num = float(ms.group(1).replace(",", ""))
            u = (ms.group(2) or "").lower()
            if u.startswith("/h") or u == "hr":
                salary_unit = "hour"
            elif u == "k":
                salary_num *= 1000
                salary_unit = "year"

        extra_locs = 0
        me = re.search(r"\+\s*(\d+)", location)
        if me:
            extra_locs = int(me.group(1))
            location = location.split("+")[0].strip()

        jobs.append({
            "company": company,
            "position": position,
            "location": location,
            "extra_locations": extra_locs,
            "salary": salary or "",
            "salary_num": salary_num,
            "salary_unit": salary_unit,
            "age_days": age_days,
            "age_text": age_txt,
            "type": jtype,
            "region": default_region,
            "tier": tier,
            "track": track,
            "tags": tags,
            "url": url,
        })
    return jobs


# ---------------------------------------------------------------- 创业公司渠道

def run_startup_scan():
    """自动执行创业渠道抓取（需无头浏览器），任何失败都不影响主流程。"""
    script = os.path.join(BASE, "scan_startup.py")
    if not os.path.exists(script):
        return False
    # 优先用带 playwright 的解释器：先试当前 python，再试专用 venv
    cands = [sys.executable, os.path.expanduser(
        "~/.cache/minimax-jobboard-probe/venv/bin/python")]
    tried = 0
    for exe in cands:
        if not exe or not os.path.exists(exe):
            continue
        tried += 1
        # 先确认这个解释器装了 playwright，避免无谓的失败
        probe = subprocess.run(
            [exe, "-c", "import playwright"], capture_output=True, timeout=60)
        if probe.returncode != 0:
            continue
        try:
            r = subprocess.run(
                [exe, script, "--pages", "3",
                 "--out", os.path.join(DATA, "startup_jobs.json")],
                capture_output=True, text=True, timeout=420)
            if r.returncode == 0:
                # 抓取器自己的告警（重试/单源失败）必须透出，否则会静默丢源
                for line in (r.stderr or "").splitlines():
                    if line.strip() and not line.strip().startswith("{"):
                        print("  %s" % line, file=sys.stderr)
                return True
            tail = (r.stderr or "").strip().splitlines()[-2:]
            print("  !! 创业渠道抓取失败(rc=%s): %s" % (r.returncode, tail), file=sys.stderr)
        except Exception as e:
            print("  !! 创业渠道抓取异常: %s: %s" % (type(e).__name__, e), file=sys.stderr)
    if not tried:
        print("  -- 跳过创业渠道：未找到装有 playwright 的解释器", file=sys.stderr)
    return False


def load_startup_jobs():
    """读取创业公司渠道（Wellfound / YC WAA）的抓取结果。

    这些渠道由 scan_startup.py 单独产出（需无头浏览器），失败时直接跳过，
    绝不影响 2027 校招主数据的产出。
    """
    path = os.path.join(DATA, "startup_jobs.json")
    if not os.path.exists(path):
        return []
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print("  !! 创业渠道数据读取失败: %s" % e, file=sys.stderr)
        return []
    jobs = data.get("jobs", [])
    for j in jobs:
        j.setdefault("extra_locations", 0)
        j.setdefault("tags", [])
        j.setdefault("source", "Startup")
    return jobs


# ---------------------------------------------------------------- 签证担保标记
# data/visa.json 由 visa_build.py 生成（劳工部 FY26 H-1B 数据 + 人工复核覆写）。
# 注意：有记录≠接受 CPT/OPT 实习生，无记录≠一定不担保，最终以 JD 原文为准。

VISA_PUNCT_RE = re.compile(r"[&.,\-']")


def load_visa_data():
    path = os.path.join(DATA, "visa.json")
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print("  !! visa.json 读取失败: %s" % e, file=sys.stderr)
        return None


def visa_for(company, visa_data):
    s = VISA_PUNCT_RE.sub(" ", company.upper())
    s = re.sub(r"\s+", " ", s).strip()
    return visa_data.get("map", {}).get(s)


# ---------------------------------------------------------------- 主流程

def main():
    print("扫描 %d 个清单文件 ..." % (len(REPOS) * len(FILE_MAP)))
    raw = download_all()

    jobs = []
    for repo in REPOS:
        for fname, (dtype, region) in FILE_MAP.items():
            text = raw.get((repo["key"], fname))
            if not text:
                continue
            jobs.extend(parse_table(text, repo["key"], dtype, region))

    # 标记主数据来源，便于与创业公司渠道区分
    for j in jobs:
        j["source"] = "SpeedyApply"

    # 合并创业公司渠道（Wellfound / YC WAA）
    if os.environ.get("SKIP_STARTUP") != "1":
        run_startup_scan()
    startup = load_startup_jobs()
    if startup:
        print("合并创业公司渠道 %d 条" % len(startup), file=sys.stderr)
        jobs.extend(startup)

    # 去重：同一 apply 链接只保留一条（跨文件/跨仓库可能重复）
    seen, uniq = {}, []
    for j in jobs:
        k = j["url"]
        if k in seen:
            continue
        seen[k] = j
        uniq.append(j)
    dup = len(jobs) - len(uniq)

    # 历史对比：识别新增 / 下架
    hist_path = os.path.join(DATA, "history.json")
    history = {}
    if os.path.exists(hist_path):
        try:
            history = json.load(open(hist_path, encoding="utf-8")).get("jobs", {})
        except Exception:
            history = {}

    today_str = TODAY.isoformat()
    for j in uniq:
        k = j["url"]
        rec = history.get(k)
        if rec:
            j["first_seen"] = rec.get("first_seen", today_str)
            rec["last_seen"] = today_str
            rec["closed"] = False
        else:
            j["first_seen"] = today_str
            history[k] = {"first_seen": today_str, "last_seen": today_str, "closed": False}

    for k, rec in history.items():
        if k not in seen:
            rec["closed"] = True

    core = [j for j in uniq if j.get("source") == "SpeedyApply"]
    startup_jobs = [j for j in uniq if j.get("source") != "SpeedyApply"]

    # 注入签证担保标记（无 visa.json 时静默跳过，不影响主流程）
    visa_data = load_visa_data()
    if visa_data:
        n_tag = 0
        for j in uniq:
            rec = visa_for(j["company"], visa_data)
            if rec:
                j["visa"] = rec["s"]
                j["visa_n"] = rec.get("n", 0)
                j["visa_via"] = rec.get("via", "")
                n_tag += 1
        print("  签证标记 %d/%d 条" % (n_tag, len(uniq)))
    else:
        print("  -- 未找到 data/visa.json，跳过签证标记", file=sys.stderr)
    by_source = {}
    for j in uniq:
        by_source[j.get("source", "SpeedyApply")] = by_source.get(j.get("source", "SpeedyApply"), 0) + 1

    snapshot = {
        "scanned_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "scan_date": today_str,
        "sources": [{"name": r["name"], "url": r["url"], "title": r["title"]} for r in REPOS],
        "stats": {
            "total": len(core),
            "intern": sum(1 for j in core if j["type"] == "intern"),
            "grad": sum(1 for j in core if j["type"] == "grad"),
            "swe": sum(1 for j in core if j["track"] == "SWE"),
            "ai": sum(1 for j in core if j["track"] == "AI"),
            "usa": sum(1 for j in core if j["region"] == "USA"),
            "intl": sum(1 for j in core if j["region"] == "INTL"),
            # 「今日新增」按 first_seen 统计，而不是按"本次扫描没见过的条数"：
            # 同一天重跑（本地兜底 + Actions，或多次手动触发）时口径保持一致，
            # 不会因为第二次跑就塌成个位数。
            "new_today": sum(1 for j in uniq if j.get("first_seen") == today_str),
            "dedup_removed": dup,
            "total_all": len(uniq),
            "startup_total": len(startup_jobs),
            "startup_student": sum(1 for j in startup_jobs if j["type"] in ("intern", "newgrad")),
            "startup_experienced": sum(1 for j in startup_jobs if j["type"] == "experienced"),
            "by_source": by_source,
            "visa_yes": sum(1 for j in uniq if j.get("visa") in ("ok", "auto")),
            "visa_no": sum(1 for j in uniq if j.get("visa") == "no"),
            "visa_warn": sum(1 for j in uniq if j.get("visa") == "warn"),
        },
        "jobs": uniq,
    }

    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "jobs.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)
    with open(hist_path, "w", encoding="utf-8") as f:
        json.dump({"updated": today_str, "jobs": history}, f, ensure_ascii=False)

    # 渲染看板
    tpl_path = os.path.join(BASE, "template.html")
    tpl = open(tpl_path, encoding="utf-8").read()
    payload = json.dumps(snapshot, ensure_ascii=False)
    payload = payload.replace("</script>", "<\\/script>")
    html = tpl.replace("/*__DATA__*/null", payload)
    with open(os.path.join(BASE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    s = snapshot["stats"]
    print("\n完成 %s" % snapshot["scanned_at"])
    print("  总计 %d 条（去重 %d）" % (s["total"], s["dedup_removed"]))
    print("  实习 %d / 正式 %d" % (s["intern"], s["grad"]))
    print("  SWE %d / AI %d ｜ 美国 %d / 国际 %d" % (s["swe"], s["ai"], s["usa"], s["intl"]))
    print("  今日新增 %d 条" % s["new_today"])
    if NOISE_HITS:
        print("  已剔除采集类零工 %d 条（%s 等）"
              % (len(NOISE_HITS), NOISE_HITS[0][0]))
    if s["startup_total"]:
        print("  创业渠道 %d 条（应届相关 %d / 有经验 %d）｜ %s"
              % (s["startup_total"], s["startup_student"], s["startup_experienced"],
                 " ".join("%s %d" % (k, v) for k, v in sorted(s["by_source"].items())
                          if k != "SpeedyApply")))
    print("  看板: %s" % os.path.join(BASE, "index.html"))


if __name__ == "__main__":
    main()