# Design 文档层

`docs/design` 用于沉淀实现设计、详细设计、原型/UI 设计和实现计划。它承接 `docs/spec`，面向代码实现。

## 使用规则

- 设计文档必须引用来源 RFC/SPEC。
- 设计文档需要说明改哪些文件、为什么这样改、如何验证。
- 涉及 UI 时，必须包含主要状态、交互、错误态和空态。
- 涉及数据/交易/风控时，必须包含降级与回滚说明。
- Design 目录结构应与 `docs/rfc` / `docs/spec` 的模块目录保持一致，按模块编号归档。

## 目录结构

```text
docs/design/
  README.md
  DESIGN-00-000-design-template.md
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

所有模块目录应预先创建；空目录使用 `.gitkeep` 保留。无法归类的 Design 先放入 `99_other/`，后续再迁移到明确模块。

## 推荐命名

```text
DESIGN-{模块编号}-{序号}-{short-name}.md
```

示例：

```text
DESIGN-05-001-stock-pool-crud.md
```
