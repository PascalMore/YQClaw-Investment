# MEMORY.md - YQuant 长期记忆

> 本文件存储 YQuant 的长期记忆，包括重要决策、项目背景、技术架构等关键信息。

## 项目概述

- **项目名称**：YQClaw-Investment 智能量化投资系统
- **目录**：workspace-yquant
- **目标**：对标顶级对冲基金的量化投研体系

## 身份定义

- **角色**：YQuant（量化金融工程师）
- **用户**：Pascal Mao
- **沟通语言**：中文（专业术语可直接使用）

## 技术栈

- **核心语言**：Python > C++/Rust
- **量化框架**：VeighNa / NautilusTrader / Hummingbot / QUANTAXIS
- **数据源**：Tushare Pro / AKshare / Binance API / Finnhub 等
- **智能体框架**：OpenClaw 多智能体框架

## 子智能体团队

- @YQuant/data-collector
- @YQuant/researcher
- @YQuant/strategist
- @YQuant/risk-manager
- @YQuant/portfolio-manager
- @YQuant/reporter
- @YQuant/common
- @YQuant/data-engineer
- @YQuant/devops

## 目录结构

```
workspace-yquant/
├── soul.md / identity.md / agents.md / claude.md
├── HEARTBEAT.md / USER.md / TOOLS.md / MEMORY.md
├── memory/                    # 每日记忆文件
├── skills/
│   ├── common/              # 通用工具
│   ├── data/                # 数据采集
│   ├── research/            # 投研分析
│   ├── strategies/          # 策略回测
│   ├── risk/                # 风险管控
│   ├── portfolio/           # 组合管理
│   ├── reports/             # 复盘报告
│   ├── infra/               # 基础设施
│   └── knowledge/           # 知识库
└── auto_push.sh
```

---

_Last updated: 2026-04-24_
