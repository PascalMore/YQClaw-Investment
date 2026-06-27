# RFC-10-005：Hermes Agent 自动升级脚本

## 元数据（Metadata）

| 项 | 值 |
|---|---|
| 状态 | 已采纳（Accepted） |
| 作者 | YQuant-Codex-Principal |
| 创建日期 | 2026-06-27 |
| 最后更新 | 2026-06-27 |
| 版本号 | V1.0 |
| 所属模块 | 10_infra（基础设施 / Hermes 运维自动化） |
| 依赖 RFC | RFC-10-003-infra-architecture, RFC-10-004-yquant-ai-coding-pipeline-skill-sync |
| 替代 RFC | 无 |
| 适配 AI 工具 | Hermes Agent, Hermes Gateway, Hermes Kanban |
| 标签 | #infra #hermes #upgrade #ops #automation |

## 版本历史（Changelog）

| 版本号 | 日期 | 更新内容 | 负责人 |
|---|---|---|---|
| V1.0 | 2026-06-27 | 初始创建，定义 Hermes Agent fork/upstream 自动升级、验证、推送与安全重启策略 | YQuant-Codex-Principal |

## 1. 执行摘要

当前 Hermes Agent 源码安装位于 `/home/pascal/workspace/hermes-agent`，origin 指向 Pascal fork，upstream 指向 NousResearch 官方仓库；本地既有用户自有 commit，也存在未提交改动。手工升级需要处理 fetch、备份、stash、upstream 合并、安装、验证、gateway 重启与 origin push，多步骤且易误删本地修复。

本 RFC 建议在 YQuant 项目 `scripts/upgrade/` 下新增一个可审计的 Python 自动升级脚本：默认升级到 `upstream/main`，也支持 `--version` 指定任意 git ref；升级前做 git stash 与 zip 备份；本地验证成功后再 push origin；gateway 重启采用脱离当前 gateway 进程树的安全方案，避免从 gateway 内部执行同步 restart 导致 SIGTERM 传播。

## 2. 背景与动机

### 2.1 当前环境

| 项 | 当前值 |
|---|---|
| Hermes repo | `/home/pascal/workspace/hermes-agent` |
| origin | `git@github.com:PascalMore/hermes-agent.git` |
| upstream | `https://github.com/NousResearch/hermes-agent.git` |
| 当前分支 | `main` |
| 本地 HEAD | `1db4992d6`，含 Pascal fork 的飞书 markdown 表格修复 |
| upstream/main | `fbf748b28`，领先本地 10+ commit |
| 未提交改动 | `gateway/shutdown_forensics.py`, `tests/gateway/test_shutdown_forensics.py`, `.install_method` |
| 安装方式 | git 源码安装，`.install_method=git` |
| 当前版本 | Hermes Agent v0.16.0 (2026.6.5) |
| 最新 tag | `v2026.6.19` |
| hermes 命令 | `/home/pascal/.local/bin/hermes` |
| Python | 3.11.15 |

### 2.2 现状痛点

- 手动升级需要同时理解 fork、upstream、origin、local commits、dirty tree 与 Hermes gateway 运行态，操作链长。
- “fast-forward only” 在本地已有自有 commit 且 upstream 继续前进时不可直接满足；若无策略修正，脚本会长期卡在 diverged 状态。
- Hermes 官方 `hermes update` 已有大量保护逻辑，但它主要围绕当前 install 的 origin/update branch；本需求还需要把官方 upstream 变更同步到 Pascal fork，并在本地验证后再 push fork。
- 从 gateway 内部直接执行 `hermes gateway restart` 可能因 systemd/cgroup 或父子进程信号传播导致当前升级流程被杀死。
- 升级失败若没有 zip 备份、stash ref 和清晰回滚说明，恢复成本高。

### 2.3 业务价值

- 将 Hermes Agent 升级从多步人工操作收敛为一条命令，提高运维确定性。
- 明确保护 Pascal fork 的本地 commit 和未提交工作，降低误删风险。
- 在 push origin 前完成本地安装与健康检查，避免把不可用状态推送到 fork。
- 输出审计日志，方便后续 reviewer/tester 复盘升级过程。

## 3. 目标与非目标

