#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创业公司渠道抓取器 v2 —— Wellfound + YC Work at a Startup

只用系统已安装的 Google Chrome（无头），不额外下载 Chromium。
输出统一结构，与 fetch_jobs.py 的 speedyapply 数据字段对齐（多一个 source）。

用法:
  python scan_startup.py [--pages N] [--out data/startup_jobs.json]
"""

import argparse
import datetime
import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

OUTDIR = os.path.dirname(os.path.abspath(__file__))
WS = re.compile(r"\s+")
SAL_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s*([kKmM]?)")

JTYPE_MAP = {
    "full-time": "grad", "part-time": "grad", "contract": "grad",
    "internship": "intern", "intern": "intern", "co-op": "intern", "coop": "intern",
}


def clean(s):
    return WS.sub(" ", s or "").strip()


# ------------------------------------------------------------------ 字段推断

def parse_salary(text):
    if not text:
        return None, None, None
    nums = SAL_RE.findall(text)
    if not nums:
        return None, None, None
    raw = int(re.sub(r"\D", "", nums[0][0]) or 0)
    mult = {"k": 1000, "m": 1000000}.get(nums[0][1].lower(), 1)
    low = text.lower()
    unit = "hour" if ("/hr" in low or "per hour" in low) else "year"
    return float(raw * mult), unit, clean(text)


def norm_age(text):
    if not text:
        return None, None
    t = text.lower()
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month)", t)
    if m:
        n, u = int(m.group(1)), m.group(2)
        tbl = {"minute": (n / 1440.0, "m"), "hour": (n / 24.0, "h"),
               "day": (n, "d"), "week": (n * 7, "w"), "month": (n * 30, "d")}
        d, lbl = tbl[u]
        return round(d, 2), "%d%s" % (n, lbl)
    if "today" in t or "just posted" in t:
        return 0, "0d"
    if "yesterday" in t:
        return 1, "1d"
    return None, None


GRAD_KW = ("new grad", "newgrad", "entry level", "graduate", "campus")
ASSOC_TECH = ("engineer", "developer", "scientist", "analyst", "programmer")
# 高级岗关键词：命中则一律视为有经验岗（除非明确写 new grad）
SENIOR_KW = ("senior", "sr.", "staff", "principal", "lead ", "director", "head of",
             "vp ", "vice president", "manager", "architect", "fellow", "founder",
             " iii", " ii ")


def classify(title, jtype=""):
    """intern / newgrad / experienced

    注意：'associate' 单独出现不代表应届（HR/运营岗也有 Associate），
    必须同时是技术岗；且任何 senior/lead/founder 类高级岗都要排除。
    """
    t = ((title or "") + " " + (jtype or "")).lower()
    if any(k in t for k in ("intern", "co-op", "coop", "practicum", "werkstudent")):
        return "intern"
    is_grad = (any(k in t for k in GRAD_KW)
               or "junior" in t
               or ("associate" in t and any(k in t for k in ASSOC_TECH)))
    if is_grad and not any(k in t for k in SENIOR_KW):
        return "newgrad"
    return "experienced"


def infer_region(location):
    loc = (location or "").lower()
    eu = ["germany", "france", "uk", "united kingdom", "netherlands", "spain",
          "italy", "sweden", "poland", "czech", "ireland", "belgium", "austria",
          "switzerland", "denmark", "finland", "portugal", "israel", "estonia",
          "hungary", "romania", "greece", "croatia", "ukraine", "lithuania",
          "latvia", "india", "singapore", "australia", "japan", "korea",
          "brazil", "mexico", "argentina", "china", "taiwan", "serbia", "bulgaria"]
    if not loc.strip():
        return "INTL"
    return "INTL" if any(k in loc for k in eu) else "USA"


def infer_track(title, blurb=""):
    t = ((title or "") + " " + (blurb or "")).lower()
    ai_kw = ["machine learning", "artificial intelligence", "llm", "data scien",
             "deep learning", "nlp", "computer vision", "generative", "ml eng",
             "ai eng", "research scientist", " ml", " ai"]
    return "AI" if any(k in t for k in ai_kw) else "SWE"


# ------------------------------------------------------------------ Wellfound

WF_JS = r"""
() => {
  const norm = s => (s||'').replace(/\s+/g,' ').trim();
  const out = [];
  const links = Array.from(document.querySelectorAll("a[href^='/jobs/']"));
  for (const a of links) {
    const href = a.getAttribute('href');
    const title = norm(a.innerText);
    if (!href || !title) continue;

    // 公司：向上找公司卡，取其第一行
    let n = a, company = '';
    while (n && n !== document.body) {
      const cl = typeof n.className === 'string' ? n.className : '';
      if (cl.includes('mb-6') && cl.includes('rounded') && cl.includes('border')) {
        const lines = n.innerText.split('\n').map(norm).filter(Boolean);
        company = lines[0] || '';
        break;
      }
      n = n.parentElement;
    }
    // 岗位行 = 链接的祖父元素，形如 "TITLE Full-time $X $Y Denver+1"
    const row = a.parentElement && a.parentElement.parentElement;
    const rowText = row ? norm(row.innerText) : '';
    // 发布时间在岗位行的上层
    const box = row && row.parentElement ? row.parentElement : null;
    const boxText = box ? norm(box.innerText) : '';

    out.push({href, title, company, rowText, boxText});
  }
  return out;
}
"""


def parse_wf_row(r):
    row = r["rowText"]
    title = r["title"]
    # 去掉开头重复的 title，再切出 type / salary / location
    rest = row[len(title):].strip() if row.startswith(title) else row
    salary_txt = None
    m = re.search(r"\$\s?[\d,]+(?:\.\d+)?\s*[kKmM]?\s*[–-]+\s*\$?\s?[\d,]+(?:\.\d+)?\s*[kKmM]?(?:\s*CAD)?", row)
    if m:
        salary_txt = m.group(0)
    jtype = ""
    low = rest.lower()
    for k in ("full-time", "part-time", "contract", "internship", "intern", "co-op"):
        if low.startswith(k):
            jtype = k
            break
    loc = ""
    tail = rest
    if salary_txt:
        tail = rest.replace(salary_txt, " ")
    tail = re.sub(r"(full-time|part-time|contract|internship|intern|co-op)", " ", tail, flags=re.I)
    loc = clean(re.sub(r"\s{2,}", " ", tail))
    a_days, a_text = norm_age(r["boxText"][-120:])
    s_num, s_unit, s_txt = parse_salary(salary_txt)
    return {
        "company": r["company"],
        "position": title,
        "location": loc,
        "salary": s_txt, "salary_num": s_num, "salary_unit": s_unit,
        "age_days": a_days, "age_text": a_text,
        "type": classify(title, jtype),
        "region": infer_region(loc),
        "track": infer_track(title, r["company"]),
        "tier": "Startup",
        "source": "Wellfound",
        "url": "https://wellfound.com" + r["href"],
    }


def scrape_wellfound(ctx):
    p = open_page(ctx, "https://wellfound.com/jobs")
    out, seen = [], set()
    try:
        for sel in ["text=View all jobs", "a:has-text('View all jobs')"]:
            try:
                loc = p.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=6000)
                    break
            except Exception:
                pass
        p.wait_for_timeout(4500)

        for r in p.evaluate(WF_JS):
            if r["href"] in seen:
                continue
            seen.add(r["href"])
            out.append(parse_wf_row(r))
    finally:
        p.close()
    return out


# ------------------------------------------------------------------ WAA

WAA_CARD = "a.group.flex.flex-col"


def _waa_card(el):
    try:
        href = el.get_attribute("href")
        comp = el.locator("p.font-semibold")
        company = clean(comp.first.inner_text()) if comp.count() else ""
        desc = ""
        if comp.count():
            desc = clean(comp.first.evaluate(
                "e => e.nextElementSibling ? e.nextElementSibling.innerText : ''") or "")
        h3 = el.locator("h3")
        title = clean(h3.first.inner_text()) if h3.count() else ""
        meta = ""
        me = el.locator("p.line-clamp-2")
        if me.count():
            meta = clean(me.first.inner_text())
        elif el.locator("p").count() > 2:
            meta = clean(el.locator("p").nth(2).inner_text())
        parts = [clean(x) for x in meta.split("·") if clean(x)]
        jtype = parts[0] if parts else ""
        rest = parts[1:]
        salary_txt, locs = None, []
        for q in rest:
            if re.search(r"\$\d", q):
                salary_txt = q
            else:
                locs.append(q)
        s_num, s_unit, s_txt = parse_salary(salary_txt or meta)
        loc = ", ".join(locs)
        return {
            "company": company, "position": title, "location": loc,
            "salary": s_txt, "salary_num": s_num, "salary_unit": s_unit,
            "meta": meta, "jtype": jtype, "desc": desc,
            "url": "https://www.workatastartup.com" + (href or ""),
        }
    except Exception:
        return None


def open_page(ctx, url, attempts=4, timeout=60000):
    """打开页面并等待渲染完成；失败时重试。

    WAA 站点在连续抓取时导航会卡住（实测出现过 45s / 60s 超时），
    每次重试都换一个全新页面，并递增退避间隔。
    """
    last = None
    for i in range(attempts):
        p = ctx.new_page()
        try:
            p.goto(url, wait_until="domcontentloaded", timeout=timeout)
            try:
                p.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            p.wait_for_timeout(3000)
            return p
        except Exception as e:
            last = e
            try:
                p.close()
            except Exception:
                pass
            print("    重试 %d/%d %s: %s"
                  % (i + 1, attempts, url, str(e).splitlines()[0][:90]), file=sys.stderr)
            time.sleep(5 * (i + 1))
    raise last


def scrape_waa(ctx, pages=3):
    p = open_page(ctx, "https://www.workatastartup.com/jobs")
    out, seen = [], set()
    try:
        def harvest():
            cards = p.locator(WAA_CARD)
            n = cards.count()
            added = 0
            for i in range(n):
                d = _waa_card(cards.nth(i))
                if not d or not d["position"] or d["url"] in seen:
                    continue
                seen.add(d["url"])
                added += 1
                out.append({
                    "company": d["company"], "position": d["position"],
                    "location": d["location"], "salary": d["salary"],
                    "salary_num": d["salary_num"], "salary_unit": d["salary_unit"],
                    "age_days": None, "age_text": None,
                    "type": classify(d["position"], d["jtype"]),
                    "region": infer_region(d["location"]),
                    "track": infer_track(d["position"], d["desc"]),
                    "tier": "YC", "source": "YC WAA",
                    "url": d["url"],
                })
            return n, added

        n, added = harvest()
        print("    WAA page 1: %d cards (+%d new)" % (n, added), file=sys.stderr)

        for pg in range(1, pages):
            nxt = p.locator("text=Next").first
            try:
                if not (nxt.count() and nxt.is_visible()):
                    print("    WAA: no Next button, stop", file=sys.stderr)
                    break
                nxt.click(timeout=10000)
            except Exception as e:
                print("    WAA: Next click failed %s" % e, file=sys.stderr)
                break
            # 翻页是渐进的，多等并滚动触发加载
            for _ in range(6):
                p.wait_for_timeout(1200)
                p.mouse.wheel(0, 3000)
            p.wait_for_timeout(1500)
            n, added = harvest()
            print("    WAA page %d: %d cards (+%d new)" % (pg + 1, n, added), file=sys.stderr)
            if added == 0:
                break
    finally:
        p.close()
    return out


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(OUTDIR, "data", "startup_jobs.json"))
    a = ap.parse_args()

    res = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--disable-blink-features=AutomationControlled"])

        def new_ctx():
            # 每个站点独立上下文：避免上一个站点的后台请求拖垮下一个
            c = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                              locale="en-US", timezone_id="America/New_York")
            c.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
            return c

        print("scanning Wellfound ...", file=sys.stderr)
        ctx = new_ctx()
        try:
            res["Wellfound"] = scrape_wellfound(ctx)
        except Exception as e:
            print("  !! wellfound failed: %s: %s" % (type(e).__name__, e), file=sys.stderr)
            res["Wellfound"] = []
        finally:
            ctx.close()
        print("  wellfound: %d" % len(res["Wellfound"]), file=sys.stderr)

        # 换站前先让浏览器喘口气：WAA 紧随 Wellfound 抓取时导航容易卡死
        time.sleep(5)
        print("scanning YC WAA (%d pages) ..." % a.pages, file=sys.stderr)
        ctx = new_ctx()
        try:
            res["YC WAA"] = scrape_waa(ctx, a.pages)
        except Exception as e:
            print("  !! waa failed: %s: %s" % (type(e).__name__, e), file=sys.stderr)
            res["YC WAA"] = []
        finally:
            ctx.close()
        print("  waa: %d" % len(res["YC WAA"]), file=sys.stderr)
        b.close()

    jobs = [j for v in res.values() for j in v]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({
            "scanned_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "counts": {k: len(v) for k, v in res.items()},
            "jobs": jobs,
        }, f, ensure_ascii=False, indent=2)
    print(json.dumps({"counts": {k: len(v) for k, v in res.items()},
                      "total": len(jobs), "out": a.out}, ensure_ascii=False),
          file=sys.stderr)


if __name__ == "__main__":
    main()