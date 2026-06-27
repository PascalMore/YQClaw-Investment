# DESIGN-10-005: Hermes Agent 自动升级脚本

## 元数据

| 项 | 值 |
|---|---|
| 状态 | Accepted |
| 作者 | YQuant-Codex-Principal |
| 创建日期 | 2026-06-27 |
| 最后更新 | 2026-06-27 |
| 来源 RFC | RFC-10-005-hermes-auto-upgrade |
| 来源 SPEC | SPEC-10-005-hermes-auto-upgrade |
| 目标模块 | 10_infra / Hermes 运维自动化 |
| 目标脚本 | `scripts/upgrade/upgrade_hermes_agent.py` |

## 1. 设计摘要

本设计把 RFC-10-005 与 SPEC-10-005 落为可实现的 Python 脚本设计。脚本定位为“Pascal fork 的 Hermes Agent 源码升级编排器”，不是 Hermes 官方 `hermes update` 的替代品：它以 `/home/pascal/workspace/hermes-agent` 这个 git 源码 checkout 为目标，默认从 `upstream/main` 升级，支持 `--version` 指向任意 git ref，并在本地安装、CLI/gateway 验证成功后才 push 到 Pascal fork 的 `origin/main`。

核心决策：

1. Git 策略采用 ff 优先；本地存在 Pascal 自有 commit 时采用 A+ merge：先保护本地 commit 可达于 origin，再 merge upstream target；冲突立即 abort，不自动选择 ours/theirs。
2. 备份采用“manifest + zip 工作树备份 + git stash + pre_head”四重锚点。git HEAD 是主恢复锚点，zip 覆盖 git 无法恢复或 dirty/untracked 文件，stash 保留未提交工作。
3. 安装命令不直接复用 `hermes update` 整体流程，因为官方实现会围绕当前 origin branch 更新，且包含 profile skill sync/config migration 等超出本脚本范围的副作用。脚本只复用其安装思想：优先使用 managed uv 执行 editable install，失败时 fallback 到 `python -m pip install -e '.[all]'`。
4. Gateway restart 默认使用 detached helper 触发 `/home/pascal/.local/bin/hermes gateway restart`，主脚本只等待健康检查；无法安全重启时退化为 `--no-restart` 行为并输出人工命令。
5. `--dry-run` 必须完整走 discovery/plan 逻辑，但不得写 zip、manifest、stash、git merge、install、restart 或 push。

## 2. 现状分析

### 2.1 相关目录与文件

| 路径 | 角色 | 本阶段行为 |
|---|---|---|
| `docs/rfc/10_infra/RFC-10-005-hermes-auto-upgrade.md` | 需求与决策来源 | 只读 |
| `docs/spec/10_infra/SPEC-10-005-hermes-auto-upgrade.md` | 可执行契约来源 | 只读 |
| `docs/design/10_infra/DESIGN-10-005-hermes-auto-upgrade.md` | 本 Design | 新增 |
| `scripts/upgrade/upgrade_hermes_agent.py` | 后续实现目标 | 本阶段不创建 |
| `/home/pascal/workspace/hermes-agent` | Hermes Agent 源码 repo | 本阶段只读分析，脚本运行时作为目标 repo |
| `/home/pascal/workspace/hermes-agent/hermes_cli/main.py` | 官方 update 行为参考 | 只读 |
| `/home/pascal/workspace/hermes-agent/hermes_cli/config.py` | 安装方法检测参考 | 只读 |

### 2.2 Hermes 官方 update 行为要点

从本地源码读取到的关键事实：

- `hermes_cli.config.detect_install_method(project_root)` 的优先级为：`<install tree>/.install_method`、legacy `$HERMES_HOME/.install_method`、managed 系统、`.git`、fallback `pip`。本脚本应调用等价检测或直接读取 `.install_method` + `.git`，并要求目标 repo 是 git 源码安装。
- `recommended_update_command_for_method()` 对 `git` 返回 `hermes update`，但本脚本不能直接执行 `hermes update` 作为升级主体，因为它更新当前 origin branch，不表达 upstream -> local fork -> verify -> origin fork push 的 A+ 策略。
- `_cmd_update_impl()` 的 git 路径会 `fetch origin <branch>`、stash dirty tree、`git pull --ff-only origin <branch>`，失败时可能 reset 到 origin；这与本需求“保护本地 commit 后 merge upstream”不同，不能照搬。
- `_install_python_dependencies_with_optional_fallback()` 的安装策略可借鉴：优先 `uv pip install -e '.[all]'`，optional extras 失败时先安装 base，再逐个安装 extras；本脚本实现可先做最小版本，不强制完整复制 optional fallback 细节，但必须保留 uv->pip fallback。
- 官方 gateway restart 路径包含 systemd、SIGUSR1 graceful drain、profile gateway relaunch 等复杂逻辑。为避免从 gateway 内同步自杀，本脚本不内联该复杂逻辑，而是 detached 启动 `hermes gateway restart` 或在 `--no-restart` 下输出手动命令。

