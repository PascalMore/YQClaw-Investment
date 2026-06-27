# SPEC-10-004: YQuant AI Coding Pipeline Skill 同步与冲突修复

## 元数据

| 项 | 值 |
|---|---|
| 状态 | Accepted |
| 作者 | YQuant-Codex-Principal |
| 创建日期 | 2026-06-27 |
| 最后更新 | 2026-06-27 |
| 来源 RFC | RFC-10-004-yquant-ai-coding-pipeline-skill-sync |
| 目标模块 | infra / Hermes Kanban Pipeline |
| 适配 Agent | YQuant-Developer-Engineer, YQuant-Test-Engineer, YQuant-Reviewer-Principal |
| 关联 RFC | RFC-10-003-infra-architecture |
| 关联 Design | DESIGN-10-004-yquant-ai-coding-pipeline-skill-sync（待创建） |

## 1. 需求摘要

本 SPEC 将 RFC-10-004 的治理决策落为可执行文件契约、操作契约与验收矩阵。实现者必须把 yquant 主 profile 运行态副本独有的 P-1~P-4 教训与 real-run journal 合并回项目源目录，并删除 4 个 worker profile 的同名 skill 副本；同时保留并更新 yquant 主 profile 副本作为 orchestrator runtime cache。

核心交付物：

1. 项目源 `skills/infra/ai-coding-pipeline/SKILL.md` 包含 P-1~P-4 与正确同步策略；
2. 项目源 `skills/infra/ai-coding-pipeline/references/real-run-journal-2026-06-25.md` 与 yquant 主 profile 运行态 journal md5 一致；
3. `~/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline/` 存在；
4. `~/.hermes/profiles/{yquantprincipal,yquantdeveloper,yquanttester,yquantreviewer}/skills/infra/yquant-ai-coding-pipeline/` 不存在；
5. 验证命令证明不再发生 `Ambiguous skill name`，worker 能进入对话循环。

## 2. 范围

### 2.1 In Scope

- [ ] 修改项目源 `skills/infra/ai-coding-pipeline/SKILL.md`。
- [ ] 新增项目源 `skills/infra/ai-coding-pipeline/references/real-run-journal-2026-06-25.md`。
- [ ] 同步项目源到 yquant 主 profile 运行态副本。
- [ ] 删除 4 个 worker profile 的同名 skill 副本。
- [ ] 运行并记录 md5、find、skill load、模型配置脚本与 Kanban worker smoke 验证。
- [ ] 产出 RFC/SPEC/Design 三层独立文档。

### 2.2 Out of Scope

- [ ] 不修改 Hermes core、skill discovery 或 collision 解析逻辑。
- [ ] 不修改 Hermes 升级脚本、安装脚本或 gateway 配置。
- [ ] 不修改 `~/.hermes/profiles/*/config.yaml` 的模型、fallback、toolset 配置。
- [ ] 不改变 pipeline 的阶段路由、assignee profile、依赖链规则。
- [ ] 不清理历史 Kanban crashed task/run；如需清理，另开任务。
- [ ] 不删除 yquant 主 profile 运行态副本。

## 3. 功能规格

| 编号 | 行为 | 输入 | 输出 | 错误/边界 |
|---|---|---|---|---|
| F-001 | 差异识别 | 项目源 SKILL 与 yquant runtime SKILL | md5 与 diff 摘要 | 如果 yquant runtime 不存在，阻塞并要求人工确认恢复来源 |
| F-002 | P-1~P-4 合并 | runtime SKILL 独有 Pitfalls | 项目源 SKILL 包含 `### P-1` 至 `### P-4` | 不得覆盖核心路由规则 |
| F-003 | 同步策略修正 | 项目源 SKILL `源目录与运行态同步` 章节 | 只同步 yquant，删除 4 个 worker 副本的命令 | 不得保留“同步到所有 profile”的旧命令作为推荐路径 |
| F-004 | journal 回流 | runtime `references/real-run-journal-2026-06-25.md` | 项目源同名文件 | md5 必须一致 |
| F-005 | yquant cache 保留 | 项目源 skill 目录 | yquant 主 profile skill 副本存在且同步到最新项目源 | 不得删除 yquant 主 profile 副本 |
| F-006 | worker 副本删除 | 4 个 worker profile skill 路径 | 目标路径不存在 | 只允许删除精确同名 skill 目录 |
| F-007 | Ambiguous 消除验证 | `find ~/.hermes/profiles ...` | 只输出 yquant 主 profile 一行 | 若输出多于一行，必须继续定位残留副本 |
| F-008 | Hermes skill load 验证 | `yquant-ai-coding-pipeline` skill 名称 | 加载成功且无 Ambiguous | 若命令不支持直接 load，以 worker smoke task 作为替代验证 |
| F-009 | worker smoke 验证 | 测试 Kanban task | worker 进入对话循环并完成 | 若 gateway 未运行，记录为环境阻塞，不伪造结果 |

