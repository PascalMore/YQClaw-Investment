# SPEC-10-005: Hermes Agent 自动升级脚本

## 元数据

| 项 | 值 |
|---|---|
| 状态 | Accepted |
| 作者 | YQuant-Codex-Principal |
| 创建日期 | 2026-06-27 |
| 最后更新 | 2026-06-27 |
| 来源 RFC | RFC-10-005-hermes-auto-upgrade |
| 目标模块 | infra / Hermes 运维自动化 |
| 适配 Agent | YQuant-Developer-Engineer, YQuant-Test-Engineer, YQuant-Reviewer-Principal |
| 关联 RFC | RFC-10-003-infra-architecture, RFC-10-004-yquant-ai-coding-pipeline-skill-sync |
| 关联 Design | DESIGN-10-005-hermes-auto-upgrade（待创建） |

## 1. 需求摘要

本 SPEC 将 RFC-10-005 落为可执行脚本契约。实现者必须在 `scripts/upgrade/` 下新增 Hermes Agent 自动升级脚本，完成 upstream 官方仓库到本地 fork checkout 的安全升级、安装验证、gateway 安全重启与 origin fork 推送。脚本必须优先保护本地 commit 与未提交改动：升级前 zip 备份与 git stash，升级时 fast-forward 优先，diverged 时采用“保护本地 commit 后 merge upstream”的 A+ 策略，冲突时中止，不自动猜测解决。

核心交付物：

1. `scripts/upgrade/upgrade_hermes_agent.py` 可执行；
2. `--dry-run`、`--version`、`--no-restart`、`--no-push`、`--rollback` 参数可用；
3. 升级前 manifest + zip + stash 保护当前状态；
4. 本地验证通过后才 push origin；
5. gateway restart 使用 detached 安全方案或明确跳过；
6. 测试覆盖 dry-run、参数解析、ref 解析、错误路径与回滚计划。

## 2. 范围

### 2.1 In Scope

- [ ] 新增 `scripts/upgrade/upgrade_hermes_agent.py`。
- [ ] 可选新增 `scripts/upgrade/README.md` 或最小使用说明。
- [ ] 支持 `/home/pascal/workspace/hermes-agent` git 源码安装场景。
- [ ] 支持 `origin=git@github.com:PascalMore/hermes-agent.git` 与 `upstream=https://github.com/NousResearch/hermes-agent.git`。
- [ ] 支持指定 `--version` 为 tag、branch、remote ref、commit SHA。
- [ ] 支持 dry-run、备份、stash、merge、install、verify、detached restart、push、rollback。
- [ ] 产出 Design 文档并由后续 Implement/Verify/Review 执行。

### 2.2 Out of Scope

- [ ] 不修改 Hermes Agent upstream 源码业务逻辑。
- [ ] 不修改 Hermes profiles 的 `config.yaml`、`.env`、`auth.json`、MCP、model/fallback 配置。
- [ ] 不自动解决 merge conflict。
- [ ] 不实现 CI/CD、定时自动升级、Docker/Nix/Homebrew 升级路径。
- [ ] 不处理非 git 源码安装的 Hermes 生产升级；检测到非 git 时应失败并提示。
- [ ] 不清理或改写 YQuant 现有无关工作区变更。

## 3. 功能规格

| 编号 | 行为 | 输入 | 输出 | 错误/边界 |
|---|---|---|---|---|
| F-001 | CLI 参数解析 | argv | `UpgradeConfig` | 参数冲突时 exit 2 |
| F-002 | repo 前置校验 | `--repo` | repo/remotes/branch/install_method 状态 | 非 git repo、缺 remote、非 main 默认失败 |
| F-003 | dry-run 计划 | `--dry-run` | 完整步骤清单 | 不得执行 fetch/stash/zip/merge/install/restart/push 修改 |
| F-004 | zip 备份 | repo path | `/tmp/hermes-backup-{timestamp}.zip` | 备份失败必须停止 |
| F-005 | manifest 写入 | upgrade state | `/tmp/hermes-upgrade-{timestamp}.json` | manifest 写入失败必须停止 |
| F-006 | dirty tree stash | dirty/untracked files | stash ref 或 null | stash 失败必须停止；dry-run 只打印 |
| F-007 | fetch remotes | origin/upstream | 更新 remote refs/tags | 网络/auth 失败必须停止 |
| F-008 | target ref 解析 | `--version` / default | target SHA | 无效 ref 必须停止 |
| F-009 | 本地 commit 保护 | `HEAD`, `upstream target`, `origin/main` | local-only commit 报告 | origin 不可 push 或本地 commit 未保护时不得继续自动 merge |
| F-010 | 升级 merge | target SHA | updated HEAD | ff 优先；diverged 用 merge；冲突 abort |
| F-011 | 安装依赖/包 | updated repo | install exit code 0 | 失败停止，不 push |
| F-012 | 版本验证 | hermes executable | `hermes --version` 输出 | exit code 非 0 停止 |
| F-013 | gateway health | gateway status/health | healthy/unhealthy | unhealthy 停止或标记需人工重启，不 push 策略见 F-015 |
| F-014 | detached restart | restart enabled | restart log + post health | 不得同步自杀；失败停止并输出手动命令 |
| F-015 | push origin | verify success + push enabled | origin/main updated | push 失败不回滚本地，但 exit 非 0 并输出修复命令 |
| F-016 | rollback | `--rollback manifest` | repo 恢复到 pre_head/zip/stash | rollback 失败必须输出人工恢复命令 |
| F-017 | 审计日志 | all steps | stdout + optional log file | 日志不得泄漏 secrets |