### 2.3 约束与兼容性风险

- 目标运行环境是 WSL/Linux，默认 Hermes repo 为 `/home/pascal/workspace/hermes-agent`，Hermes CLI 为 `/home/pascal/.local/bin/hermes`。
- 本脚本不得修改 Hermes profile `config.yaml`、`.env`、`auth.json`、MCP、model/fallback 配置。
- 真实 push origin 与真实 gateway restart 是有副作用动作：脚本实现允许，但测试阶段默认用 `--no-push` / `--no-restart` 或 temp repo/mock；真实执行需 Pascal 或主控明确确认。
- 不支持非 `main` 工作分支；不新增 `--branch`。`--version` 是 target ref，不是工作分支选择器。

## 3. 方案设计

### 3.1 模块与函数分解

`upgrade_hermes_agent.py` 使用单文件 Python 标准库实现，推荐函数分解如下：

| 层级 | 函数 / 数据结构 | 职责 |
|---|---|---|
| CLI | `parse_args(argv) -> argparse.Namespace` | 定义 `--repo`, `--version`, `--dry-run`, `--no-restart`, `--no-push`, `--backup-dir`, `--rollback`, `--yes`, `--verbose` |
| Config | `UpgradeConfig.from_args(args) -> UpgradeConfig` | 将 CLI 参数标准化为内部配置 |
| Command | `run_cmd(cmd, cwd=None, check=False, capture=True, env=None) -> CommandResult` | 统一执行外部命令，记录 cwd/exit_code/stdout/stderr 摘要，禁止 `shell=True` |
| Redaction | `redact(text) -> str` | 对 token-like、`.env` 路径附近输出做保守脱敏 |
| Repo inspect | `inspect_repo(config) -> RepoState` | 校验 git repo、remotes、branch、install_method、HEAD、dirty files、local-only commits |
| Backup | `create_zip_backup(state, manifest) -> Path` | 按 include/exclude 规则创建 zip |
| Backup | `stash_dirty_tree(state, manifest) -> Optional[str]` | dirty tree 时执行 `git stash push --include-untracked` 并记录 stash ref |
| Git | `fetch_remotes(config, manifest)` | scoped fetch：`upstream` target 相关 ref/tag + `origin main` |
| Git | `resolve_target_ref(config) -> str` | 将 `--version` / `upstream/main` 解析为 commit SHA |
| Git | `classify_git_relation(head, target, origin_main) -> GitPlan` | 判定 already-up-to-date、ff-only、merge、invalid/unrelated/conflict-risk |
| Git | `protect_local_commits(plan)` | 检查本地领先 commit 已在 origin 可达；必要时先 push origin main 保护，不 force push |
| Git | `apply_merge(plan, manifest)` | ff-only 或 `git merge --no-edit <target_sha>`；冲突时 abort |
| Install | `install_editable(config, manifest)` | 清 pycache，优先 uv editable install，fallback 到 pip editable install |
| Verify | `verify_cli(config)`, `verify_import(config)`, `verify_gateway(config)` | 检查 `/home/pascal/.local/bin/hermes --version`、Python import、gateway status |
| Restart | `schedule_detached_restart(config, manifest)` | detached 启动 gateway restart helper，写 restart log |
| Push | `push_origin_if_enabled(config, manifest)` | 所有验证成功后 `git push origin main` |
| Rollback | `rollback_from_manifest(config)` | 读取 manifest，按 pre_head/zip/stash 恢复 |
| Reporting | `print_plan(plan)`, `write_manifest(manifest)` | 输出 dry-run/真实执行摘要，持续更新 manifest |
| Entrypoint | `main(argv=None) -> int` | 区分 rollback 与 upgrade 模式，统一 exit code |

