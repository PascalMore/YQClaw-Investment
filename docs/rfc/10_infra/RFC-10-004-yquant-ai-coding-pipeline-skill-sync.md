# RFC-10-004：YQuant AI Coding Pipeline Skill 同步与冲突修复

## 元数据（Metadata）

| 项 | 值 |
|---|---|
| 状态 | 已采纳（Accepted） |
| 作者 | YQuant-Codex-Principal |
| 创建日期 | 2026-06-27 |
| 最后更新 | 2026-06-27 |
| 版本号 | V1.0 |
| 所属模块 | 10_infra（基础设施 / Hermes Kanban Pipeline） |
| 依赖 RFC | RFC-10-003-infra-architecture |
| 替代 RFC | 无 |
| 适配 AI 工具 | Hermes Agent, Hermes Kanban |
| 标签 | #infra #hermes #kanban #skill #pipeline |

## 版本历史（Changelog）

| 版本号 | 日期 | 更新内容 | 负责人 |
|---|---|---|---|
| V1.0 | 2026-06-27 | 初始创建，定义 AI Coding Pipeline skill canonical source、运行态副本保留策略与 worker 副本删除策略 | YQuant-Codex-Principal |

## 1. 执行摘要

`yquant-ai-coding-pipeline` skill 同时存在于项目源目录与 worker profile 运行态目录时，Hermes 会把同名 skill 判定为 Ambiguous 并导致 worker 启动崩溃。本 RFC 规定：项目源目录是唯一 canonical source，yquant 主 profile 保留一份运行态副本，4 个 worker profile 不保留同名副本，以消除 Skill name collision 并恢复 Kanban worker 正常启动。

## 2. 背景与动机

### 2.1 现状痛点

- 项目源目录 `/home/pascal/workspace/yquant-investment/skills/infra/ai-coding-pipeline/` 与 profile 运行态目录 `~/.hermes/profiles/*/skills/infra/yquant-ai-coding-pipeline/` 曾同时存在同名 skill。
- Worker 启动时 `HERMES_HOME` 指向目标 profile，同时通过 `workspace_path=/home/pascal/workspace/yquant-investment` 发现项目源目录，两个候选 skill 名称相同，触发 `Ambiguous skill name`。
- 运行态 yquant 主 profile 副本包含 2026-06-25 实跑后补的 P-1~P-4 教训与 `real-run-journal-2026-06-25.md`，但项目源目录才是 skill 自身声明的 canonical source。
- 若只删除所有 profile 副本，yquant 主 profile 在 cwd 不在项目目录时可能无法加载该 skill；若保留 worker 副本，则 worker 会继续 collision。

### 2.2 业务影响

- RFC/SPEC/Design/Implement/Verify/Review 流水线无法稳定派发；worker 在进入对话循环前崩溃，任务会被 dispatcher 标记 `crashed`，连续失败后进入 `blocked`。
- Orchestrator 看不到有效阶段产出，流水线自动依赖链失效，增加人工清理 Kanban DB 与重派任务成本。
- 运行态教训未回流到项目源，会造成下一次同步或迁移时再次复现同类事故。

### 2.3 触发原因

2026-06-25 RFC-03-006 流水线实跑中，Round 1 冒烟测试发现 worker 由于同名 skill collision 直接 exit 1。修复时临时删除了 4 个 worker profile 副本并保留 yquant 主 profile 副本，但源目录尚未吸收运行态独有教训与 journal，需要治理为长期规则。

## 3. 目标与非目标

### 3.1 必须目标（Must-Have）

- [ ] 项目源 `skills/infra/ai-coding-pipeline/SKILL.md` 吸收运行态独有 P-1~P-4 教训。
- [ ] 项目源 `references/real-run-journal-2026-06-25.md` 存在，内容与 yquant 主 profile 运行态 journal 一致。
- [ ] yquant 主 profile 保留 `skills/infra/yquant-ai-coding-pipeline/` 副本，以支持 cwd 不在项目目录的 orchestrator 场景。
- [ ] `yquantprincipal`、`yquantdeveloper`、`yquanttester`、`yquantreviewer` 4 个 worker profile 不保留同名 skill 副本。
- [ ] `find ~/.hermes/profiles -name "SKILL.md" -path "*yquant-ai-coding-pipeline*"` 只输出 yquant 主 profile 一行。
- [ ] Hermes 加载 `yquant-ai-coding-pipeline` 不再报 Ambiguous，worker 能进入对话循环。

### 3.2 非目标（Out of Scope）

- [ ] 不修改 Hermes core 的 skill discovery / collision 机制。
- [ ] 不修改 Hermes 升级脚本或安装器。
- [ ] 不修改任何 profile `config.yaml` 的模型、fallback、toolsets 配置。
- [ ] 不改变 AI Coding Pipeline 的核心阶段路由、角色分工和 Kanban 创建规则。
- [ ] 不迁移既有 Kanban DB 历史任务或清理历史 crashed run。

