# RFC-00-002: 多平台 Agent Profile 生成器

## 元数据（Metadata）

| 项 | 值 |
|---|---|
| 状态 | Draft |
| 作者 | YQuant-Codex-Principal |
| 创建日期 | 2026-06-23 |
| 最后更新 | 2026-06-23 |
| 版本号 | V1.0 |
| 所属模块 | 00_project_overview / infra |
| 依赖RFC | RFC-00-001-yquant-investment-global-architecture |
| 替代RFC | 无 |
| 适配AI工具 | OpenClaw / Hermes / Claude Code / Codex |
| 标签 | #架构 #AgentProfile #Hermes #OpenClaw #迁移 #配置生成 |

### 版本历史（Changelog）

| 版本号 | 日期 | 更新内容 | 负责人 |
|---|---|---|---|
| V1.0 | 2026-06-23 | 初始创建，定义多平台 profile 生成器第一版边界 | YQuant-Codex-Principal |

## 1. 执行摘要（Executive Summary）

YQuant 已完成从 OpenClaw 到 Hermes 的主要运行迁移，但项目内仍保留大量面向 OpenClaw 的 Markdown profile、heartbeat、memory 和工具说明。本文档定义一个多平台 Agent Profile 生成器：以项目内 Markdown 文件作为长期权威语义来源，第一版生成 Hermes profile，后续扩展到 Claude Code、Codex 等平台。

## 2. 背景与动机（Background & Motivation）

- OpenClaw 迁移 Hermes 的过程中，profile 映射、cron 迁移、venv 路径、systemd 服务边界等信息主要依赖人工排查。
- YQuant 后续需要在其他 Hermes 机器上快速初始化，而不是重新逐项映射 OpenClaw 配置。
- 项目中的 `AGENTS.md`、`CLAUDE.md`、`HEARTBEAT.md`、`IDENTITY.md`、`MEMORY.md`、`SOUL.md`、`TOOLS.md`、`USER.md` 仍有价值，应作为跨平台 agent 语义的长期积累入口。
- 定时任务信息应继续保留在 `HEARTBEAT.md`，但不应在其中写入 Hermes `jobs.json` 的完整实现细节。

## 3. 目标与非目标（Goals & Non-Goals）

### 3.1 必须目标（Must-Have）

- [ ] 在 `scripts/` 下提供一个可重复运行的 profile 生成器。
- [ ] 第一版支持 `--platform hermes`，生成 Hermes profile 所需文件。
- [ ] 支持 `--output-dir` 指定输出目录，默认输出到 `dist/agent-profiles/{platform}/{profile}`。
- [ ] 支持 `--apply` 将生成结果安装到目标平台目录，例如 `~/.hermes/profiles/yquant`。
- [ ] 从 `HEARTBEAT.md` 解析 cron 任务名称、cron 表达式、状态等关键信息。
- [ ] 生成 `skills_manifest.json`，描述 YQuant 可供 agent 使用的 skills。
- [ ] 生成 manifest，记录输入文件、输出文件、哈希、生成时间和生成器版本。

### 3.2 非目标（Out of Scope）

- [ ] 第一版不生成 Claude Code 或 Codex 的最终 profile，只保留平台适配接口。
- [ ] 第一版不改变 Hermes gateway、systemd service、业务脚本的运行方式。
- [ ] 第一版不把 Hermes 专用 `jobs.json` 或脚本路径写回 `HEARTBEAT.md`。
- [ ] 第一版不新增 `.agent-profiles/` 作为仓库内默认输出目录。
- [ ] 第一版不管理密钥、邮箱密码、API token 或 `.env` 内容。

## 4. 整体设计（Overall Design）

### 4.1 核心设计哲学

以项目 Markdown 文件保存长期语义，以平台 adapter 生成短期运行配置；源文件保持人类可读，平台配置保持机器可执行。

### 4.2 架构总览