建议使用 dataclass：

```text
@dataclass(frozen=True)
class UpgradeConfig:
    repo: Path
    version_ref: str
    backup_dir: Path
    dry_run: bool
    restart: bool
    push: bool
    rollback_manifest: Optional[Path]
    yes: bool
    verbose: bool
    hermes_bin: Path = Path('/home/pascal/.local/bin/hermes')

@dataclass
class CommandResult:
    cmd: list[str]
    cwd: Optional[str]
    exit_code: int
    stdout: str
    stderr: str

@dataclass
class RepoState:
    repo: Path
    branch: str
    pre_head: str
    origin_url: str
    upstream_url: str
    install_method: str
    dirty_files: list[str]
    local_only_commits: list[str]
    origin_main_sha: Optional[str]

@dataclass
class GitPlan:
    target_ref: str
    target_sha: str
    merge_mode: Literal['already-up-to-date', 'ff-only', 'merge']
    local_commits_need_protection: bool
```

### 3.2 CLI 参数到内部结构映射

| CLI 参数 | `UpgradeConfig` 字段 | 默认值 | 语义 |
|---|---|---|---|
| `--repo PATH` | `repo` | `/home/pascal/workspace/hermes-agent` | 目标 Hermes Agent 源码 repo，必须是绝对路径或可 resolve 为绝对路径 |
| `--version REF` | `version_ref` | `upstream/main` | 目标 git ref；可为 tag、remote ref、branch、SHA；不是工作分支选择 |
| `--dry-run` | `dry_run` | `False` | 只输出将执行步骤，不写文件、不执行修改命令 |
| `--no-restart` | `restart` | `True` | 设为 False 时跳过 detached gateway restart |
| `--no-push` | `push` | `True` | 设为 False 时本地验证后不 push origin |
| `--backup-dir PATH` | `backup_dir` | `/tmp` | manifest、zip、restart log 输出目录 |
| `--rollback MANIFEST` | `rollback_manifest` | `None` | 启动 rollback 模式；与升级动作互斥 |
| `--yes` | `yes` | `False` | 非交互确认；不得绕过 conflict、verify、push 顺序保护 |
| `--verbose` | `verbose` | `False` | 输出命令 stdout/stderr 摘要与更多诊断 |

参数冲突处理：

- `--rollback` 与 `--version`、`--no-push`、`--no-restart` 同时出现时返回 exit 2，并提示 rollback 模式只接受 `--repo`、`--backup-dir`、`--dry-run`、`--yes`、`--verbose`。
- `--dry-run --rollback MANIFEST` 表示打印 rollback 计划，不执行 reset/unzip/stash。
- `--yes` 只跳过“是否继续”的交互确认；不允许跳过备份、manifest、origin 保护、conflict abort、验证后 push 等硬性规则。

### 3.3 主控制流

```text
main
 ├─ parse_args / build UpgradeConfig
 ├─ if rollback_manifest:
 │    └─ rollback_from_manifest(config)
 └─ upgrade(config)
      ├─ inspect_repo
      ├─ build initial manifest path
      ├─ if dry_run: print discovered state + planned steps, then return 0
      ├─ create_zip_backup
      ├─ write_manifest(status=backup_created)
      ├─ stash_dirty_tree
      ├─ fetch_remotes
      ├─ resolve_target_ref
      ├─ classify_git_relation
      ├─ protect_local_commits if needed
      ├─ apply_merge
      ├─ install_editable
      ├─ verify_cli + verify_import + verify_gateway(pre-restart)
      ├─ schedule_detached_restart unless no-restart
      ├─ verify_gateway(post-restart) or mark restart skipped
      ├─ push_origin_if_enabled
      └─ final summary + manifest path
```

关键顺序不允许调整：

1. destructive git 操作前必须已有 zip + manifest + pre_head。
2. dirty tree 必须先 stash 再 merge。
3. 本地 commit 未保护时不得 merge upstream。
4. install/version/gateway 验证失败时不得 push origin。
5. push origin 必须晚于 restart 或明确 skipped restart；若 restart enabled 但失败，默认不得 push。

### 3.4 Git 状态机与 A+ merge 策略

#### 3.4.1 状态判定命令