## 4. 整体设计

### 4.1 核心设计哲学

把项目源目录作为长期事实源，把 profile 副本降级为 yquant 主 profile 的运行态 cache；worker profile 一律通过共享 workspace 读取项目源，避免同名副本与源目录并存。

### 4.2 架构总览

```text
Canonical source:
  /home/pascal/workspace/yquant-investment/skills/infra/ai-coding-pipeline/
    SKILL.md
    references/*.md

Runtime cache kept:
  ~/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline/

Runtime copies forbidden:
  ~/.hermes/profiles/yquantprincipal/skills/infra/yquant-ai-coding-pipeline/
  ~/.hermes/profiles/yquantdeveloper/skills/infra/yquant-ai-coding-pipeline/
  ~/.hermes/profiles/yquanttester/skills/infra/yquant-ai-coding-pipeline/
  ~/.hermes/profiles/yquantreviewer/skills/infra/yquant-ai-coding-pipeline/

Worker discovery:
  HERMES_HOME=~/.hermes/profiles/<worker>/
  workspace_path=/home/pascal/workspace/yquant-investment
  -> load project source skill only
```

### 4.3 模块分工

- 项目源 skill：保存 pipeline 规则、P-1~P-4 教训、journal 引用，是长期维护入口。
- yquant 主 profile 副本：运行态 cache，用于 orchestrator 在非项目 cwd 下仍可加载 pipeline skill。
- worker profile：不保存该 skill 副本，仅通过 `workspace_path` 发现项目源。
- Kanban task body：继续显式传入 `workspace_kind="dir"` 与 `workspace_path="/home/pascal/workspace/yquant-investment"`。

## 5. 详细设计

### 5.1 业务流程（Flow）

1. 读取项目源 SKILL 与 yquant 主 profile 运行态 SKILL，确认差异。
2. 将运行态独有的 2026-06-25 教训合并回项目源：
   - P-1：Skill name collision 让 worker 永远进不了对话循环。
   - P-2：dispatcher 透明跑 fallback 链，任务名义 assignee 与实际模型可能不一致。
   - P-3：Kanban DB 任务 ID 不存在时不能用 `parents=[]` 强行串联。
   - P-4：`workspace_path` 必须用共享项目目录。
3. 将运行态 `references/real-run-journal-2026-06-25.md` 复制到项目源 references。
4. 更新源 SKILL 的同步策略：只同步到 yquant 主 profile，并删除 4 个 worker profile 副本。
5. 删除 worker profile 同名 skill 副本。
6. 运行验收命令，确认只剩 yquant 主 profile 一份副本且模型自检正常。
7. 通过 Hermes skill load / 测试 Kanban worker 验证不再 Ambiguous。

### 5.2 数据模型（Data Model）

本 RFC 不引入业务数据模型。治理对象是文件系统路径集合：

| 实体 | 类型 | 约束 | 说明 |
|---|---|---|---|
| canonical_skill_dir | path | 必须存在 | 项目源目录 |
| orchestrator_runtime_copy | path | 必须存在 | yquant 主 profile 运行态副本 |
| worker_runtime_copy | path | 必须不存在 | 4 个 worker profile 同名副本 |
| real_run_journal | markdown file | 必须存在且 md5 一致 | 2026-06-25 实跑复盘 |

### 5.3 接口契约（API Contract）

本 RFC 不新增程序 API。对运维与 worker 派发的操作契约如下：

```bash
# 验证副本数量
find ~/.hermes/profiles -name "SKILL.md" -path "*yquant-ai-coding-pipeline*"

# 同步项目源到 yquant 主 profile cache
mkdir -p /home/pascal/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline
cp -a /home/pascal/workspace/yquant-investment/skills/infra/ai-coding-pipeline/. \
  /home/pascal/.hermes/profiles/yquant/skills/infra/yquant-ai-coding-pipeline/

# 删除 worker profile 副本
for p in yquantprincipal yquantdeveloper yquanttester yquantreviewer; do
  rm -rf "/home/pascal/.hermes/profiles/$p/skills/infra/yquant-ai-coding-pipeline"
done
```

### 5.4 AI 模型设计

不涉及模型能力变更。P-2 仅要求在高价值任务中观察实际模型 fallback，避免误把 fallback 模型产物当作 primary 模型产物。

## 6. AI 实装规范

### 6.1 必须执行

- 先备份或记录项目源与运行态 SKILL 的 checksum，再合并内容。
- 只修改 `skills/infra/ai-coding-pipeline/` 与本 RFC/SPEC 相关文档。
- 删除 worker profile 副本时只删除 `skills/infra/yquant-ai-coding-pipeline/` 这一目录，不动其他 skill。
- 验证命令输出必须保存在完成 handoff 中。

### 6.2 先询问再执行