### 3.1 必须目标（Must-Have）

- [ ] 在 `scripts/upgrade/` 下新增 Hermes Agent 自动升级脚本的 RFC/SPEC/Design/实现交付链。
- [ ] 默认目标为 `upstream/main`，支持 `--version <git-ref>` 指定 tag、branch、commit 或 remote ref。
- [ ] 升级前自动创建 zip 备份到 `/tmp/hermes-backup-{timestamp}.zip`，并对 dirty tree 创建 git stash。
- [ ] 检测本地领先 upstream 的 commit，先确保可 push origin 保护，再合并 upstream 目标。
- [ ] 升级策略支持 fast-forward 优先；当本地存在自有 commit 导致 ff-only 不可行时，采用显式 merge upstream 的 A+ 策略；冲突时中止并要求人工处理。
- [ ] 本地安装、版本验证、gateway 健康检查通过后再 push origin。
- [ ] 支持 `--dry-run` 输出将执行的步骤而不修改 repo、venv、gateway 或 origin。
- [ ] 支持回滚，从 zip 备份与 git 记录恢复。
- [ ] gateway 重启不得在 gateway 进程内同步执行会自杀的 restart；脚本必须使用脱离进程树的 restart job 或 `--no-restart` 明确跳过。

### 3.2 非目标（Out of Scope）

- [ ] 不修改 `/home/pascal/workspace/hermes-agent` 源码内容，除升级时由 git merge/fetch/pull 带来的上游代码变更。
- [ ] 不修改 Hermes profile `config.yaml`、`.env`、MCP、model/fallback 配置。
- [ ] 不实现 CI/CD、GitHub Actions、自动定时升级或容器化部署。
- [ ] 不替代 Hermes 官方 `hermes update` 的全部能力；本脚本是 Pascal fork/upstream 同步与本机升级编排器。
- [ ] 不自动解决 merge conflict；发生冲突必须停止并输出人工处理说明。
- [ ] 不执行真实交易、投资策略或生产数据 schema 变更。

## 4. 整体设计

### 4.1 核心设计哲学

脚本应是“保守、安全、可回滚”的运维编排器：优先保护当前状态，所有 destructive 操作前都留下可恢复锚点；本地验证成功才 push；凡是可能需要人工语义判断的冲突不自动猜测。

### 4.2 架构总览

```text
YQuant repo
  scripts/upgrade/upgrade_hermes_agent.py
        |
        | validates args/env
        v
Hermes repo (/home/pascal/workspace/hermes-agent)
  1. inspect remotes/branch/status
  2. create zip backup under /tmp
  3. stash dirty tree
  4. fetch upstream + origin
  5. resolve target ref (--version or upstream/main)
  6. protect local-only commits by push/check origin
  7. merge target into local main (ff if possible, merge commit otherwise)
  8. install dependencies / editable package
  9. verify hermes --version and gateway health
 10. detached restart if enabled
 11. push origin main only after local verification
```

### 4.3 模块分工

| 模块 | 职责 | 输入 | 输出 |
|---|---|---|---|
| CLI 参数层 | 解析 `--version`, `--dry-run`, `--repo`, `--no-restart`, `--push`, `--rollback` 等参数 | argv | 运行配置 |
| 状态检查层 | 检查 repo/remotes/branch/dirty tree/local-only commits/install method | hermes repo | 升级前状态报告 |
| 备份层 | zip 备份、stash、记录 pre-upgrade HEAD | repo path | backup manifest |
| Git 升级层 | fetch、resolve ref、merge、冲突检测 | target ref | updated worktree 或 abort |
| 安装验证层 | 安装依赖/包、清 pycache、运行 `hermes --version`、gateway health | updated repo | verification report |
| 重启层 | 使用 detached job 或跳过重启 | restart policy | gateway restart status |
| 推送层 | 验证通过后 push origin | local main | origin updated |
| 回滚层 | 从 manifest/zip/stash/pre HEAD 恢复 | backup id/path | restored repo |

## 5. 详细设计

### 5.1 业务流程