| 信息 | 命令 |
|---|---|
| 当前分支 | `git branch --show-current` |
| 当前 HEAD | `git rev-parse HEAD` |
| dirty tree | `git status --porcelain=v1` |
| remote URL | `git remote get-url origin`, `git remote get-url upstream` |
| origin/main | `git rev-parse --verify origin/main` |
| target SHA | `git rev-parse --verify <ref>^{commit}` |
| ancestor 判断 | `git merge-base --is-ancestor A B` |
| local-only commits | `git rev-list --left-only --cherry-pick HEAD...upstream/main` 与 `git rev-list origin/main..HEAD` |
| unmerged files | `git diff --name-only --diff-filter=U` |

#### 3.4.2 状态机

```text
S0 inspect
 ├─ 非 git / 缺 remote / 非 main / 非 git install -> FAIL_PRECHECK
 └─ OK -> S1 backup

S1 backup
 ├─ zip/manifest 失败 -> FAIL_BACKUP
 └─ OK -> S2 stash

S2 stash
 ├─ dirty 且 stash 失败 -> FAIL_STASH
 └─ OK -> S3 fetch

S3 fetch/resolve
 ├─ fetch/ref 无效 -> FAIL_FETCH_OR_REF
 └─ target_sha -> S4 classify

S4 classify
 ├─ HEAD == target_sha -> ALREADY_UP_TO_DATE -> S7 install/verify
 ├─ HEAD ancestor of target -> FF_ONLY -> S6 merge
 ├─ target ancestor of HEAD -> LOCAL_AHEAD -> S5 protect + S6 merge/already
 ├─ merge-base exists -> DIVERGED -> S5 protect + S6 merge
 └─ no merge-base -> FAIL_UNRELATED

S5 protect local commits
 ├─ origin/main ancestor of HEAD 或 local commits already reachable from origin -> OK
 ├─ push origin main succeeds -> OK
 └─ push/check fails -> FAIL_LOCAL_PROTECTION

S6 merge
 ├─ ff-only succeeds -> S7
 ├─ no-edit merge succeeds -> S7
 ├─ conflict -> git merge --abort -> FAIL_CONFLICT
 └─ other failure -> FAIL_MERGE

S7 install/verify
 ├─ install/version/import/gateway fail -> FAIL_VERIFY
 └─ OK -> S8 restart

S8 restart
 ├─ restart skipped -> S9 push
 ├─ detached restart + health OK -> S9 push
 └─ restart fail -> FAIL_RESTART

S9 push
 ├─ push skipped -> DONE_LOCAL_ONLY
 ├─ push succeeds -> DONE_PUSHED
 └─ push fails -> FAIL_PUSH_NONROLLBACK
```

#### 3.4.3 A+ merge 详细流程

A+ 场景定义：本地 `main` 包含不在 upstream target 中的 Pascal 自有 commit，且 upstream target 也有本地未包含的新 commit。

执行流程：

1. `git fetch origin main` 与 `git fetch upstream --tags`。若 `--version` 是 remote ref，则 scoped fetch 对应 remote/ref。
2. 解析 `target_sha`。
3. 计算本地需要保护的 commit：`git rev-list target_sha..HEAD`。
4. 检查这些 commit 是否可由 `origin/main` 到达：如果 `git merge-base --is-ancestor HEAD origin/main` 成立，说明 origin 已包含；否则执行 `git push origin main` 保护。禁止 `--force` 与 `--force-with-lease`。
5. 执行 `git merge --no-edit target_sha`。禁止 rebase，避免改写 Pascal commit SHA。
6. 若 merge 返回非 0：读取 unmerged files；执行 `git merge --abort`；manifest 写入 `merge_mode=abort-conflict`、conflicted files；返回非零。
7. 若 merge 成功：记录 `post_head` 与 `merge_mode=merge`。
8. 后续 install/verify 成功后再执行第二次 `git push origin main`，把 upstream merge commit 同步到 Pascal fork。

### 3.5 Manifest schema

Manifest 文件路径：`/tmp/hermes-upgrade-{YYYYmmdd-HHMMSS}.json`，schema 版本固定为 `1`。实现必须在每个关键阶段后原子写入 manifest（先写临时文件，再 `Path.replace`）。

必填字段：

