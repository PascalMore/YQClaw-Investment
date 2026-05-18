# Argus - 机构智慧资金行为追踪系统

基于 YQClaw Investment 的 Argus 子项目，实现机构资金行为的日度追踪与分析。

## 目录结构

```
skills/research/argus/
├── config/                    # 配置文件
│   ├── argus_config.yaml      # 主配置
│   └── product_alias.yaml     # 产品化名映射
├── core/                      # 核心业务逻辑
│   ├── credibility.py        # 贝叶斯信誉评分
│   ├── signal_generator.py   # 信号生成
│   ├── pool_manager.py       # 四区股票池
│   ├── rebalancing_detector.py # 调仓检测
│   ├── darwin_detector.py    # 达尔文时刻
│   └── consensus_engine.py    # 多产品共识
├── cli/                       # 命令行工具
│   └── daily_processor.py   # 日度处理
├── tests/                     # 单元测试
└── docs/                      # 文档
```

## 快速开始

### 日度处理

```bash
python -m skills.research.argus.cli.daily_processor 2026-03-11
```

### 运行测试

```bash
python -m pytest skills/research/argus/tests/test_argus_core.py -v
```

## 核心模块

### CredibilityScorer
贝叶斯信誉评分引擎，计算产品行为可信度。

### SignalGenerator
多时间框架信号融合，输出标准化信号。

### PoolManager
四区股票池管理：SCAN / WATCH / CANDIDATE / CONVICTION。

### RebalancingDetector
调仓事件检测，识别持仓比例突变。

### DarwinDetector
达尔文时刻检测，识别拥挤度峰值。

### ConsensusEngine
多产品共识引擎，跨产品汇聚信号。

## 输出

- 日志：`logs/research/argus/argus_{YYYYMMDD}.log`
- 信号：`logs/research/argus/argus_signal_{YYYYMMDD}.json`

## 依赖

- skills/data/ - 数据接口
- skills/infra/ - 基础设施