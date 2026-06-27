# SPEC 文档层

`docs/spec` 用于沉淀从 `docs/rfc` 派生出的工程规格。RFC 说明业务目标和架构约束，SPEC 说明可执行、可测试的行为。

## 使用规则

- 当 `docs/rfc` 中的需求进入实装阶段时，先创建对应 SPEC。
- SPEC 必须引用来源 RFC。
- Developer 和 Test Engineer 以 SPEC 为直接依据。
- RFC 发生业务语义变化时，同步更新对应 SPEC。
- SPEC 目录结构应与 `docs/rfc` 的模块目录保持一致，按模块编号归档。

## 目录结构

```text
docs/spec/
  README.md
  SPEC-00-000-spec-template.md
  00_project_overview/
  01_app/
  02_common/
  03_data/
  04_knowledge/
  05_portfolio/
  06_strategy/
  07_trading/
  08_research/
  09_reports/
  10_infra/
  99_other/
```

所有模块目录应预先创建；空目录使用 `.gitkeep` 保留。无法归类的 SPEC 先放入 `99_other/`，后续再迁移到明确模块。

## 推荐命名

```text
SPEC-{模块编号}-{序号}-{short-name}.md
```

示例：

```text
SPEC-05-001-stock-pool-crud.md
```