| 字段 | 类型 | 写入时机 | 说明 |
|---|---|---|---|
| `schema_version` | string | 初始化 | 固定 `1` |
| `created_at` | string | 初始化 | UTC ISO timestamp |
| `repo` | string | 初始化 | 目标 repo 绝对路径 |
| `pre_branch` | string | inspect 后 | 升级前分支，必须为 `main` |
| `pre_head` | string | inspect 后 | 升级前 HEAD SHA |
| `origin_url` | string | inspect 后 | origin URL，用于审计 |
| `upstream_url` | string | inspect 后 | upstream URL，用于审计 |
| `target_ref` | string | 初始化 | CLI 输入或默认 `upstream/main` |
| `target_sha` | string/null | ref resolve 后 | 目标 commit SHA |
| `backup_zip` | string | backup 后 | zip 路径 |
| `backup_size_bytes` | int/null | backup 后 | zip 大小 |
| `stash_ref` | string/null | stash 后 | dirty tree stash commit/ref |
| `dirty_files` | array[string] | inspect 后 | 备份前 dirty 文件清单 |
| `local_only_commits` | array[string] | classify 后 | Pascal 自有 commit 摘要 |
| `merge_mode` | string/null | merge 后 | `already-up-to-date` / `ff-only` / `merge` / `abort-conflict` |
| `post_head` | string/null | merge 后 | merge 后 HEAD |
| `install_status` | string | install 后 | `pending` / `ok` / `failed` / `skipped-dry-run` |
| `verify_status` | string | verify 后 | `pending` / `ok` / `failed` |
| `restart_status` | string | restart 后 | `pending` / `skipped` / `ok` / `failed` |
| `push_status` | string | push 后 | `pending` / `skipped` / `ok` / `failed` |
| `restart_log` | string/null | restart plan 后 | detached restart 日志路径 |
| `commands` | array[object] | 每次命令后 | 脱敏后的 cmd/cwd/exit_code/stdout_tail/stderr_tail |
| `errors` | array[object] | 错误发生时 | stage/code/message/next_steps |

Manifest 不得包含完整 `.env` 内容、OAuth token、API key、`auth.json` 内容或完整命令输出中的敏感字符串。

### 3.6 Rollback 详细步骤

Rollback 模式输入为 manifest，不重新解析 `--version`。默认需要交互确认；非交互环境必须传 `--yes` 才执行真实恢复。`--dry-run --rollback` 只打印计划。

恢复顺序：

1. 读取 manifest，校验 `schema_version == "1"`、`repo` 存在且仍为 git repo。
2. 打印恢复对象：repo、pre_head、post_head、backup_zip、stash_ref、dirty_files。
3. 校验当前 repo 是否存在未记录的新 dirty tree：
   - 若 dirty 且无 `--yes`，拒绝执行并要求人工确认；
   - 若 dirty 且有 `--yes`，先创建新的安全 stash `hermes-auto-upgrade-rollback-{timestamp}`，记录在 stdout，但不改写原 manifest。
4. 执行 `git merge --abort`（允许失败，不作为最终失败条件；用于清理可能残留的 merge 状态）。
5. 执行 `git reset --hard <pre_head>`。这是唯一允许的 hard reset 路径，前提是 manifest 中已有 pre_head，且执行前已打印确认。
6. 如 `backup_zip` 存在，按 zip 中路径覆盖恢复工作树文件；zip 解压必须做 zip-slip 校验，禁止成员路径逃逸 repo。
7. 如 `stash_ref` 存在，默认不自动 `stash apply`，而是输出命令：`git stash apply <stash_ref>`。只有后续实现显式加入 `--restore-stash` 且测试覆盖冲突处理时，才允许自动 apply。
8. 运行最小验证：`git -C <repo> status --short`、`/home/pascal/.local/bin/hermes --version`。若 CLI 仍失败，输出人工恢复命令和 manifest 路径。

Rollback 不执行 gateway restart、不 push origin。若需要 restart，输出人工命令。

### 3.7 Zip 备份 include/exclude 规则

备份目标是 Hermes repo 工作树，不是 Hermes profile 数据目录。zip 主要用于恢复 dirty/untracked 文件和非 git 文件；git 历史由 `pre_head` 恢复。

Include：

- 默认包含 repo 下所有 tracked/untracked 普通文件；
- 包含 `.install_method`，因为它是 install tree scoped 的安装方式锚点；
- 包含小型配置/元数据文件，如 `pyproject.toml`、lockfile、脚本、源码、测试。

