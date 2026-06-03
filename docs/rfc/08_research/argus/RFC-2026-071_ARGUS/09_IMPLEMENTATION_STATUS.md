---
file_id: ARGUS-09
title: "实现状态追踪 / Implementation Status"
rfc_id: RFC-2026-071
doc_status: "CURRENT_IMPLEMENTATION_NOTE"
approval_status: "NOT_SUBMITTED"
impl_status: "PHASE_4_5_IMPLEMENTED"
version: "1.0.0"
created: "2026-06-02"
last_updated: "2026-06-02"
drafter: "YQuant Codex Principal"
owner: "YQuant"
depends_on:
  - "ARGUS-02 (独立架构与技术栈)"
  - "ARGUS-03 (三层数据库Schema)"
  - "ARGUS-04 (信号引擎与评分系统)"
  - "ARGUS-05 (股票池管理与 Web 界面)"
  - "ARGUS-06 (高级分析能力)"
amendment_level: L2
---

# ARGUS-09: 实现状态追踪

> 本文件记录 2026-06-02 代码审查确认的 ARGUS 实际实现状态。原始 v2.0.1/v3.0 RFC 内容保留为设计基线；本文件用于标注当前实现与原始设计的差异。

## 1 当前实现总览

| 模块 | 状态 | 代码依据 | 说明 |
|:--|:--:|:--|:--|
| Phase 1/2 基础数据与核心信号 | IMPLEMENTED | `cli/daily_processor.py`, `core/credibility.py`, `core/signal_generator.py` | 从 `portfolio_position` / `portfolio_trade` 读取日度持仓和交易，生成产品信誉与个股信号。 |
| MongoDB 数据层 | IMPLEMENTED | `skills/data/data_interface/mongo_writer.py`, `config/argus_config.yaml` | 当前写入 MongoDB `tradingagents`，不是原始 RFC 中的 SQLite 13 表。 |
| 行业权重 Phase 4A | IMPLEMENTED | `core/industry_weight_calculator.py` | 聚合持仓到申万一级行业，输出 `weight_pct`, `weight_change_1d/30d/60d`。 |
| Darwin 检测 Phase 4B | IMPLEMENTED | `core/darwin_detector.py` | 使用行业指数 20 日回撤 + 产品信誉分位数 + `weight_change_30d` 检测分歧。 |
| Consensus Direction Phase 4C | IMPLEMENTED | `core/consensus_direction.py` | Prosperity Gauge + Conviction Radar，基于行业 30d/60d 权重变化。 |
| 四区 signal_pool | IMPLEMENTED | `core/pool_manager.py`, `cli/daily_processor.py` | 生成 `SCAN/WATCH/CANDIDATE/CONVICTION`，写入 `08_research_argus_signal_pool`。 |
| Portfolio 股票池同步 Phase 5 | IMPLEMENTED | `cli/daily_processor.py`, `skills/portfolio/stock_pool/ingestion.py` | `daily_processor` 调用 `ingest_signals_incremental()` 同步至 `05_portfolio_stock_pool` 并写审计。 |
| ARGUS signal 订阅器 Phase 5 | IMPLEMENTED | `argus_portfolio_subscriber.py` | 从 `08_research_argus_signal` 读取当日信号，转换为 Portfolio ingestion payload。 |
| FastAPI/Jinja2/HTMX Web UI | DEFERRED | 未发现对应 app/router/template 实现 | 原始 RFC 设计保留；当前实现为纯 CLI + MongoDB。 |
| SQLite 单库/三层 13 表 | DEFERRED | 当前 MongoWriter 写入 `08_research_*` 集合 | 原始 Schema 为设计基线，未作为当前运行数据层。 |
| 真正 Beta 分布贝叶斯后验 | PARTIAL | `core/bayesian_scoring.py` | 类名为 BayesianScorer，但当前 signal-pool score 是加权平均并 clamp 到 `[0,1]`；产品 profile 中 `alpha/beta` 仅用于产品信誉映射。 |
| 周五 Web 操作流 / 手动归档 UI | NOT_STARTED | 未发现 Web UI 实现 | 当前通过 CLI 和 Portfolio stock-pool service 边界处理。 |

## 2 当前实际目录结构