1. 解析参数，默认 `repo=/home/pascal/workspace/hermes-agent`，默认 `target=upstream/main`。
2. 读取并校验 repo：必须是 git repo；必须存在 `origin` 与 `upstream`；当前工作分支必须为 `main`，除非后续 SPEC/Design 明确支持 `--branch`。
3. 输出升级前状态：HEAD、branch、remotes、dirty files、local-only commits、upstream target、origin target。
4. 创建 `/tmp/hermes-backup-{timestamp}.zip`，覆盖 repo 工作树关键内容但排除 `.git/objects` 中可由 git 恢复的大体积对象可在 Design 阶段评估；同时生成 manifest JSON。
5. 若 dirty tree 非空，执行 `git stash push --include-untracked -m "hermes-auto-upgrade-{timestamp}"`，记录 stash ref；dry-run 只打印。
6. `git fetch upstream --tags` 与 `git fetch origin`。
7. 将 `--version` 解析为 commit SHA：支持 `v2026.6.19`、`upstream/main`、`main`、短 SHA/长 SHA；默认 `upstream/main`。
8. 检测 `upstream/<target>` 与本地 `HEAD` 的关系：
   - 若可 fast-forward，执行 `git merge --ff-only <target_sha>`。
   - 若本地有 Pascal 自有 commit，先确认 origin 已包含或可接收这些 commit，再执行 `git merge --no-edit <target_sha>` 创建 merge commit。
   - 若 merge conflict，执行 `git merge --abort`，保留 stash，停止并输出人工处理步骤。
9. 清理 Python bytecode cache，执行安装命令（Design 阶段决定调用 Hermes 内置 update 子流程还是使用 `uv pip install -e '.[all]'` / fallback）。
10. 验证 `hermes --version` 能正常执行；如果指定 tag 可检查版本日期或 commit 近似匹配；运行 gateway health/status 检查。
11. 如果 `--no-restart` 为 false，安排 detached restart：不得从 gateway 进程内阻塞执行 `hermes gateway restart`；应使用 `setsid/nohup` 或小型 helper 延迟执行，并把日志写到 `/tmp/hermes-upgrade-restart-{timestamp}.log`。
12. 重启/健康检查通过后 push origin；若 push 失败，不回滚本地成功升级，但明确提示 fork 未同步。
13. 如果任何 install/verify 步骤失败，停止在本地，提示 `--rollback <manifest>`。

### 5.2 数据模型

| 实体 | 字段 | 类型 | 说明 |
|---|---|---|---|
| UpgradeConfig | repo | path | Hermes repo，默认 `/home/pascal/workspace/hermes-agent` |
| UpgradeConfig | target_ref | string | `--version` 或默认 `upstream/main` |
| UpgradeConfig | dry_run | bool | 只打印计划不执行修改 |
| UpgradeConfig | restart | bool | 默认 true，`--no-restart` 设为 false |
| UpgradeConfig | push | bool | 默认 true，`--no-push` 设为 false |
| UpgradeState | pre_head | sha | 升级前 HEAD |
| UpgradeState | target_sha | sha | 解析后的目标 commit |
| UpgradeState | stash_ref | string/null | dirty tree stash 引用 |
| UpgradeState | backup_zip | path | `/tmp/hermes-backup-{timestamp}.zip` |
| UpgradeState | merge_mode | enum | `already-up-to-date`, `ff-only`, `merge`, `abort-conflict` |
| UpgradeState | verification | object | install/version/gateway/push 结果 |
| RollbackManifest | schema_version | string | manifest schema 版本 |
| RollbackManifest | repo | path | 原 repo 路径 |
| RollbackManifest | pre_head | sha | 可 reset 的 git 锚点 |
| RollbackManifest | backup_zip | path | zip 备份路径 |
| RollbackManifest | stash_ref | string/null | 可恢复 dirty tree 的 stash |
| RollbackManifest | created_at | string | ISO timestamp |

### 5.3 接口契约

本 RFC 不新增 Python package API，对外命令接口由 SPEC 固化。建议入口：

```bash
python3 scripts/upgrade/upgrade_hermes_agent.py [options]
```

核心参数：