## 4. 数据与接口契约

### 4.1 路径契约

| 名称 | 路径 | 状态要求 | 说明 |
|---|---|---|---|
| canonical_skill_dir | `/home/pascal/workspace/yquant-investment/skills/infra/ai-coding-pipeline/` | 必须存在 | 唯一长期维护源 |
| canonical_skill_md | `skills/infra/ai-coding-pipeline/SKILL.md` | 必须包含 P-1~P-4 | 项目源 SKILL |
| canonical_journal | `skills/infra/ai-coding-pipeline/references/real-run-journal-2026-06-25.md` | 必须存在 | 实跑 journal |
| yquant_runtime_skill_dir | `/home/pascal/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline/` | 必须存在 | 主 profile runtime cache |
| worker_principal_copy | `/home/pascal/.hermes/profiles/yquantprincipal/skills/infra/yquant-ai-coding-pipeline/` | 必须不存在 | 避免 collision |
| worker_developer_copy | `/home/pascal/.hermes/profiles/yquantdeveloper/skills/infra/yquant-ai-coding-pipeline/` | 必须不存在 | 避免 collision |
| worker_tester_copy | `/home/pascal/.hermes/profiles/yquanttester/skills/infra/yquant-ai-coding-pipeline/` | 必须不存在 | 避免 collision |
| worker_reviewer_copy | `/home/pascal/.hermes/profiles/yquantreviewer/skills/infra/yquant-ai-coding-pipeline/` | 必须不存在 | 避免 collision |

### 4.2 输入契约：必须合并的运行态独有内容

| 输入内容 | 来源 | 项目源落点 | 验证方式 |
|---|---|---|---|
| delegate_task 不创建 Kanban DB task 的历史教训 | yquant runtime SKILL 执行模型段 | `## Hermes 执行模型` bullet | grep `delegate_task.*不在 Kanban DB 创建 task 记录` |
| SPEC 文件清单需精确到目录层级 | yquant runtime SKILL 执行模型段 | `## Hermes 执行模型` bullet | grep `SPEC §3 文件清单必须精确到目录层级` |
| worker profile 不保留副本策略 | yquant runtime SKILL 同步段 | `### 源目录与运行态同步` | grep `不要把 worker profile` |
| P-1 Skill name collision | yquant runtime SKILL Pitfalls | `## Pitfalls` | grep `### P-1` |
| P-2 fallback 链透明 | yquant runtime SKILL Pitfalls | `## Pitfalls` | grep `### P-2` |
| P-3 Kanban DB task id | yquant runtime SKILL Pitfalls | `## Pitfalls` | grep `### P-3` |
| P-4 workspace_path | yquant runtime SKILL Pitfalls | `## Pitfalls` | grep `### P-4` |
| real-run-journal-2026-06-25.md | yquant runtime references | 项目源 references | md5sum 一致 |

### 4.3 输出契约：合并后项目源 SKILL 必须包含的章节

- `## Hermes 执行模型`
- `### Hermes Profile 路由`
- `### 源目录与运行态同步`
- `### Kanban 创建规则`
- `## 触发入口`
- `## 编排顺序`
- `### 三层文档强制规则`
- `## 强制角色拆分`
- `## 运行态自检`
- `## Pitfalls（2026-06-25 实跑后补）`
- `## 参考资料`

### 4.4 操作契约：允许执行的命令