```text
AGENTS/CLAUDE/HEARTBEAT/IDENTITY/MEMORY/SOUL/TOOLS/USER
        |
        v
scripts/generate_agent_profile.py
        |
        +--> common model: identity, soul, memory, tools, heartbeat, skills, cron
        |
        +--> hermes adapter
        |       +--> profile.yaml
        |       +--> config.yaml
        |       +--> SOUL.md
        |       +--> memories/*.md
        |       +--> skills/skills_manifest.json
        |       +--> cron/jobs.json
        |       +--> migration/generated-manifest.json
        |
        +--> future adapters: claude-code, codex
```

### 4.3 模块分工

- Source reader：读取项目根目录 Markdown 文件和 skills 目录元信息。
- Heartbeat parser：解析 `HEARTBEAT.md` 中的 `## 定期检查` 与 `## 调度汇总`。
- Common model：将不同来源规整为平台无关的数据模型。
- Platform adapter：将 common model 渲染成目标平台 profile。
- Validator：校验输出目录、必需文件、cron 表达式、任务数量、重复任务名。
- Installer：在显式 `--apply` 下写入目标平台目录，并可做备份。

## 5. 详细设计（Detailed Design）

### 5.1 业务流程（Flow）

- 触发条件：开发者执行 `scripts/generate_agent_profile.py --platform hermes --profile yquant`。
- 核心处理：
  - 读取项目根目录 profile Markdown。
  - 解析 `HEARTBEAT.md` 的定期检查和调度汇总。
  - 扫描 `skills/` 目录生成 skills manifest。
  - 使用 Hermes adapter 生成输出文件。
  - 执行验证并生成 manifest。
- 正常分支：生成到 `dist/agent-profiles/hermes/yquant`；若提供 `--apply`，再安装到 `~/.hermes/profiles/yquant`。
- 异常分支：缺少关键源文件、cron 表达式非法、任务名重复、输出目录已有内容且未指定 `--force` 时失败并给出明确错误。

### 5.2 数据模型（Data Model）

| 字段 | 类型 | 说明 | 约束 |
|---|---|---|---|
| profile | string | profile 名称，例如 `yquant` | 非空 |
| platform | string | 目标平台，例如 `hermes` | 第一版仅 `hermes` |
| sources | object | 输入文件路径与哈希 | 生成 manifest 必填 |
| scheduled_jobs | list | 从 `HEARTBEAT.md` 抽取的任务 | 名称唯一 |
| skills | list | 可用 skills 摘要 | 路径唯一 |
| output_files | list | 输出文件路径与哈希 | 生成 manifest 必填 |

### 5.3 接口契约（API Contract）

命令行接口：

```bash
python scripts/generate_agent_profile.py \
  --platform hermes \
  --profile yquant \
  --source-root /home/pascal/workspace/yquant-investment \
  --output-dir dist/agent-profiles/hermes/yquant \
  --validate
```

可选参数：

- `--apply`：安装到目标平台默认目录。
- `--force`：覆盖输出目录已有文件。
- `--backup`：安装前备份目标平台原 profile。
- `--dry-run`：只打印将生成的文件和验证结果。
- `--target-root`：覆盖平台安装根目录，例如 Hermes 的 `~/.hermes/profiles`。

### 5.4 AI模型设计

无。该生成器不依赖 LLM 推断；所有生成结果必须来自可解析源文件、显式映射表或平台 adapter 固定规则。

## 6. AI实装规范（AI Implementation Rules）

### 6.1 必须执行

- 保持生成器幂等：相同输入产生相同输出。
- 对 Markdown 结构使用明确锚点、标题或表格解析，不依赖模糊自然语言推断。
- `HEARTBEAT.md` 只作为 cron 关键信息来源，不写入 Hermes 专用脚本细节。
- 生成结果必须包含 `migration/generated-manifest.json`。
- 所有路径默认使用项目相对路径；安装路径必须由参数或平台 adapter 明确给出。

