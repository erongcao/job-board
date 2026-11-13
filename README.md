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

**自动刷新**：已配置每天早上 8:00（Asia/Shanghai）自动扫描，任务名「2027 岗位看板每日扫描」，扫描完会主动汇报当日新增岗位。

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

## 文件说明

```
job-board/
├── index.html        # 看板（由脚本生成，每次扫描覆盖；已部署到 GitHub Pages）
├── template.html     # 看板模板，改样式改这里
├── fetch_jobs.py     # 扫描脚本（零第三方依赖，只用 Python 标准库）
├── scan_startup.py   # 创业渠道抓取（Wellfound / YC Work at a Startup，需 Playwright + Chrome）
├── visa_build.py     # 签证标记生成器（产出 data/visa.json）
└── data/             # 本地数据目录，不入库（.gitignore），由脚本重新生成
    ├── jobs.json     # 当日岗位快照
    ├── history.json  # 历史累计，用于识别新增岗位
    ├── visa.json     # 公司 -> H-1B 担保记录标记
    ├── h1b_employers_fy26q3.json  # 劳工部 FY26 H-1B 雇主统计（visa_build 的原料）
    └── raw/          # 8 个清单文件的 markdown 留档
```

> `data/` 目录体积大且每天变动，已在 `.gitignore` 中排除；看板页面 `index.html` 已把数据内嵌，无需 `data/` 也能正常打开。

## 在线看板

本仓库已开启 GitHub Pages：

**https://erongcao.github.io/job-board/**

每次本地跑完 `python3 fetch_jobs.py` 后，把新的 `index.html` 提交推送，页面即同步更新。

改看板样式请改 `template.html`，然后重跑 `python3 fetch_jobs.py` 重新生成 `index.html`。

## 说明

本看板只是对上游仓库 markdown 清单的解析、汇总与筛选视图，岗位是否仍在招、投递要求以公司官方页面为准。