```text
--version <git-ref>      指定升级目标；默认 upstream/main
--repo <path>            Hermes repo；默认 /home/pascal/workspace/hermes-agent
--dry-run                打印计划，不执行 git/install/restart/push 修改
--no-restart             本次不重启 gateway，只输出手动重启命令
--no-push                本地验证后不 push origin
--rollback <manifest>    根据 manifest 执行回滚
--yes                    非交互确认，仅允许在已满足安全前置条件时使用
```

### 5.4 AI 模型设计

不涉及 AI 模型变更。脚本不得读取或修改 Hermes provider/model/fallback 配置，不得打印 secrets。

## 6. AI 实装规范

### 6.1 必须执行

- 使用 Python 实现，优先标准库：`argparse`, `subprocess`, `pathlib`, `json`, `zipfile`, `datetime`, `shutil`。
- 每个外部命令必须记录命令、cwd、exit code；日志不得包含 token 或 `.env` 内容。
- destructive 操作前必须已写入 manifest 或可恢复锚点。
- dry-run 必须覆盖完整计划，包括将要执行的 git 命令、安装命令、验证命令、restart/push 行为。
- merge conflict、install 失败、gateway health 失败必须返回非零 exit code。

### 6.2 先询问再执行

- 删除或 hard reset Hermes repo 工作树。
- 自动解决 merge conflict。
- 修改 Hermes profile config、secrets、gateway platform 配置。
- 引入新第三方依赖。
- 改变生产 gateway 长期服务配置或 systemd unit。

### 6.3 绝对禁止

- 不得在未备份、未记录 pre_head 的情况下执行 `git reset --hard`。
- 不得在验证失败时 push origin。
- 不得从 gateway 进程内同步执行可能杀死自身的 `hermes gateway restart`。
- 不得打印 `.env`、API key、OAuth token、auth.json 或 profile secrets。
- 不得把冲突文件自动选择 `ours/theirs` 后继续升级。

## 7. 风险与应对

| 风险 | 概率 | 影响 | 应对方案 | 降级策略 |
|---|---|---|---|---|
| 本地自有 commit 与 upstream 冲突 | 中 | 高 | merge 前保护 origin；冲突时 abort 并保留 stash | 人工 resolve 后重跑 |
| dirty tree 被覆盖 | 中 | 高 | zip 备份 + `git stash --include-untracked` + manifest | `--rollback` 恢复 zip/stash |
| pip/uv install 失败 | 中 | 高 | 安装阶段非零即停止，不 push origin | rollback 到 pre_head 或使用 Hermes 内置 `hermes update` 手动修复 |
| gateway restart 自杀 | 中 | 高 | detached restart 或 `--no-restart` | 另一个 shell 手动 `hermes gateway restart` |
| push origin 失败 | 中 | 中 | push 放在验证后，失败只影响 fork 同步 | 输出手动 push 命令，保留本地成功状态 |
| `--version` 指向不可达 ref | 中 | 低 | fetch 后 `rev-parse --verify` | 停止并提示 ref 无效 |
| zip 备份过大或耗时 | 中 | 中 | Design 阶段明确排除策略；显示备份大小 | 允许 `--backup-dir` 后续扩展 |
| Hermes CLI 行为随 upstream 改变 | 中 | 中 | 使用官方 docs 与本地源码检测安装方法 | Design/Review 阶段重新核对命令 |

## 8. 备选方案

### 8.1 直接使用 `hermes update`

优点：复用官方内置更新、备份、安装、重启保护。缺点：当前需求要同步 NousResearch upstream 到 Pascal fork origin，并保护 fork-local commit；`hermes update` 的默认路径并不完整表达“upstream -> local fork -> verify -> origin fork push”的策略。最终不单独采用，可在安装/验证阶段借鉴或部分调用。

### 8.2 纯 bash 脚本

优点：实现快，适合串联 git 命令。缺点：复杂错误处理、manifest、zip、dry-run、日志脱敏、跨 WSL/未来 Linux 行为更难维护。最终不选，建议 Python。

### 8.3 rebase Pascal commit 到 upstream

优点：历史线性。缺点：会改写本地自有 commit 的 SHA，对 fork origin 和现有工作树风险更高，需要更强人工判断。默认不选；除非 Pascal 显式要求线性历史。

### 8.4 fast-forward only + abort

