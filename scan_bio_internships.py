#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
温哥华 / BC 省 生物学相关实习岗位扫描

口径放宽：不限于植物学，覆盖 plant biology / 农学 / 生物科技 / 生态 / 海洋 /
林业 / 食品科学 / 医学研究等所有 life sciences 方向。

同时用 Indeed（无频率限制）和 LinkedIn，按 job_type="internship" 过滤。
"""
import json, os, time, datetime
from jobspy import scrape_jobs

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "bio-internships.json")

# 检索词按方向分组，便于汇报时分类
QUERIES = [
    # 植物 / 园艺 / 农业
    ("plant",  '"plant" (intern OR co-op) (science OR biology OR horticulture)'),
    ("agri",   '(agronomy OR agriculture OR agriscience) (intern OR "summer student")'),
    ("horti",  '(horticulture OR nursery OR greenhouse) (intern OR co-op OR student)'),
    # 生物科技 / 实验室
    ("biotech",'(biotech OR biotechnology OR "life sciences") (intern OR co-op)'),
    ("lab",    '("lab assistant" OR "laboratory assistant" OR "lab technician") (intern OR student) biology'),
    ("research",'"research assistant" (biology OR "plant biology" OR ecology OR botany)'),
    ("molbio", '(molecular OR microbiology OR genetics OR biochemistry) (intern OR co-op)'),
    # 生态 / 海洋 / 保护
    ("eco",    '(ecology OR ecological OR biodiversity OR conservation) (intern OR co-op)'),
    ("marine", '(marine OR ocean OR fisheries OR aquatic) (intern OR co-op OR student)'),
    ("wild",   '(wildlife OR ornithology OR mammalogy OR habitat) (intern OR co-op)'),
    # 医学研究 / 临床
    ("med",    '("clinical research" OR biomedical OR "research coordinator") (intern OR co-op)'),
    ("bioinf", '(bioinformatics OR "computational biology" OR "data scientist") (intern OR co-op) biology'),
]

LOCATIONS = [
    ("Vancouver, BC",  "温哥华"),
    ("British Columbia", "BC 省"),
]

SITES = ["indeed", "linkedin"]

def run(term, location):
    got = []
    for site in SITES:
        try:
            df = scrape_jobs(
                site_name=[site],
                search_term=term,
                location=location,
                results_wanted=25,
                hours_old=336,          # 14 天
                country_indeed="Canada",
                job_type="internship",
                verbose=0,
            )
            print(f"   {site:9s} -> {len(df)}", flush=True)
            if len(df):
                for _, r in df.iterrows():
                    got.append(r)
        except Exception as e:
            print(f"   {site:9s} !! {type(e).__name__}", flush=True)
        time.sleep(3)
    return got


def main():
    rows, seen = [], set()
    for cat, term in QUERIES:
        for loc, loc_cn in LOCATIONS:
            print(f"[{cat}] {term[:52]} @ {loc}", flush=True)
            for r in run(term, loc):
                url = r.get("job_url_direct") or r.get("job_url")
                if not url or url in seen:
                    continue
                seen.add(url)
                rows.append({
                    "category": cat,
                    "title": r.get("title"),
                    "company": r.get("company"),
                    "location": r.get("location"),
                    "date_posted": str(r.get("date_posted")),
                    "job_type": r.get("job_type"),
                    "is_remote": r.get("is_remote"),
                    "min_amount": r.get("min_amount"),
                    "max_amount": r.get("max_amount"),
                    "currency": r.get("currency"),
                    "interval": r.get("interval"),
                    "company_industry": r.get("company_industry"),
                    "skills": r.get("skills"),
                    "url": url,
                })
            time.sleep(2)

    snapshot = {
        "scanned_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "query_count": len(QUERIES) * len(LOCATIONS) * len(SITES),
        "total": len(rows),
        "jobs": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)

    print("\n===== 共 %d 条，按方向 =====" % len(rows))
    from collections import Counter
    for k, v in Counter(r["category"] for r in rows).most_common():
        print(f"  {k:10s} {v}")
    print("\n===== 标题 =====")
    for r in sorted(rows, key=lambda x: (str(x["date_posted"]), x["company"] or ""), reverse=True):
        print(f"- [{r['category']}] {r['title']} | {r['company']} | {r['location']} | {r['date_posted']}")


if __name__ == "__main__":
    main()