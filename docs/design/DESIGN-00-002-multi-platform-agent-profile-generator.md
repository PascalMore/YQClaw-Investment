# DESIGN-00-002: 多平台 Agent Profile 生成器

## 元数据

| 项 | 值 |
|---|---|
| 状态 | Draft |
| 作者 | YQuant-Codex-Principal |
| 创建日期 | 2026-06-23 |
| 最后更新 | 2026-06-23 |
| 来源 RFC | RFC-00-002 |
| 来源 SPEC | SPEC-00-002 |
| 目标模块 | scripts / infra |

## 1. 设计摘要

本设计实现一个以 Markdown profile 为源、以平台 adapter 为输出的生成器。第一版只落地 Hermes，但代码结构必须允许后续接入 Claude Code 和 Codex；`HEARTBEAT.md` 保留定时任务信息，Hermes 专用字段通过 adapter 映射补齐。

## 2. 现状分析

- 相关目录：
  - `scripts/`
  - `skills/`
  - `docs/rfc/00_project_overview/`
  - `docs/spec/`
  - `docs/design/`
- 相关文件：
  - `AGENTS.md`
  - `CLAUDE.md`
  - `HEARTBEAT.md`
  - `IDENTITY.md`
  - `MEMORY.md`
  - `SOUL.md`
  - `TOOLS.md`
  - `USER.md`
- 现有约束：
  - `HEARTBEAT.md` 需要保留 OpenClaw 可读的定期检查和调度汇总。
  - Hermes 的完整运行配置不应写入 `HEARTBEAT.md`。
  - 默认输出目录不能使用 `.agent-profiles/`。
- 兼容性风险：
  - 当前 Hermes 已有真实 profile，生成器不能默认覆盖。
  - 当前 5 个 cron 任务依赖 wrapper script 和 venv 路径，仅靠 `HEARTBEAT.md` 无法完整生成可运行 job。

## 3. 方案设计

### 3.1 模块/文件改动

| 文件 | 改动 | 原因 |
|---|---|---|
| `scripts/generate_agent_profile.py` | 新增 CLI 入口 | 统一生成多平台 profile |
| `scripts/agent_profile/__init__.py` | 新增包入口 | 组织生成器代码 |
| `scripts/agent_profile/models.py` | 新增 common model | 隔离平台无关数据结构 |
| `scripts/agent_profile/sources.py` | 新增 source reader | 读取 Markdown 和 skills |
| `scripts/agent_profile/heartbeat.py` | 新增 parser | 解析 `HEARTBEAT.md` 调度汇总 |
| `scripts/agent_profile/platforms/hermes.py` | 新增 Hermes adapter | 生成 Hermes 文件集 |
| `scripts/agent_profile/manifest.py` | 新增 manifest 工具 | 输出可追溯清单 |
| `tests/agent_profile/` | 新增测试 | 覆盖解析、生成、验证 |

第一版如需减少文件数量，也可以先放在单个 `scripts/generate_agent_profile.py`，但内部仍按上述职责拆分函数，避免后续 adapter 扩展困难。

### 3.2 数据流/控制流

```text
CLI args
  -> SourceRoot
  -> MarkdownSourceReader
  -> HeartbeatParser
  -> SkillsScanner
  -> AgentProfileModel
  -> HermesAdapter
  -> OutputWriter
  -> Validator
  -> GeneratedManifest
```

### 3.3 接口与数据结构

新增 dataclass：

```python
@dataclass
class ScheduledJob:
    name: str
    schedule: str
    enabled: bool
    schedule_type: str = "cron"
    source: str = "HEARTBEAT.md"

@dataclass
class SkillEntry:
    id: str
    name: str
    path: str
    description: str | None = None

@dataclass
class AgentProfileModel:
    profile: str
    platform: str
    source_root: Path
    soul: str | None
    user_memory: str | None
    project_memory: str | None
    scheduled_jobs: list[ScheduledJob]
    skills: list[SkillEntry]
```

Hermes adapter 需要额外映射：

```python
HERMES_JOB_SCRIPT_MAP = {
    "每日全球市场日报": "yquant-cron/daily-global-market-report.sh",
    "每日SmartMoney数据报告发送": "yquant-cron/daily-smartmoney-data-report.sh",
    "每日Argus数据批处理": "yquant-cron/daily-argus-batch-processing.sh",
    "每周酒店价格抓取": "yquant-cron/weekly-hotel-price-scraper.sh",
    "每日自动代码提交": "yquant-cron/daily-auto-code-commit.sh",
}
```

第一版生成 `cron/jobs.json` 时：

- `name` 来自 `HEARTBEAT.md`。
- `schedule` 来自 `HEARTBEAT.md`。
- `enabled` 来自 `状态 == active`。
- `script` 来自 Hermes adapter 映射。
- `no_agent` 固定为 `true`。
- `deliver` 固定为 `local`。

### 3.4 UI/原型设计

无。

## 4. 实现计划

- [ ] Step 1：创建 CLI 参数解析和 dry-run 框架。
- [ ] Step 2：实现 `HEARTBEAT.md` 调度汇总 parser。
- [ ] Step 3：实现 skills scanner，生成 `skills_manifest.json`。
- [ ] Step 4：实现 Hermes adapter 输出文件。
- [ ] Step 5：实现 manifest 哈希和输出校验。
- [ ] Step 6：增加单元测试和临时目录集成测试。
- [ ] Step 7：用当前 YQuant 5 个 cron 任务做回归验证。

## 5. 测试策略

- 单元测试：
  - `test_parse_heartbeat_schedule_table`
  - `test_reject_invalid_cron_expression`
  - `test_reject_duplicate_job_name`
  - `test_scan_skills_manifest`
  - `test_generated_manifest_hashes_outputs`
- 集成测试：
  - 在临时目录执行 `--platform hermes --profile yquant --output-dir <tmp> --validate`。
  - 验证输出文件存在且 JSON 可解析。
- 手工验证：
  - 对比当前 Hermes 5 个 active jobs 的名称和 schedule。
  - 检查 `HEARTBEAT.md` 未被修改。
- 回归范围：
  - OpenClaw heartbeat 文本仍可读。
  - Hermes profile 生成输出不默认覆盖真实 profile。

## 6. 风险、降级与回滚

| 风险 | 应对 | 降级/回滚 |
|---|---|---|
| 解析 Markdown 表格失败 | 固定表头并提供明确错误 | 停止生成，不写输出 |
| Hermes script 映射缺失 | adapter 校验所有 active job | 生成失败并列出缺失名称 |
| 输出覆盖真实 profile | 默认只写 `dist/`，`--apply` 才安装 | 使用 `--backup` 生成回滚目录 |
| skills 描述提取不准确 | 第一版只提取标题和首段摘要 | manifest 保留 path，允许人工检查 |

## 7. 交接给实现者

- 必须遵守：
  - 不修改 `HEARTBEAT.md`。
  - 不默认写入 `~/.hermes`。
  - 不默认创建 `.agent-profiles/`。
  - 不读取 `.env`。
  - 相同输入必须生成稳定输出。
- 可自行判断：
  - 第一版是单文件脚本还是小型 Python package。
  - 是否使用 Python 标准库手写 Markdown 表格 parser。
  - `profile.yaml` 和 `config.yaml` 的字段细节可先贴合当前 Hermes yquant profile。
- 遇到以下情况退回 Principal：
  - 需要新增 `HEARTBEAT.md` 字段。
  - 当前 Hermes `jobs.json` 字段与 adapter 设计不一致。
  - 需要引入第三方依赖。
  - 需要迁移或删除现有运行 profile。