Exclude：

| 规则 | 原因 |
|---|---|
| `.git/objects/**`, `.git/refs/**`, `.git/logs/**` | 大体积且由 git 恢复；避免 zip 过大 |
| `.git/index.lock`, `.git/*.lock` | 避免备份瞬态锁 |
| `venv/**`, `.venv/**` | 可由 install 重建，体积大 |
| `node_modules/**` | 可由 npm 重建，体积大 |
| `__pycache__/**`, `*.pyc`, `.pytest_cache/**`, `.ruff_cache/**`, `.mypy_cache/**` | 构建/缓存产物 |
| `web/node_modules/**`, `apps/**/node_modules/**`, `apps/**/dist/**` | 前端构建产物 |
| `.env`, `auth.json`, `*.pem`, `*.key`, `*.token` | 防止 secrets 进入 `/tmp` zip；Hermes repo 正常不应有这些文件，但仍防御 |
| `.DS_Store`, `Thumbs.db` | 无业务价值 |

zip 写入前必须对每个 candidate 做 `Path.resolve()`，确认仍在 repo 内；写入 zip 时使用相对路径。zip 解压回滚时必须拒绝绝对路径、`..` 路径和 symlink 成员。

### 3.8 安装命令最终选型与 fallback

最终选择：脚本直接执行 editable install，而不是调用 `hermes update`。

原因：

- `hermes update` 的 git 主流程围绕当前 origin branch，并可能在 diverged 时 reset 到 origin；与 A+ upstream merge 策略冲突。
- `hermes update` 包含 bundled skills sync、profile env backfill、config migration、curator notice 等副作用；本脚本的 scope 明确禁止修改 profile config/secrets，且不需要触发这些行为。
- 直接 editable install 更容易在 temp repo/mock 中测试，失败边界更清晰。

安装流程：

1. 删除 repo 内 `__pycache__` 与 `.pyc`，避免旧 bytecode 污染。
2. 优先查找 uv：
   - 若 `/home/pascal/workspace/hermes-agent/venv` 存在，设置 `VIRTUAL_ENV=<repo>/venv`；
   - 执行 `uv pip install -e '.[all]'`；
   - uv 不存在或失败时 fallback。
3. Fallback：执行 `python -m pip install -e '.[all]'`，其中 Python 优先为 `<repo>/venv/bin/python`，不存在时用当前 `sys.executable`。
4. 若 `.[all]` 失败，Implement 可选择进一步 fallback 到 `pip install -e .`，但必须在输出中标记 optional extras 未完整安装，并让 Verify/Review 判断是否接受。
5. 安装成功后执行：
   - `/home/pascal/.local/bin/hermes --version`；
   - `<target_python> -c "import hermes_cli; import hermes_cli.main"`；
   - 读取 `.install_method` 或等价调用，确认仍为 `git`。

安装失败处理：manifest 标记 `install_status=failed`，不得 restart，不得 push，提示 `--rollback <manifest>`。

### 3.9 Gateway detached restart 方案与安全边界

默认 `restart=True`。脚本不得从当前进程同步执行可能杀死自身的 restart，尤其当升级由 gateway `/update`、Kanban worker 或其他 gateway 子进程触发时。

实现方案：

```text
schedule_detached_restart:
  restart_log = /tmp/hermes-upgrade-restart-{timestamp}.log
  helper = bash -lc 'sleep 2; /home/pascal/.local/bin/hermes gateway restart >>LOG 2>&1'
  subprocess.Popen(helper, start_new_session=True, stdout=DEVNULL, stderr=DEVNULL)
  poll /home/pascal/.local/bin/hermes gateway status for up to 90s
```

要求：

- POSIX 使用 `start_new_session=True`（setsid 等价）脱离父进程组。
- stdout/stderr 写入 `restart_log`，主脚本只输出路径，不内联大量日志。
- 若 `hermes gateway status` 在 restart 前已不可用，允许记录 `pre_gateway_status=unknown`，但 restart 后必须重新检查。
- 若 poll 超时或 restart log 出现明显失败，manifest 标记 `restart_status=failed`，不 push origin。
- 若传 `--no-restart`，不启动 helper，manifest 标记 `restart_status=skipped`，输出手动命令：`/home/pascal/.local/bin/hermes gateway restart`。