```bash
# 1. 合并前证据
md5sum \
  /home/pascal/workspace/yquant-investment/skills/infra/ai-coding-pipeline/SKILL.md \
  /home/pascal/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline/SKILL.md

diff -u \
  /home/pascal/workspace/yquant-investment/skills/infra/ai-coding-pipeline/SKILL.md \
  /home/pascal/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline/SKILL.md

# 2. journal 回流
cp /home/pascal/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline/references/real-run-journal-2026-06-25.md \
  /home/pascal/workspace/yquant-investment/skills/infra/ai-coding-pipeline/references/real-run-journal-2026-06-25.md

# 3. yquant runtime cache 同步
mkdir -p /home/pascal/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline
cp -a /home/pascal/workspace/yquant-investment/skills/infra/ai-coding-pipeline/. \
  /home/pascal/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline/

# 4. worker 副本删除
for p in yquantprincipal yquantdeveloper yquanttester yquantreviewer; do
  rm -rf "/home/pascal/.hermes/profiles/$p/skills/infra/yquant-ai-coding-pipeline"
done

# 5. 副本数量验证
find ~/.hermes/profiles -name "SKILL.md" -path "*yquant-ai-coding-pipeline*" -print
```

## 5. 配置契约

本 SPEC 不新增或修改 `config.yaml` 字段。

| 配置项 | 行为 |
|---|---|
| provider/model/fallback | 不修改 |
| gateway / dispatcher | 不修改 |
| profile toolsets | 不修改 |
| skill path | 仅通过文件系统目录存在性治理，不写入 config |

## 6. 行为契约（RFC 决策 → 落地点映射）

| RFC 决策 | SPEC 落地点 | 章节 |
|---|---|---|
| 项目源目录是唯一 canonical source | `canonical_skill_dir` 路径契约；SKILL 同步策略 | 4.1, 4.4 |
| yquant 主 profile 保留运行态副本 | yquant_runtime_skill_dir 必须存在；同步命令只复制到 yquant | 4.1, 4.4 |
| 4 个 worker profile 删除同名副本 | worker_*_copy 必须不存在；rm 精确路径 | 4.1, 4.4 |
| 运行态独有 P-1~P-4 必须回流项目源 | 输入契约列明 7 项 grep 验证 | 4.2 |
| journal 必须进入项目源 references | canonical_journal md5 一致 | 4.1, 4.2 |
| 不修改 Hermes core / config / 路由规则 | Out of Scope 与配置契约 | 2.2, 5 |
| worker smoke task 作为端到端证明 | 验收 A-006 | 9 |

## 7. 错误契约

| 错误情形 | 处理方式 | 是否阻塞 |
|---|---|---|
| yquant runtime SKILL 不存在 | 不猜测内容；阻塞并要求人工确认恢复来源 | 是 |
| runtime journal 不存在 | 不创建空 journal；阻塞并要求人工确认是否跳过或从历史恢复 | 是 |
| find 输出多于 1 行 | 定位残留 worker 副本并删除；重新运行 find | 是 |
| find 输出 0 行 | 说明 yquant 主 profile cache 丢失；重新同步 yquant cache | 是 |
| skill load 命令不可用 | 用 Kanban worker smoke task 替代 | 否，需记录替代验证 |
| gateway 未运行导致 smoke task 不调度 | 记录环境阻塞并要求 operator 启动 gateway | 是 |
| model script 因外部依赖失败 | 记录真实错误，不伪造通过 | 是 |

## 8. 文件改动清单

### 8.1 新增

- `docs/rfc/10_infra/RFC-10-004-yquant-ai-coding-pipeline-skill-sync.md`
- `docs/spec/10_infra/SPEC-10-004-yquant-ai-coding-pipeline-skill-sync.md`
- `docs/design/10_infra/DESIGN-10-004-yquant-ai-coding-pipeline-skill-sync.md`（Design 阶段创建）
- `skills/infra/ai-coding-pipeline/references/real-run-journal-2026-06-25.md`

### 8.2 修改

- `skills/infra/ai-coding-pipeline/SKILL.md`
- `/home/pascal/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline/`（从项目源同步，运行态 cache）

### 8.3 删除

- `/home/pascal/.hermes/profiles/yquantprincipal/skills/infra/yquant-ai-coding-pipeline/`
- `/home/pascal/.hermes/profiles/yquantdeveloper/skills/infra/yquant-ai-coding-pipeline/`
- `/home/pascal/.hermes/profiles/yquanttester/skills/infra/yquant-ai-coding-pipeline/`
- `/home/pascal/.hermes/profiles/yquantreviewer/skills/infra/yquant-ai-coding-pipeline/`

### 8.4 不改动（明确列出）