```text
skills/research/argus/
├── argus_portfolio_subscriber.py
├── cli/
│   ├── daily_processor.py
│   ├── refresh_all.py
│   └── backfill_phase4_bc.py
├── config/
│   ├── argus_config.yaml
│   ├── config.py
│   └── product_alias.yaml
├── core/
│   ├── bayesian_scoring.py
│   ├── consensus_direction.py
│   ├── consensus_engine.py
│   ├── credibility.py
│   ├── crowding.py
│   ├── darwin_detector.py
│   ├── industry_weight_calculator.py
│   ├── pool_manager.py
│   ├── rebalancing_detector.py
│   └── signal_generator.py
└── docs/
    └── README.md
```

## 3 当前实际数据流

```text
portfolio_position / portfolio_trade (MongoDB)
    ↓
skills.research.argus.cli.daily_processor.process_date()
    ↓
    ├─ credibility.py
    ├─ crowding.py
    ├─ signal_generator.py
    ├─ industry_weight_calculator.py
    ├─ darwin_detector.py
    ├─ consensus_direction.py
    └─ pool_manager.py
    ↓
MongoDB:
  - 08_research_argus_credential_score
  - 08_research_argus_signal
  - 08_research_argus_signal_pool
  - 08_research_argus_industry_weight
  - 08_research_argus_darwin_event
  - 08_research_argus_consensus_direction
    ↓
Portfolio:
  - 05_portfolio_stock_pool
  - 05_portfolio_stock_pool_audit
```

## 4 当前 MongoDB 集合与唯一键

| Collection | 唯一键 | 写入位置 | 用途 |
|:--|:--|:--|:--|
| `08_research_argus_credential_score` | `date, product_code` | `MongoWriter.write_argus_credential_scores()` | 产品当日信誉分。 |
| `08_research_argus_signal` | `date, signal_id` | `MongoWriter.write_argus_signals()` | 单产品单股票信号。 |
| `08_research_argus_signal_pool` | `date, wind_code` | `MongoWriter.write_argus_signal_pool()` | 四区股票池状态。 |
| `08_research_argus_industry_weight` | `date, product_code, sw1_code` | `MongoWriter.write_argus_industry_weights()` | 产品行业权重与 1d/30d/60d 变化。 |
| `08_research_argus_darwin_event` | `date, sw1_code` | `MongoWriter.write_argus_darwin_events()` | Darwin 事件。 |
| `08_research_argus_consensus_direction` | `date` | `MongoWriter.write_argus_consensus_direction()` | 景气方向与行业信念雷达。 |
| `05_portfolio_stock_pool` | Portfolio repository 管理 | `StockPoolIngestionService` | 组合股票池主表。 |
| `05_portfolio_stock_pool_audit` | Portfolio repository 管理 | `StockPoolIngestionService` | 入池、升降级、退出审计。 |

## 5 与原始设计的主要差异

| 设计项 | 原始 RFC v2.0.1/v3.0 | 当前实现 |
|:--|:--|:--|
| 应用形态 | 独立 FastAPI + Jinja2 + HTMX Web UI | 纯 CLI 编排 + MongoDB 写入 + JSON 日志输出 |
| 数据库 | SQLite `argus.db`，Raw/Processed/Decision 13 表 | MongoDB `tradingagents`，`08_research_argus_*` collections |
| 信号评分 | Beta 分布贝叶斯后验 + CI | `BayesianScorer` 当前为加权平均：rebalancing/product credibility/consensus/direction |
| Darwin 弱/强手阈值 | 固定 `credibility < 0.5` / `> 0.7` | 当日信誉分位数：20th / 80th percentile |
| Darwin 行业行为 | 通过窗口内权重 lookup 计算 | 使用 `IndustryWeightCalculator` 预计算的 `weight_change_30d` |
| 股票池 Web 管理 | `/pool` 页面、手动归档、HTMX 操作 | 写入 `08_research_argus_signal_pool`，再增量同步 Portfolio 股票池 |
| Empire 接口 | REST API 主通道 + JSON 备用 | 当前未实现 REST；Phase 5 通过 Portfolio ingestion service 边界同步 |

## 6 运行入口

```bash
python -m skills.research.argus.cli.daily_processor 2026-03-11
python -m skills.research.argus.cli.refresh_all
python -m skills.research.argus.cli.backfill_phase4_bc
```