## 4. 数据与接口契约

### 4.1 文件与目录契约

| 名称 | 路径 | 状态要求 | 说明 |
|---|---|---|---|
| upgrade_dir | `scripts/upgrade/` | 必须存在 | 脚本目录 |
| upgrade_script | `scripts/upgrade/upgrade_hermes_agent.py` | 必须新增且可执行 | 主入口 |
| hermes_repo_default | `/home/pascal/workspace/hermes-agent` | 必须是 git repo | 默认目标 repo |
| backup_zip | `/tmp/hermes-backup-{YYYYmmdd-HHMMSS}.zip` | 升级前创建 | 工作树文件级备份 |
| manifest | `/tmp/hermes-upgrade-{YYYYmmdd-HHMMSS}.json` | 升级前创建并随步骤更新 | rollback 输入 |
| restart_log | `/tmp/hermes-upgrade-restart-{YYYYmmdd-HHMMSS}.log` | restart enabled 时创建 | detached restart 日志 |

### 4.2 CLI 参数契约

| 参数 | 类型 | 默认 | 行为 |
|---|---|---|---|
| `--repo PATH` | path | `/home/pascal/workspace/hermes-agent` | 指定 Hermes repo |
| `--version REF` | string | `upstream/main` | 指定目标 git ref，支持 tag/branch/remote ref/SHA |
| `--dry-run` | flag | false | 只输出计划，不修改文件、git、gateway、origin |
| `--no-restart` | flag | false | 跳过 gateway restart，输出手动命令 |
| `--no-push` | flag | false | 跳过 push origin，输出手动命令 |
| `--backup-dir PATH` | path | `/tmp` | 备份与 manifest 输出目录 |
| `--rollback MANIFEST` | path | null | 进入回滚模式，不执行升级 |
| `--yes` | flag | false | 非交互确认；不得绕过冲突/失败保护 |
| `--verbose` | flag | false | 输出更详细命令日志 |

参数冲突：

- `--rollback` 与 `--version`、`--no-push`、`--no-restart` 同时出现时，rollback 优先；实现应拒绝无意义组合或忽略并明确提示。
- `--dry-run --rollback MANIFEST` 表示打印 rollback 计划，不实际恢复。

### 4.3 `UpgradeConfig` 契约

```text
repo: Path
version_ref: str
backup_dir: Path
dry_run: bool
restart: bool
push: bool
rollback_manifest: Optional[Path]
yes: bool
verbose: bool
hermes_bin: Path = /home/pascal/.local/bin/hermes
```

### 4.4 `UpgradeManifest` JSON 契约

Manifest 必须是 JSON，可由 `--rollback` 读取。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | string | 是 | 固定 `1` |
| `created_at` | string | 是 | ISO timestamp |
| `repo` | string | 是 | Hermes repo 绝对路径 |
| `pre_head` | string | 是 | 升级前 HEAD SHA |
| `pre_branch` | string | 是 | 升级前分支 |
| `target_ref` | string | 是 | 输入 ref |
| `target_sha` | string/null | 否 | fetch/resolve 后写入 |
| `backup_zip` | string | 是 | zip 路径 |
| `stash_ref` | string/null | 否 | dirty tree stash ref |
| `merge_mode` | string/null | 否 | `ff-only` / `merge` / `already-up-to-date` |
| `post_head` | string/null | 否 | merge 后 HEAD |
| `install_status` | string/null | 否 | `pending` / `ok` / `failed` |
| `verify_status` | string/null | 否 | `pending` / `ok` / `failed` |
| `restart_status` | string/null | 否 | `skipped` / `ok` / `failed` |
| `push_status` | string/null | 否 | `skipped` / `ok` / `failed` |
| `commands` | array | 是 | 已执行命令摘要，含 cwd/exit_code，脱敏 |