安全边界：

- 不修改 systemd unit、launchd plist、gateway platform 配置。
- 不 kill 任意 PID，不调用 `pkill`。
- 不在脚本中实现 root/sudo systemctl 逻辑；交给 Hermes CLI 自身的 gateway restart 命令处理。

### 3.10 Dry-run 行为定义

`--dry-run` 是完整计划模式，不是 no-op help。

允许执行的只读命令：

- `git status`, `git rev-parse`, `git remote get-url`, `git branch --show-current`, `git merge-base`, `git rev-list`；
- 如本地已有 remote refs，允许解析 target；默认不执行网络 fetch。若 ref 仅远端可见，dry-run 输出“真实执行将 fetch 后解析”。
- `/home/pascal/.local/bin/hermes --version` 可作为只读探测。

禁止执行：

- 写 zip、写 manifest、git stash、git fetch、git merge、git reset、install、gateway restart、push origin。

输出必须包含：

1. repo/remotes/branch/install_method 当前状态；
2. dirty files 摘要；
3. target_ref 与可解析时的 target_sha；
4. 预计 merge_mode（若无法无 fetch 判定，标记 `unknown-before-fetch`）；
5. 将创建的 backup/manifest/restart_log 路径；
6. 将执行的安装、验证、restart、push 命令；
7. 明确声明“dry-run 未修改 repo、venv、gateway、origin”。

## 4. 实现计划

1. 新增 `scripts/upgrade/upgrade_hermes_agent.py` 骨架：argparse、dataclass、`main()`、exit code。
2. 实现 command wrapper 与 redaction，所有 git/pip/hermes 命令走统一入口。
3. 实现 repo inspect：git repo、remote、branch、install_method、dirty tree、HEAD、origin/main。
4. 实现 dry-run 输出，先不做任何写操作。
5. 实现 manifest 原子写与 zip backup include/exclude。
6. 实现 dirty stash、fetch、target ref resolve、git relation classify。
7. 实现 A+ protect + merge：ff-only、merge commit、conflict abort。
8. 实现 editable install 与 version/import/gateway 验证。
9. 实现 detached restart 与 post-restart health poll。
10. 实现 verify-success 后 push origin，以及 `--no-push` 跳过。
11. 实现 rollback dry-run 与真实 rollback。
12. 增加测试与 README（如 developer 判断需要）。

## 5. 测试策略

### 5.1 单元测试

建议新增 `tests/scripts/test_upgrade_hermes_agent.py`，覆盖：

| 编号 | 测试 | 断言 |
|---|---|---|
| UT-001 | `--help` | exit 0，核心参数存在 |
| UT-002 | 参数冲突 | `--rollback` 与升级参数冲突 exit 2 |
| UT-003 | manifest serialization | 必填字段完整，可 JSON round-trip |
| UT-004 | command wrapper | 记录 cmd/cwd/exit_code，失败不泄漏 secrets |
| UT-005 | zip exclude | `.env`、`venv`、`.git/objects`、`node_modules` 不入 zip |
| UT-006 | ref classify | already-up-to-date / ff-only / merge / unrelated 判定正确 |
| UT-007 | dry-run no mutation | mock 所有写函数未调用 |
| UT-008 | rollback plan | dry-run rollback 打印 reset/unzip/stash 计划但不执行 |

### 5.2 集成测试：temp git repo 矩阵

使用 `tmp_path` 创建 bare origin、bare upstream、local clone，不触碰真实 `/home/pascal/workspace/hermes-agent`。

| 编号 | 场景 | 操作 | 断言 |
|---|---|---|---|
| IT-001 | ff | local 落后 upstream，无本地 commit | `--repo tmp --no-restart --no-push` 后 HEAD == target |
| IT-002 | local commit + upstream commit | local 有 Pascal commit，upstream 有新 commit | 产生 merge commit，local commit 保留 |
| IT-003 | conflict | local/upstream 修改同一行 | merge abort，exit 非 0，manifest 保留 stash/backup |
| IT-004 | rollback | IT-002 后 rollback manifest | HEAD 回到 pre_head，zip 可解压 |
| IT-005 | invalid ref | `--version definitely-not-a-ref` | exit 非 0，无 stash/merge/install |
| IT-006 | dirty tree | tracked + untracked dirty | stash_ref 写入 manifest |
| IT-007 | install failure | mock install command 非 0 | 不 restart，不 push |
| IT-008 | push after verify | mock verify ok | push 在 verify/restart 后发生 |