优点：最安全，不产生 merge commit。缺点：当前本地已有领先 upstream 的自有 commit，长期无法升级。最终不选为唯一策略；保留为“可 ff 时优先 ff”。

### 8.5 A+：保护本地 commit 后 merge upstream

优点：保留 Pascal 自有 commit，不改写历史；能处理当前 fork diverged 状态；验证成功后 push origin。缺点：可能产生 merge commit，冲突时需人工处理。最终选用。

## 9. 验收标准

### 9.1 功能验收

- RFC/SPEC/Design 三层文档分别存在于 `docs/rfc/10_infra/`、`docs/spec/10_infra/`、`docs/design/10_infra/`。
- `scripts/upgrade/upgrade_hermes_agent.py --dry-run` 输出完整执行计划，且不修改 Hermes repo、gateway、origin。
- `--version <git-ref>` 能解析 tag、branch、commit；无效 ref 返回非零并说明错误。
- dirty tree 时创建 stash 与 zip 备份，manifest 记录 pre_head、target_sha、stash_ref、backup_zip。
- 本地有自有 commit 时，脚本采用 A+ merge 策略而不是卡死在 ff-only。
- install/version/gateway 验证失败时，不 push origin。
- 验证成功时，push origin fork，并输出新 HEAD。
- `--rollback <manifest>` 能给出可执行恢复步骤；Design/Implement 阶段至少要自动恢复 git HEAD 与 zip 文件。

### 9.2 非功能验收

- 不修改 Hermes profile config、secrets 或 YQuant 业务代码。
- 日志不泄漏 token、`.env`、`auth.json` 内容。
- 脚本对重复运行幂等：already-up-to-date、已有 stash、已同步 origin 等场景有明确行为。
- 失败路径输出足够清晰，operator 能知道下一步是 retry、rollback 还是人工解决冲突。

## 10. 落地计划

### 10.1 阶段划分

1. RFC/SPEC：定义升级策略、输入输出、错误与验收契约。
2. Design：定义脚本文件结构、函数分解、命令序列、日志、manifest、回滚和测试设计。
3. Implement：在 `scripts/upgrade/` 下实现脚本，不修改 Hermes 源码。
4. Verify：执行 dry-run、无效 ref、help、lint，以及可安全模拟的 git 测试。
5. Review：审查是否误触生产配置、是否满足 RFC/SPEC/Design。

### 10.2 任务清单

| 阶段 | 负责人 | 交付物 |
|---|---|---|
| RFC/SPEC | yquantprincipal | RFC-10-005、SPEC-10-005 |
| Design | yquantprincipal | DESIGN-10-005 |
| Implement | yquantdeveloper | `scripts/upgrade/upgrade_hermes_agent.py` 与必要 README/测试 |
| Verify | yquanttester | dry-run/lint/模拟仓库验证报告 |
| Review | yquantreviewer | 独立代码与风险审查 |

## 11. 开放问题

- Design 阶段需最终确认安装命令：直接调用 Hermes 内置 `hermes update` 的部分逻辑、还是在脚本内执行 `uv pip install -e '.[all]'` / fallback。
- Design 阶段需确认 gateway health check 的具体命令：`hermes gateway status`、API Server health endpoint，或二者组合。
- 是否允许脚本在非 `main` 分支执行？本 RFC 默认不允许，后续如需支持应另加参数与测试。
- zip 备份是否排除 `.git/objects` 以降低大小？Design 阶段需在可恢复性与体积之间决策。

## 12. 参考资料

- Hermes Agent docs: `https://hermes-agent.nousresearch.com/docs/`
- Hermes skill: `hermes-agent`（CLI、gateway、update、profile 路径约定）
- 本地 Hermes 源码：`/home/pascal/workspace/hermes-agent/hermes_cli/main.py` 的 `cmd_update` / `_cmd_update_impl`
- 本地 Hermes 源码：`/home/pascal/workspace/hermes-agent/hermes_cli/config.py` 的 `detect_install_method` / `recommended_update_command_for_method`
- `docs/rfc/10_infra/RFC-10-004-yquant-ai-coding-pipeline-skill-sync.md`
- `docs/spec/SPEC-00-000-spec-template.md`