### 4.5 Git 策略契约

| 场景 | 判定 | 动作 |
|---|---|---|
| already up to date | `HEAD == target_sha` | 跳过 merge，仍可 install/verify/restart/push 由参数决定 |
| fast-forward | `git merge-base --is-ancestor HEAD target_sha` | `git merge --ff-only target_sha` |
| local-only commit | `HEAD` 非 target ancestor 且 local commits 不为空 | 先检查/推送 origin 保护，再 `git merge --no-edit target_sha` |
| unrelated/复杂 diverged | merge-base 不存在或 merge 预检失败 | 停止，输出人工处理说明 |
| conflict | merge 返回非 0 且存在 unmerged files | `git merge --abort`，保留 stash，停止 |

### 4.6 安装与验证契约

Design 阶段必须在以下两个安装方案中明确选择一个：

1. 复用 Hermes 官方 update 路径的可调用命令；或
2. 直接在 repo 内执行 editable install，例如基于本地实际 venv/uv 的 `uv pip install -e '.[all]'` fallback 到 `python -m pip install -e '.[all]'`。

无论选择哪种，SPEC 要求验证至少包含：

| 验证项 | 命令/方法 | 成功条件 |
|---|---|---|
| CLI boot | `/home/pascal/.local/bin/hermes --version` | exit code 0，输出非空版本信息 |
| install method | 读取 `.install_method` 或 `hermes_cli.config.detect_install_method` | git 源码安装仍可识别 |
| gateway status | `/home/pascal/.local/bin/hermes gateway status` 或 Design 选定 health endpoint | exit code 0 或可解析健康状态 |
| Python import | `python -c 'import hermes_cli'` 在目标环境中运行 | exit code 0 |

### 4.7 Gateway 重启契约

- 默认启用 restart，除非传入 `--no-restart`。
- 脚本必须检测当前是否可能运行在 gateway 子进程/网关触发上下文；若无法安全确认，仍必须使用 detached restart，而不是同步阻塞 restart。
- detached restart 的最低要求：
  - restart command 脱离当前进程树：`setsid`、`nohup`、延迟 shell helper 或 Design 等价方案；
  - stdout/stderr 写入 `restart_log`；
  - 主脚本等待健康检查结果，但不得依赖被 restart 杀死的子进程继续执行关键清理；
  - 如果不能安全自动 restart，应退化为 `--no-restart` 行为并返回需人工处理。

## 5. 配置契约

本 SPEC 不新增或修改 Hermes `config.yaml` 字段，不修改 `.env`。

| 配置项 | 行为 |
|---|---|
| provider/model/fallback | 不读取完整配置，不修改 |
| gateway platform credentials | 不读取、不打印、不修改 |
| profile toolsets | 不修改 |
| updates.* | 可读取但不得写入；如使用 Hermes 内置 update 需记录实际行为 |
| `.install_method` | 可读取用于校验 git 安装；不得随意覆盖 |

## 6. 行为契约（用户决策 → 代码层映射）

| 用户/Intake 决策 | SPEC 落地点 | 章节 |
|---|---|---|
| Q1 原倾向 fast-forward only，但当前有本地 commit，需修正为 A+ | Git 策略：ff 优先，local-only commit 时保护后 merge | 4.5 |
| Q2 默认 upstream/main HEAD，支持 `--version` 任意 git ref | CLI 参数 `--version` 与 ref 解析 | 4.2, 4.5 |
| Q3 自动 git stash + zip 备份到 `/tmp/hermes-backup-{timestamp}.zip` | F-004/F-006 与 Manifest | 3, 4.1, 4.4 |
| Q4 先本地验证成功，再 push origin | F-011~F-015 顺序与验收 | 3, 4.6, 10 |
| gateway 内部不能直接 restart | detached restart 契约与 `--no-restart` | 4.7 |
| 不改 Hermes profile 配置 | Out of Scope 与配置契约 | 2.2, 5 |

## 7. 错误契约