- 修改 Hermes core、升级脚本、profile `config.yaml` 或 gateway 配置。
- 删除 yquant 主 profile 运行态副本。
- 改变 pipeline 角色路由或阶段依赖链。

### 6.3 绝对禁止

- 删除 `~/.hermes/profiles/<profile>/skills/` 下无关目录。
- 把 secrets、provider token 或完整 profile config 写入文档。
- 为了通过验收而创建空的 worker profile skill 占位目录。

## 7. 风险与应对

| 风险 | 概率 | 影响 | 应对方案 | 降级策略 |
|---|---|---|---|---|
| 合并遗漏运行态教训 | 中 | 中 | diff 源 SKILL 与运行态 SKILL；验收 grep P-1~P-4 | 从 yquant 主 profile 副本重新提取 |
| 删除错 profile 目录 | 低 | 高 | rm 命令写死精确路径，只针对 4 个 worker profile 同名 skill | 从项目源重新同步目标 profile 或恢复备份 |
| yquant 主 profile cwd 不在项目目录时找不到 skill | 中 | 中 | 保留 yquant 主 profile runtime cache | 临时从项目源 cp 到 yquant profile |
| worker profile 仍发生 collision | 中 | 高 | find 验证只剩 yquant 主 profile 一行；测试 worker 启动 | 继续排查其他同名 skill 路径 |
| 运行态 cache 与项目源再次漂移 | 中 | 中 | 文档明确先改项目源，再同步 yquant 主 profile | 后续增加自动同步脚本（另 RFC） |

## 8. 备选方案

### 8.1 删除所有 profile 副本，只保留项目源

优点：最纯粹的单一事实源。缺点：yquant 主 profile 在 cwd 不在项目目录时可能无法加载 pipeline skill。最终不选用。

### 8.2 所有 profile 均保留副本，并改名避免 collision

优点：每个 worker 离线可加载。缺点：需要重命名 skill 或改 task skills，破坏现有调用习惯，并增加同步漂移风险。最终不选用。

### 8.3 修改 Hermes skill discovery 忽略重复

优点：从平台层解决 collision。缺点：涉及 Hermes core 行为变更，风险和范围超过本次修复。最终不选用。

### 8.4 只保留 yquant 主 profile 副本，worker profile 无副本

优点：兼顾 orchestrator 可用性与 worker 无 collision；最小变更；符合 2026-06-25 实跑验证。最终选用。

## 9. 验收标准

### 9.1 功能验收

- `find ~/.hermes/profiles -name "SKILL.md" -path "*yquant-ai-coding-pipeline*"` 只输出 yquant 主 profile 一行。
- 项目源 `SKILL.md` 包含 P-1、P-2、P-3、P-4 四条 Pitfalls。
- 项目源 `references/real-run-journal-2026-06-25.md` 存在且与 yquant 主 profile 运行态 journal md5 一致。
- Hermes 加载该 skill 不再输出 `Ambiguous skill name`。
- `python3 skills/common/utils/print_agent_models.py` 正常输出。
- 一个测试 Kanban worker 能进入对话循环并完成 smoke task。

### 9.2 非功能验收

- 不修改 profile 模型/fallback 配置。
- 不改变 pipeline 核心路由规则。
- 不引入新依赖。
- 不写入 secrets 或 token。

## 10. 落地计划

### 10.1 阶段划分

1. RFC/SPEC：产出本 RFC 与对应 SPEC，定义文件、命令、验收契约。
2. Design：定义精确操作顺序、回滚步骤、验证脚本与 handoff。
3. Implement：合并 SKILL，复制 journal，同步 yquant cache，删除 worker 副本。
4. Verify：运行 find、md5、skill load、model script、worker smoke task。
5. Review：审查 diff、验证输出与 RFC/SPEC/Design 一致性。

### 10.2 任务清单

| 阶段 | 负责人 | 交付物 |
|---|---|---|
| RFC/SPEC | yquantprincipal | RFC-10-004、SPEC-10-004 |
| Design | yquantprincipal | DESIGN-10-004 |
| Implement | yquantdeveloper | SKILL/journal/profile 副本修复 |
| Verify | yquanttester | 验证报告 |
| Review | yquantreviewer | 独立 review 结论 |

## 11. 开放问题

- 是否需要后续新增一个自动同步脚本，避免项目源与 yquant 主 profile cache 再次漂移？本 RFC 不处理。
- Hermes core 是否应支持同名 skill 的优先级策略或去重策略？本 RFC 不处理。

## 12. 参考资料

- `skills/infra/ai-coding-pipeline/SKILL.md`
- `skills/infra/ai-coding-pipeline/references/real-run-journal-2026-06-25.md`
- `skills/infra/ai-coding-pipeline/references/document-layers.md`
- `skills/infra/ai-coding-pipeline/references/spec-from-rfc.md`
- Hermes Kanban worker lifecycle guidance