### 6.2 先询问再执行

- 修改 `HEARTBEAT.md` 标准语法。
- 修改 Hermes 现有 active profile。
- 新增或删除真实运行任务。
- 改动 systemd、crontab、gateway 服务状态。

### 6.3 绝对禁止

- 从 `.env`、shell history 或日志中读取并写入密钥。
- 在未指定 `--apply` 时写入 `~/.hermes`。
- 默认新增 `.agent-profiles/` 目录。
- 将平台专用 `jobs.json` 全量内容反写到 `HEARTBEAT.md`。

## 7. 风险与应对（Risks & Mitigations）

| 风险 | 概率 | 影响 | 应对方案 | 降级策略 |
|---|---|---|---|---|
| Markdown 解析脆弱 | 中 | 中 | 固定 `## 调度汇总` 表格字段并做验证 | 解析失败时停止生成 |
| Hermes cron 缺少脚本路径 | 中 | 高 | 从 adapter 显式映射或现有 Hermes 配置补齐 | 生成 disabled job 并提示补齐 |
| 多平台语义不一致 | 中 | 中 | common model 只保存跨平台字段 | 平台差异放 adapter |
| 覆盖现有 profile | 低 | 高 | `--apply` 需显式指定，默认备份 | 回滚备份目录 |

## 8. 备选方案（Alternatives Considered）

- 直接维护 Hermes `jobs.json`：执行简单，但无法沉淀 OpenClaw/Hermes/未来平台之间的语义映射。
- 在 `HEARTBEAT.md` 写入完整 Hermes 配置：生成方便，但污染 OpenClaw heartbeat 语义。
- 新增仓库内 `.agent-profiles/`：便于版本化输出，但容易把生成物当源码维护，当前不采用。

## 9. 验收标准（Acceptance Criteria）

### 9.1 功能验收

- 生成器能从当前 `HEARTBEAT.md` 解析出 5 个 active cron 任务。
- Hermes 输出包含 `profile.yaml`、`config.yaml`、`SOUL.md`、`memories/`、`skills/skills_manifest.json`、`cron/jobs.json`、`migration/generated-manifest.json`。
- `--dry-run` 不写文件。
- `--output-dir` 能写入任意指定目录。
- `--apply` 能在备份后安装到 Hermes profile 目录。

### 9.2 非功能验收

- 重复执行不会产生无意义 diff。
- 缺少源文件时错误信息明确。
- 不读取或输出敏感凭证。
- 生成 manifest 能追溯每个输出文件的来源。

## 10. 落地计划（Implementation Plan）

### 10.1 阶段划分

- Phase 1：实现 Hermes adapter、Heartbeat parser、skills manifest、manifest。
- Phase 2：补充 Claude Code adapter 设计。
- Phase 3：补充 Codex adapter 设计。

### 10.2 任务清单

- [ ] 定义 common model。
- [ ] 实现 Markdown source reader。
- [ ] 实现 `HEARTBEAT.md` 调度表解析。
- [ ] 实现 Hermes adapter。
- [ ] 实现 skills manifest 扫描。
- [ ] 实现 manifest 与验证。
- [ ] 增加单元测试和 dry-run 示例。

## 11. 开放问题（Open Questions）

- Hermes cron 的脚本路径第一版是否从现有 `~/.hermes` 读取，还是维护 repo 内显式映射文件。
- `HEARTBEAT.md` 的 `## 调度汇总` 是否需要增加 `id` 列，以减少名称映射歧义。
- skills manifest 是否只扫描 `SKILL.md`，还是同时纳入 docs/RFC 作为参考资源。

## 12. 参考资料（References）

- `HEARTBEAT.md`
- `AGENTS.md`
- `SOUL.md`
- `MEMORY.md`
- `USER.md`
- `docs/rfc/00_project_overview/RFC-00-001-yquant-investment-global-architecture.md`