| 错误情形 | 检测方式 | 处理方式 | 是否允许 push |
|---|---|---|---|
| repo 不存在/非 git | path / `.git` 检查 | exit 1，提示 `--repo` | 否 |
| 缺 origin/upstream | `git remote get-url` | exit 1，提示添加 remote | 否 |
| 当前分支非 main | `git branch --show-current` | 默认 exit 1；Design 可定义 `--branch` 扩展 | 否 |
| dirty tree stash 失败 | stash exit code | exit 1，提示人工处理 | 否 |
| zip 备份失败 | zip exception | exit 1，不继续 git 操作 | 否 |
| fetch 失败 | git exit code | exit 1，分类提示网络/auth/ref | 否 |
| ref 无效 | `rev-parse --verify` | exit 1，提示 ref | 否 |
| origin 保护失败 | push/check exit code | exit 1，提示手动 push/检查 SSH | 否 |
| merge conflict | unmerged files | `git merge --abort`，保留 stash，exit 1 | 否 |
| install 失败 | install exit code | exit 1，manifest 标记 failed | 否 |
| `hermes --version` 失败 | exit code | exit 1，建议 rollback | 否 |
| gateway health 失败 | status/health 非健康 | exit 1 或 restart failed，提示手动处理 | 否 |
| push origin 失败 | push exit code | exit 1，本地保持升级后状态，输出手动 push | 已验证但未同步 |
| rollback 失败 | rollback command exit | exit 1，输出人工 reset/unzip/stash 命令 | 不适用 |

## 8. 文件改动清单

### 8.1 新增

- `docs/rfc/10_infra/RFC-10-005-hermes-auto-upgrade.md`
- `docs/spec/10_infra/SPEC-10-005-hermes-auto-upgrade.md`
- `docs/design/10_infra/DESIGN-10-005-hermes-auto-upgrade.md`（Design 阶段创建）
- `scripts/upgrade/upgrade_hermes_agent.py`（Implement 阶段创建）
- 可选：`scripts/upgrade/README.md`（如果 Design 认为需要）

### 8.2 修改

- 无必改现有代码文件。
- 如果 Implement 需要测试，可新增或修改本脚本相关测试文件，Design 阶段须列明具体路径。

### 8.3 不改动（明确列出）

- `/home/pascal/workspace/hermes-agent/**` 源码：本项目实现阶段不得直接修改；脚本运行升级时由 git 管理变更另算。
- `~/.hermes/profiles/*/config.yaml`
- `~/.hermes/profiles/*/.env`
- `~/.hermes/auth.json` 或 profile auth 文件
- YQuant `skills/data/**`、`docs/rfc/03_data/**`、`docs/spec/03_data/**`
- Hermes gateway platform 配置和 systemd unit 文件
- 生产数据库、报告调度、投资/交易/风控业务逻辑

## 9. 测试要求

| 编号 | 类型 | 命令 / 方法 | 断言 |
|---|---|---|---|
| UT-001 | CLI help | `python3 scripts/upgrade/upgrade_hermes_agent.py --help` | exit 0，列出核心参数 |
| UT-002 | dry-run | `python3 scripts/upgrade/upgrade_hermes_agent.py --dry-run --no-restart --no-push` | exit 0；输出 fetch/stash/merge/install/verify/push plan；Hermes repo status 不变 |
| UT-003 | invalid ref | `--dry-run --version definitely-not-a-ref` 或 mock rev-parse | exit 非 0 或 dry-run 明确 invalid；不修改 repo |
| UT-004 | manifest serialization | 单元测试构造 `UpgradeManifest` 写读 | JSON 字段完整，可被 rollback 读取 |
| UT-005 | command wrapper | mock subprocess 返回成功/失败 | 记录 cwd/exit_code；失败按契约中止 |
| UT-006 | secret redaction | 输入含 token-like 字符串的命令输出 | 日志中被脱敏或不记录敏感值 |
| IT-001 | temp git repo ff | 临时 origin/upstream/local repo 模拟 ff | dry-run 与真实测试均到目标 SHA |
| IT-002 | temp git repo local commit merge | 临时 repo 模拟本地领先 upstream | merge commit 产生；local commit 保留 |
| IT-003 | temp git conflict | 临时 repo 制造冲突 | merge abort；exit 非 0；stash/manifest 保留 |
| IT-004 | rollback temp repo | 用 manifest 回滚临时 repo | HEAD 回到 pre_head，dirty stash 可恢复 |
| IT-005 | executable bit | `test -x scripts/upgrade/upgrade_hermes_agent.py` | exit 0 |
| LINT-001 | Python syntax | `python3 -m py_compile scripts/upgrade/upgrade_hermes_agent.py` | exit 0 |
| LINT-002 | Optional ruff | 如果项目已有 ruff 配置则运行目标文件 lint | exit 0 或记录无 ruff |
| REG-001 | git 范围 | `git status --short` | 只包含本任务文档/脚本相关变更与既有无关变更；不得触碰 OUT 文件 |

