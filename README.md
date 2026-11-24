# 2027 岗位看板（实习 / 正式工作）

每日扫描 speedyapply 的两个 2027 校招仓库，汇总成一张可筛选的看板，**实习与正式工作分成两个 Tab**。

## 数据来源

| 仓库 | 内容 |
|---|---|
| [speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs) | 软件工程岗 |
| [speedyapply/2027-AI-College-Jobs](https://github.com/speedyapply/2027-AI-College-Jobs) | AI / ML 岗 |

每个仓库含4 个清单文件，共 8 个：

| 文件 | 对应看板分类 |
|---|---|
| `README.md` | 实习 · 美国 |
| `INTERN_INTL.md` | 实习 · 国际 |
| `NEW_GRAD_USA.md` | 正式工作 · 美国 |
| `NEW_GRAD_INTL.md` | 正式工作 · 国际 |

## 使用

**打开看板**：双击 `index.html`（纯静态，无需服务器）

**手动刷新数据**：

```bash
cd job-board
python3 fetch_jobs.py
```

**自动刷新**：由 GitHub Actions 在云端每天跑（详见下方「自动同步」）。本机 cron 每天 08:00 负责**取回**云端已生成的数据并汇报当日新增。

> 为什么要放云端：本地定时任务的调度器跑在 MiniMax Code 桌面 App 进程里，
> App 没运行（机器还在深度睡眠、或 App 被关掉）就**当天完全不触发**，且没有补跑。
> 实测 2026-10-10 至 11-24 的 46 天里断档 18 天。GitHub Actions 的调度器跑在
> GitHub 的云端，与本机状态完全无关。

## 看板功能

- 三个 Tab：实习 / 正式工作 / 全部
- 筛选：赛道（SWE / AI）、地区（美国 / 国际）、层级（FAANG+ / Quant / Other）
- 开关：仅看 7 天内新岗位、隐藏 PhD 岗位
- 搜索：公司 / 岗位 / 地点关键词
- 排序：点表头按公司、岗位、地点、薪资、发布时间排序
- 导出 CSV（按当前筛选条件）
- 岗位标签：FAANG+、Quant、Remote、Co-op、PhD、High School、多地点 `+N`
- 「● 新增」标记：当日首次出现在两个仓库里的岗位（靠 `data/history.json` 比对识别）
- 签证担保标记：公司名旁「H-1B✓（人工复核）/ H-1B~（自动匹配，带 FY26 认证数）/ 无H-1B记录 / 存疑」，并有签证筛选下拉框。数据来自劳工部 FY2026 Q1–Q3 H-1B 披露数据，由 `visa_build.py` 生成 `data/visa.json`，`fetch_jobs.py` 扫描时注入。注意：有记录 ≠ 接受 CPT/OPT 实习生，无记录 ≠ 一定不担保，最终以 JD 原文为准。

## 分类逻辑

岗位归入「实习」还是「正式工作」，先看岗位标题关键词，再回退到来源文件：

- 标题含 `intern` / `co-op` / `trainee` → **实习**
- 标题含 `new grad` / `full-time` / `entry level` / `engineer I` 等 → **正式工作**
- 标题都没命中 → 按来源文件归类（README/INTERN_INTL 算实习，NEW_GRAD_* 算正式）

当前数据里，正式工作 Tab 中混入的实习岗位为 0 条，分类准确。

## 数据过滤

上游清单里混着两类不是软件岗的东西，已在管道里精确剔除：

| 过滤项 | 规则 | 影响 |
|---|---|---|
| 数据采集零工 | 标题含 `recording videos`（如 Mindrift「Earn $70 Recording Videos at Home for AI」——付钱让普通人在家录视频给模型做训练数据） | 剔除 10 条。不误伤 `Robotics Data Collection` 这类真实实习标题 |
| 创业渠道非技术岗 | 标题必须命中技术岗白名单才保留 | 创业渠道 89 → 81 条，剔掉 VP/Analytics、Creative Director、Actuary、Events Manager 等 8 条 |

创业渠道的白名单**只作用于创业渠道**，不碰 2027 校招主数据——主数据里有 NVIDIA PhD Economics、Micron 采购实习这类真实但非 CS 的岗位，按关键词砍会误伤。

白名单特意包含 `Member of Technical Staff` / `MTS`（YC 体系里对创始工程师的标准称谓），并刻意不收 `development` / `analytics` / `platform` 等泛词，避免 `Director, International Development` / `VP, Analytics` 这类漏网。

## 文件说明

```
job-board/
├── index.html        # 看板（由脚本生成，每次扫描覆盖；已部署到 GitHub Pages）
├── template.html     # 看板模板，改样式改这里
├── fetch_jobs.py     # 扫描脚本（零第三方依赖，只用 Python 标准库）
├── scan_startup.py   # 创业渠道抓取（Wellfound / YC Work at a Startup，需 Playwright + 浏览器）
├── visa_build.py     # 签证标记生成器（产出 data/visa.json）
├── .github/workflows/sync.yml  # 每日云端同步（GitHub Actions）
└── data/             # 本地数据目录
    ├── jobs.json     # 当日岗位快照（不入库，每次重新生成）
    ├── history.json  # 历史累计，用于识别新增岗位  ← 入库
    ├── visa.json     # 公司 -> H-1B 担保记录标记      ← 入库
    ├── h1b_employers_fy26q3.json  # 劳工部 FY26 H-1B 雇主统计（visa_build 的原料，不入库）
    └── raw/          # 8 个清单文件的 markdown 留档（不入库）
```

> `data/` 下只有 `history.json` 和 `visa.json` 入库，其余排除。`history.json` 必须入库，
> 否则云端每次都把全部岗位当成「今日新增」，`first_seen` 也会全部塌成当天；
> `visa.json` 必须入库，因为 `visa_build.py` 依赖本机不存在的 `visa_curated.json`，
> 无法在云端重新生成。

## 自动同步（GitHub Actions）

`.github/workflows/sync.yml` 每天 **07:30（Asia/Shanghai）** 在 GitHub 云端跑一遍完整管道：

1. 检出代码（带上 `data/history.json` 和 `data/visa.json`）
2. 装 Python 依赖 + Playwright 自带 Chromium
3. 跑 `fetch_jobs.py`：下载 8 个清单 → 解析 → 合并创业渠道 → 注入签证标记 → 渲染 `index.html`
4. 提交并推送 `index.html` + 状态文件 → 推送触发 GitHub Pages 自动重建

也支持在 Actions 页面手动触发（workflow_dispatch）随时验证。

几个设计要点：

- **时区**：runner 默认 UTC，工作流里设了 `TZ: Asia/Shanghai`，`scan_date` 才是北京时间。
- **浏览器**：本地优先用系统 Chrome；云端没有系统 Chrome，`scan_startup.py` 会自动回退到 Playwright 自带 Chromium。
- **单写者**：只有 Actions 会推送。本机 cron 只负责取回并汇报，避免两边同时改 `history.json` 打架。
- **幂等**：同一天重跑不会让「今日新增」塌成个位数——该字段按 `first_seen` 统计，不是按本次扫描的命中数。

> GitHub Actions 的 schedule 在仓库 60 天无活动时会自动停用。本仓库每天都有提交，不会触发。
> 另外 Actions 的定时任务在高峰期可能被推迟几分钟，所以本地 cron 定在 08:00，留了 30 分钟余量。

## 在线看板

本仓库已开启 GitHub Pages：

**https://erongcao.github.io/job-board/**

现在由 Actions 自动推送更新，不需要手动提交。

改看板样式请改 `template.html`，然后重跑 `python3 fetch_jobs.py` 重新生成 `index.html`。

## 说明

本看板只是对上游仓库 markdown 清单的解析、汇总与筛选视图，岗位是否仍在招、投递要求以公司官方页面为准。