# JobSpy 中文速查表

> 原始文档：[speedyapply/JobSpy README](https://github.com/speedyapply/JobSpy)
> 原文存档：`docs/JobSpy-README.md`
> 整理日期：2026-10-09 ｜ 对应本机版本：python-jobspy 1.2.0

---

## 一、基本信息

| 项 | 值 |
|---|---|
| PyPI 包名 | `python-jobspy`（**注意带 python- 前缀**） |
| import 名 | `jobspy` |
| 版本 | 1.2.0 |
| 作者| Cullen Watson |
| 许可证 | MIT |
| Python 要求 | >= 3.10 |
| 本机路径 | `/opt/anaconda3/lib/python3.12/site-packages/jobspy` |
| 依赖 | beautifulsoup4, curl_cffi, markdownify, pandas, pydantic, requests |

**查是否安装用全名**（`pip show jobspy` 查不到，会误判）：

```bash
python3 -m pip show python-jobspy
```

---

## 二、最小可用示例

```python
from jobspy import scrape_jobs

jobs = scrape_jobs(
    site_name=["linkedin"],           # 不写则全部站点都跑
    search_term="software engineer",
    location="San Francisco, CA",
    results_wanted=20,                # 每个站点各取多少条
    hours_old=72,                     # 只看 72 小时内发布的
    country_indeed='USA',
)
print(f"Found {len(jobs)} jobs")
print(jobs.head())
jobs.to_csv("jobs.csv", index=False)
```

---

## 三、核心参数

| 参数 | 说明 |
|---|---|
| `site_name` | `linkedin` / `indeed` / `glassdoor` / `zip_recruiter` / `google` / `bayt` / `bdjobs` / `naukri` / `hellowork`，默认全部 |
| `search_term` | 搜索词 |
| `google_search_term` | 仅对 google 站点生效 |
| `location` | 地点，如 `"Vancouver, BC"` |
| `distance` | 半径（英里），默认 50 |
| **`job_type`** | **`fulltime` / `parttime` / `internship` / `contract` ← 实习/正式分类直接用它** |
| `proxies` | `['user:pass@host:port', 'localhost']`，各站点轮询使用 |
| `is_remote` | 布尔，筛远程岗 |
| `results_wanted` | 每个站点的结果数 |
| `easy_apply` | 只保留支持站内一键申请的 |
| `user_agent` | 覆盖默认 UA（默认 UA 可能过时） |
| `description_format` | `markdown`（默认）/ `html` |
| `offset` | 从第 N 条开始取，如 25 |
| `hours_old` | 按发布时间过滤（小时） |
| `verbose` | 0=仅错误，1=错误+警告（默认），2=全部日志 |
| `fetch_description` | 抓取 JD 正文。**每个岗位多一次请求，大批量搜索务必配 proxy** |
| `linkedin_company_ids` | 按 LinkedIn 公司 ID 过滤 |
| `country_indeed` | Indeed/Glassdoor 的国家过滤，**必须用文档里的准确拼写** |
| `enforce_annual_salary` | 统一换算成年薪 |
| `ca_cert` | proxy 的 CA 证书路径 |

---

## 四、各站点的地理规则（重要）

| 站点 | 规则 |
|---|---|
| **LinkedIn** | **全球搜索**，只用 `location` 参数，不需要 `country_indeed` |
| ZipRecruiter | 只覆盖 **美国/加拿大**，只用 `location` |
| **Indeed / Glassdoor** | 支持多国，但**必须传 `country_indeed`**，且 `location` 要写到城市级别 |
| Bayt | 除非 location 指定国家，否则搜所有国家 |
| BDJobs | 孟加拉国 |
| Naukri | 印度 |
| HelloWork | 法国，多数岗位法语发布，**用法语搜索词效果更好** |

`country_indeed` 支持的国家：Argentina, Australia, Austria, Bahrain, Belgium, Brazil, **Canada**, Chile, China, Colombia, Costa Rica, Czech Republic, Denmark, Ecuador, Egypt, Finland, France, Germany, Greece, Hong Kong, Hungary, India, Indonesia, Ireland, Israel, Italy, Japan, Kuwait, Luxembourg, Malaysia, Mexico, Morocco, Netherlands, New Zealand, Nigeria, Norway, Oman, Pakistan, Panama, Peru, Philippines, Poland, Portugal, Qatar, Romania, Saudi Arabia, Singapore, South Africa, South Korea, Spain, Sweden, Switzerland, Taiwan, Thailand, Turkey, Ukraine, UAE, UK, USA, Uruguay, Venezuela, Vietnam（带 * 的同时支持 Glassdoor）

---

## 五、性能与风控（踩坑重点）

| 站点 | 表现 |
|---|---|
| **Indeed** | **目前最好用，无频率限制**，首选 |
| LinkedIn | 请求密集会返回 **429**，约 1 分钟后恢复；大批量搜索需配 proxy |
| Glassdoor | 超过约 2 请求/秒会限流 |
| 通用 | 多数站点单次搜索上限约 **1000 条** |

### 收到 429 怎么办

说明被目标站点封了。处理方式：
1. 两次抓取之间留间隔（视站点而定）
2. 用 `proxies` 换 IP

### Indeed 结果不相关怎么办

Indeed 会搜索**正文描述**，不只是标题。语法：
- `-` 排除词
- `""` 精确匹配
- `(a OR b)` 或

好用的例子：

```python
search_term='"engineering intern" software summer (java OR python OR c++) 2025 -tax -marketing'
```

### Google Jobs 不可用

文档明确写了 Google Jobs 当前不可用，选了会没结果。

---

## 六、返回字段（JobPost Schema）

```
id, site, job_url, job_url_direct, title, company, location, date_posted,
job_type, salary_source, interval, min_amount, max_amount, currency,
is_remote, job_level, job_function, listing_type, emails, description,
company_industry, company_url, company_logo, company_url_direct,
company_addresses, company_num_employees, company_revenue,
company_description, skills, experience_range, company_rating,
company_reviews_count, vacancy_count, work_from_home_type
```

**站点本身不提供的字段会是空值**——不要把空值当成"该岗位没有这项信息"，可能只是站点不提供。

对求职看板最有用的是：`title` `company` `location` `date_posted` `job_type` `min_amount` `max_amount` `currency` `job_url_direct` `description` `skills` `is_remote` `job_level` `company_industry`

---

## 七、本机实测记录（2026-10-09）

用 11 个关键词扫温哥华/BC 省/全加的植物科学实习，实测结论：

- `country_indeed="canada"` + `site_name=["linkedin"]` 工作正常，能返回结构化 DataFrame
- **搜索噪音很大**：`plant biology intern` 只返回 2 条且不相关；宽泛词会混进工程、兽医、矿业岗位
- **加拿大没有面向植物学本科生的对口实习**——搜到的都是农艺（agronomy）、林业（forestry）、生态（ecology）
- 真正对口的 UBC 校内 research assistant 和 AAFC 联邦农业岗**不在 LinkedIn 上**，需走学校/政府渠道

> 实操建议：先用 `job_type="internship"` 过滤，再用精确 `search_term`（带引号和排除词）缩小范围，最后按 `date_posted` 排序看最新的。