不可自动化验证项：

- 真实 gateway restart 可能影响当前 Hermes 服务，Verify 阶段默认用 `--no-restart` 或 mock/dry-run；真实 restart 需 Pascal/主控明确确认。
- 真实 push origin 会写远端 fork，Verify 阶段默认用 `--no-push` 或临时 repo；真实 push 需 Pascal/主控明确确认。

## 10. 验收标准

| 编号 | 验收项 | 验证方式 | 对应测试 |
|---|---|---|---|
| A-001 | 脚本存在且可执行 | `test -x scripts/upgrade/upgrade_hermes_agent.py` | IT-005 |
| A-002 | `--help` 正常 | help 命令 | UT-001 |
| A-003 | `--dry-run` 不修改真实 repo | dry-run 前后 `git -C /home/pascal/workspace/hermes-agent status --short` 一致 | UT-002 |
| A-004 | 支持 `--version` ref 解析 | tag/branch/SHA/invalid ref 测试 | UT-003 / IT |
| A-005 | 升级前有 zip + manifest + stash 保护 | 临时 repo 或 mock 验证 | UT-004 / IT-002 |
| A-006 | 本地 commit 场景采用 merge 而非失败卡死 | temp repo local commit merge | IT-002 |
| A-007 | conflict 时 abort 且不 push | temp conflict repo | IT-003 |
| A-008 | install/verify 失败不 push | mock install/version failure | UT-005 |
| A-009 | rollback 可恢复 | temp repo rollback | IT-004 |
| A-010 | 不修改 profiles/config/secrets | 文件范围检查 | REG-001 |
| A-011 | 日志不泄漏 secrets | secret redaction test | UT-006 |
| A-012 | 真实 destructive 操作默认需要明确参数/确认 | `--no-restart`/`--no-push` 与 `--yes` 行为审查 | Review |

## 11. 实现约束

- 必须使用 Python 标准库优先实现；新增第三方依赖必须回到 Principal/主控确认。
- 所有路径必须支持显式 `--repo`，但默认值固定为当前 Hermes repo。
- Git 命令必须通过 `subprocess.run([...], shell=False)` 形式执行，避免 shell injection。
- `--version` 值不得拼接进 shell 字符串；必须作为 argv 元素传给 git。
- zip 备份不得包含 `.env`、`auth.json`、profile secrets；备份 Hermes repo 工作树时一般不涉及 profile secrets，但 Design 阶段仍需列出排除规则。
- 回滚模式必须先打印将恢复的 repo/pre_head/backup_zip/stash_ref，并在非 `--yes` 时要求交互确认；若运行环境非交互且无 `--yes`，应拒绝执行真实 rollback。
- push origin 必须在 install/version/gateway 验证成功之后。
- 真实 gateway restart 与真实 push 在测试阶段默认跳过；不得为了验收在当前生产 gateway 上冒险操作。

## 12. 风险与未解决问题

| 风险 | 缓解 | 归属 |
|---|---|---|
| 安装命令选择错误导致 Hermes CLI 不可用 | Design 阶段读取本地 Hermes update 实现与 venv 布局；Verify 用 mock/临时环境 | Principal/Tester |
| gateway restart 误杀升级进程 | detached restart + `--no-restart` 安全阀；真实 restart 需确认 | Developer/Tester |
| fork push 改写或泄漏错误历史 | 禁止 force push；push 前验证 HEAD 与 remote 关系 | Developer/Reviewer |
| 备份体积过大 | Design 阶段定义 zip exclude；manifest 保留 git pre_head 作为主恢复锚点 | Principal |
| `--version` 指向旧 tag 导致 downgrade | dry-run 明确显示 target 与 current；真实执行可要求 `--yes` | Developer/Reviewer |

未解决问题（移交 Design）：

- 最终安装命令选型：是否复用 Hermes 内置 update 的部分行为，还是脚本直接执行 editable install。
- gateway health check 的具体机制与超时阈值。
- zip 备份 exclude 规则：是否排除 `.git/objects`、`venv`、`node_modules` 等大目录，同时保持恢复能力。
- 是否需要新增 `--branch` 支持非 main；本 SPEC 默认不支持。
