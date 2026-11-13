#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全加拿大 生物学相关实习岗位扫描

地域口径放宽到全国（location="Canada"），方向覆盖 life sciences 全谱系。
LinkedIn 全球搜索、不需要 country_indeed；Indeed 加拿大覆盖偏弱但一并尝试。
"""
import json, os, time, datetime
from collections import Counter
from jobspy import scrape_jobs

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "bio-internships-canada.json")

QUERIES = [
    ("plant",   '(plant OR botany OR horticulture) (intern OR co-op)'),
    ("agri",    '(agronomy OR agriculture OR agronomy OR agriscience) (intern OR "summer student")'),
    ("forest",  '(forestry OR silviculture OR "forest management") (intern OR "summer student")'),
    ("biotech", '(biotech OR biotechnology OR "life sciences" OR "molecular biology") (intern OR co-op)'),
    ("lab",     '("lab assistant" OR "laboratory technician" OR "research assistant") biology intern'),
    ("eco",     '(ecology OR ecological OR biodiversity OR conservation) (intern OR co-op)'),
    ("marine",  '(marine biology OR ocean OR fisheries OR aquatic) (intern OR co-op)'),
    ("wild",    '(wildlife OR zoology OR ornithology) (intern OR co-op)'),
    ("med",     '("clinical research" OR biomedical OR "research assistant") (intern OR co-op)'),
    ("food",    '("food science" OR foodscapes OR "plant pathology") (intern OR co-op)'),
    ("data",    '(bioinformatics OR "computational biology" OR "data analyst") biology (intern OR co-op)'),
    ("env",     '("environmental science" OR "environmental consultant") (intern OR co-op)'),
]


def run(term, loc, sites):
    got = []
    for site in sites:
        try:
            df = scrape_jobs(
                site_name=[site],
                search_term=term,
                location=loc,
                results_wanted=30,
                hours_old=336,
                country_indeed="Canada",
                job_type="internship",
                verbose=0,
            )
            print(f"   {site:9s} -> {len(df)}", flush=True)
            if len(df):
                for _, r in df.iterrows():
                    got.append(r)
        except Exception as e:
            print(f"   {site:9s} !! {type(e).__name__}: {e}", flush=True)
        time.sleep(3)
    return got


def main():
    rows, seen = [], set()
    for cat, term in QUERIES:
        print(f"[{cat}] {term[:56]} @ Canada", flush=True)
        for r in run(term, "Canada", ["linkedin", "indeed"]):
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

    snap = {
        "scanned_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "scope": "Canada (nationwide)",
        "total": len(rows),
        "jobs": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)

    print("\n===== 共 %d 条 =====" % len(rows))
    for k, v in Counter(r["category"] for r in rows).most_common():
        print(f"  {k:10s} {v}")
    print("\n===== 省份分布 =====")
    prov = []
    for r in rows:
        loc = (r["location"] or "")
        for p in ["British Columbia", "Ontario", "Quebec", "Alberta", "Manitoba",
                  "Saskatchewan", "Nova Scotia", "New Brunswick", "Newfoundland",
                  "Prince Edward Island", "Yukon", "Northwest Territories", "Nunavut"]:
            if p in loc:
                prov.append(p); break
    for k, v in Counter(prov).most_common():
        print(f"  {k:22s} {v}")
    print("\n===== 岗位 =====")
    for r in sorted(rows, key=lambda x: (str(x["date_posted"]), x["company"] or ""), reverse=True):
        print(f"- [{r['category']}] {r['title']} | {r['company']} | {r['location']} | {r['date_posted']}")


if __name__ == "__main__":
    main()