### 5.3 手工/安全验证

- `python3 scripts/upgrade/upgrade_hermes_agent.py --dry-run --no-restart --no-push`：确认真实 Hermes repo 状态不变。
- `python3 -m py_compile scripts/upgrade/upgrade_hermes_agent.py`。
- `git status --short`：仅出现本任务允许文件与既有无关变更。
- 真实 restart/push 不在 Verify 阶段默认执行；需要 Pascal/主控明确确认。

## 6. 风险、降级与回滚

| 风险 | 应对 | 降级/回滚 |
|---|---|---|
| A+ merge 冲突 | conflict 时 `git merge --abort`，保留 stash/backup/manifest | 人工 resolve 后重跑，或 `--rollback` |
| zip 备份过大 | 排除 `.git/objects`、venv、node_modules、cache | 以 git `pre_head` 为主恢复锚点 |
| install 失败导致 CLI 不可用 | install 失败即停止，不 restart、不 push | `--rollback <manifest>`，再人工检查 venv |
| gateway restart 误杀当前进程 | detached helper + restart log + health poll | `--no-restart`，人工从另一个 shell restart |
| push origin 失败 | push 最后执行；失败不回滚本地成功升级 | 输出 `git -C <repo> push origin main` |
| dry-run 被误认为已升级 | 输出明确 no mutation 声明 | 无需回滚 |
| secrets 入日志/zip | exclude + redaction | 删除 zip/log，修复 redaction 测试 |

## 7. 交接给实现者

### 7.1 精确文件清单

Implement 阶段允许新增/修改：

- 新增：`scripts/upgrade/upgrade_hermes_agent.py`
- 可选新增：`scripts/upgrade/README.md`
- 建议新增：`tests/scripts/test_upgrade_hermes_agent.py`
- 仅当测试目录约定需要时可新增：`tests/scripts/__init__.py`

Implement 阶段不得修改：

- `/home/pascal/workspace/hermes-agent/**` 源码；
- `~/.hermes/profiles/*/config.yaml`、`~/.hermes/profiles/*/.env`、`~/.hermes/auth.json` 或任意 OAuth/API key 文件；
- Hermes gateway systemd unit、platform 配置；
- YQuant 数据管道、投研、交易、风控、报告业务代码；
- 已完成的 RFC/SPEC/Design，除非发现明确矛盾并回退 Principal。

### 7.2 必须遵守

- Python 标准库优先，新增第三方依赖必须退回 Principal/主控确认。
- 所有外部命令使用 `subprocess.run([...], shell=False)`。
- `--version` 作为 argv 元素传给 git，禁止拼接 shell 字符串。
- `git reset --hard` 只允许 rollback 模式或 conflict 清理路径，且必须有 manifest/pre_head。
- 验证失败不得 push origin。
- conflict 不自动解决。
- 测试不得真实 restart gateway，不得真实 push Pascal fork。

### 7.3 可自行判断

- 是否新增 README；若脚本 `--help` 足够清晰，可不新增。
- optional extras fallback 是否完整复制 Hermes 官方实现，或先实现 uv -> pip -> base install 的最小安全路径。
- gateway health poll timeout 可在 60-120 秒之间选择，默认建议 90 秒。

### 7.4 遇到以下情况退回 Principal

- 发现真实 Hermes venv 布局与本设计不一致，导致安装命令需要改变。
- 需要支持非 `main` 分支或 rebase/linear history。
- 需要修改 Hermes profile config/secrets/systemd unit。
- temp repo 无法模拟关键 git 场景，需要真实 repo  destructive 验证。

## 8. 验收标准映射

| SPEC 验收 | Design 覆盖 |
|---|---|
| Design 文件存在且非空 | 本文件 |
| ff 优先 + local commit A+ merge | 3.4 |
| zip + stash + manifest rollback | 3.5, 3.6, 3.7 |
| 安装命令最终选型 | 3.8 |
| detached restart | 3.9 |
| dry-run 行为 | 3.10 |
| temp git repo 测试矩阵 | 5.2 |
| Implement 文件清单和禁止事项 | 7.1 |
