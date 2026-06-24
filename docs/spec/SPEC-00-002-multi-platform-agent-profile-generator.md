# SPEC-00-002: 多平台 Agent Profile 生成器

## 元数据

| 项 | 值 |
|---|---|
| 状态 | Draft |
| 作者 | YQuant-Codex-Principal |
| 创建日期 | 2026-06-23 |
| 最后更新 | 2026-06-23 |
| 来源 RFC | RFC-00-002 |
| 目标模块 | scripts / infra |
| 适配 Agent | YQuant-Developer-Engineer, YQuant-Test-Engineer |

## 1. 需求摘要

实现一个多平台 Agent Profile 生成器，第一版支持从 YQuant 项目 Markdown 和 skills 目录生成 Hermes profile。生成器必须保留 OpenClaw 语义来源，不把 Hermes 运行细节写回 `HEARTBEAT.md`，并支持自定义输出目录、dry-run、验证和显式安装。

## 2. 范围

### 2.1 In Scope

- [ ] 新增 `scripts/generate_agent_profile.py`。
- [ ] 支持 `--platform hermes`。
- [ ] 支持 `--profile`、`--source-root`、`--output-dir`、`--target-root`、`--dry-run`、`--apply`、`--force`、`--backup`、`--validate`。
- [ ] 读取 `AGENTS.md`、`CLAUDE.md`、`HEARTBEAT.md`、`IDENTITY.md`、`MEMORY.md`、`SOUL.md`、`TOOLS.md`、`USER.md` 中存在的文件。
- [ ] 从 `HEARTBEAT.md` 的 `## 调度汇总` 解析 active cron 任务。
- [ ] 从 `skills/**/SKILL.md` 生成 `skills/skills_manifest.json`。
- [ ] 生成 Hermes profile 文件集。
- [ ] 生成 `migration/generated-manifest.json`。

### 2.2 Out of Scope

- [ ] 不实现 Claude Code 和 Codex 输出，只保留 adapter 注册结构。
- [ ] 不新增 `.agent-profiles/` 默认目录。
- [ ] 不管理 `.env`、密钥或外部凭证。
- [ ] 不启动、停止或重启 Hermes gateway。
- [ ] 不修改 systemd、crontab 或业务脚本。

## 3. 功能规格

| 编号 | 行为 | 输入 | 输出 | 错误/边界 |
|---|---|---|---|---|
| F-001 | 解析源 Markdown | `--source-root` | common model | 缺少非必需文件只记录 warning |
| F-002 | 解析 heartbeat cron | `HEARTBEAT.md` | scheduled jobs | 表格缺列、cron 非法、任务名重复时报错 |
| F-003 | 生成 Hermes profile | common model | profile 文件集 | 缺少必需字段时报错 |
| F-004 | 生成 skills manifest | `skills/**/SKILL.md` | `skills/skills_manifest.json` | skill 名重复时报错 |
| F-005 | dry-run | `--dry-run` | 计划输出到 stdout | 不得写入文件 |
| F-006 | 输出目录写入 | `--output-dir` | 文件树 | 目录存在且未 `--force` 时失败 |
| F-007 | 安装到平台 | `--apply --target-root` | Hermes profile | 未 `--backup` 时覆盖前必须二次显式参数确认，第一版用 `--force` 表示确认 |
| F-008 | 生成 manifest | 输出文件集 | `migration/generated-manifest.json` | 哈希失败时报错 |

## 4. 数据与接口契约

### 4.1 CLI

```bash
python scripts/generate_agent_profile.py \
  --platform hermes \
  --profile yquant \
  --source-root . \
  --output-dir dist/agent-profiles/hermes/yquant \
  --validate
```

### 4.2 `HEARTBEAT.md` 解析契约

生成器从 `## 调度汇总` 表格读取以下列：

| 列名 | 说明 |
|---|---|
| 任务 | cron job 展示名 |
| 调度 | 调度类型，第一版支持 `cron` |
| 时间 | 5 字段 cron 表达式，允许 Markdown 反引号 |
| 状态 | `active` 生成 enabled job，其他状态默认不生成 active job |

`## 定期检查` 作为人类可读检查项保留；第一版可用于交叉验证任务名称，但不作为唯一数据源。

### 4.3 Hermes 输出契约

```text
{output-dir}/
  profile.yaml
  config.yaml
  SOUL.md
  memories/
    USER.md
    MEMORY.md
  skills/
    skills_manifest.json
  cron/
    jobs.json
  migration/
    generated-manifest.json
```

### 4.4 `skills_manifest.json`

```json
{
  "schema_version": 1,
  "profile": "yquant",
  "generated_at": "2026-06-23T00:00:00+08:00",
  "skills": [
    {
      "id": "data-pipeline",
      "name": "data-pipeline",
      "path": "skills/data/data-pipeline/SKILL.md",
      "description": "..."
    }
  ]
}
```

### 4.5 `generated-manifest.json`

```json
{
  "schema_version": 1,
  "generator": "scripts/generate_agent_profile.py",
  "platform": "hermes",
  "profile": "yquant",
  "source_root": ".",
  "inputs": [],
  "outputs": []
}
```

## 5. 验收标准

| 编号 | 验收项 | 验证方式 |
|---|---|---|
| A-001 | 能解析当前 `HEARTBEAT.md` 中 5 个 active cron 任务 | 单元测试 |
| A-002 | 生成目录包含 Hermes 第一版全部文件 | 集成测试 |
| A-003 | `--dry-run` 不产生文件 | 集成测试 |
| A-004 | `--output-dir` 可指定到临时目录 | 集成测试 |
| A-005 | `skills_manifest.json` 覆盖所有 `skills/**/SKILL.md` | 单元测试 |
| A-006 | 缺少 Hermes cron 脚本映射时报错或生成 disabled job，并在 manifest 标注 | 单元测试 |
| A-007 | 不读取 `.env`，不输出密钥 | 代码审查 + 测试 |

## 6. 测试要求

- 单元测试：heartbeat 表格解析、cron 表达式校验、skills 扫描、manifest 哈希。
- 集成测试：在临时目录生成 Hermes profile。
- 回归测试：当前 5 个 YQuant cron 任务名称和调度不丢失。
- 不可自动化验证项：安装到真实 `~/.hermes` 后是否符合当前 Hermes gateway 版本的运行习惯。

## 7. 实现约束

- 禁止事项：默认写入 `~/.hermes`、默认新增 `.agent-profiles/`、读取 `.env`、修改 `HEARTBEAT.md`。
- 依赖限制：优先使用 Python 标准库；如引入 YAML 依赖需先确认。
- 性能/安全/风控约束：扫描范围限制在 `--source-root` 内；输出前做路径归一化，禁止路径穿越。

## 8. 开放问题

- [ ] Hermes cron job 的 script 路径映射放在独立 repo 配置文件，还是从已安装 Hermes profile 反向读取。
- [ ] 是否在 `HEARTBEAT.md` 的调度汇总增加 `id` 列。
- [ ] `CLAUDE.md` 与 `AGENTS.md` 在 Hermes profile 中的映射优先级。