- `~/.hermes/profiles/*/config.yaml`
- Hermes core / CLI / gateway 源码
- `skills/infra/ai-coding-pipeline/references/pipeline.md`
- `skills/infra/ai-coding-pipeline/references/document-layers.md`
- `skills/infra/ai-coding-pipeline/references/agent-handoff.md`
- `skills/infra/ai-coding-pipeline/references/hermes-kanban-orchestration.md`
- `skills/infra/ai-coding-pipeline/references/spec-from-rfc.md`
- 所有 data / research / portfolio / report 业务模块代码

## 9. 测试要求

| 编号 | 类型 | 命令 / 方法 | 断言 |
|---|---|---|---|
| UT-001 | 文档检查 | `grep -n "### P-[1-4]" skills/infra/ai-coding-pipeline/SKILL.md` | 输出 P-1~P-4 四行 |
| UT-002 | journal 一致性 | `md5sum <runtime_journal> <canonical_journal>` | 两个 md5 相同 |
| UT-003 | profile 副本检查 | `find ~/.hermes/profiles -name "SKILL.md" -path "*yquant-ai-coding-pipeline*"` | 只输出 yquant 主 profile 一行 |
| UT-004 | 禁改检查 | `git diff -- ~/.hermes/profiles/*/config.yaml` 或确认无 config diff | 无 config 修改 |
| IT-001 | 模型脚本 | `python3 skills/common/utils/print_agent_models.py` | exit code 0，正常输出 profile 模型信息 |
| IT-002 | skill load | Hermes skill load / chat 加载该 skill | stderr/stdout 不含 `Ambiguous skill name` |
| IT-003 | Kanban worker smoke | 创建一个只回答 `2` 的 yquantprincipal smoke task | task done，summary 表示进入对话循环 |
| REG-001 | git 范围 | `git status --short` | 只包含本 SPEC/RFC/Design 与 skill/journal 相关变更；既有无关变更不被触碰 |

## 10. 验收标准

| 编号 | 验收项 | 验证方式 | 对应测试 |
|---|---|---|---|
| A-001 | find 只输出 yquant 主 profile 一份 | `find ~/.hermes/profiles ...` | UT-003 |
| A-002 | 项目源 SKILL 包含 P-1~P-4 | grep `### P-1` 至 `### P-4` | UT-001 |
| A-003 | 项目源 journal 存在且与 runtime 一致 | md5sum | UT-002 |
| A-004 | Hermes 加载 skill 不再 Ambiguous | skill load 或 worker smoke 日志 | IT-002 / IT-003 |
| A-005 | model config 自检正常 | `python3 skills/common/utils/print_agent_models.py` | IT-001 |
| A-006 | worker 正常进入对话循环 | smoke task done | IT-003 |
| A-007 | 未修改 profile config 或 Hermes core | git/status/路径检查 | UT-004 / REG-001 |

## 11. 实现约束

- 删除命令必须是精确目录：`.../skills/infra/yquant-ai-coding-pipeline`，不得使用宽泛 glob 删除整个 `skills/infra`。
- 同步方向必须是项目源 → yquant 主 profile，不得用运行态副本反向覆盖项目源（除人工 diff 后挑选内容）。
- 文档中不得包含 API key、OAuth token、完整 secrets 环境变量值。
- 若验收命令失败，必须报告真实失败，不得写“已验证通过”的占位文本。
- Design 阶段必须补充回滚策略：可从项目源重新同步 yquant cache；worker 副本删除无需恢复，除非 Hermes discovery 机制改变。

## 12. 风险与未解决问题

| 风险 | 缓解 | 归属 |
|---|---|---|
| 项目源与 yquant cache 再次漂移 | 后续可新增同步脚本或 CI 检查 | 后续 RFC |
| Hermes 未来 discovery 机制变化 | 保留 RFC/SPEC 记录，必要时重新评估副本策略 | Principal |
| smoke task 依赖 gateway 与模型可用性 | 验证时区分 skill collision 与外部模型/gateway 故障 | Tester |

未解决问题：

- 是否需要把“只同步 yquant cache、删除 worker copy”的逻辑固化到 Hermes profile bootstrap 或项目脚本中？本 SPEC 不处理。
- 是否需要在 Hermes upstream 支持同名 skill 优先级或 shadowing 规则？本 SPEC 不处理。
