# Tests Directory

顶层测试目录，用于跨模块的集成测试和端到端测试。

## 结构

```
tests/
├── unit/           # 单元测试
├── integration/    # 集成测试
└── e2e/           # 端到端测试
```

## 规范

- 使用 pytest 作为测试框架
- 测试文件命名：`test_*.py`
- 所有测试须可通过 `pytest` 命令执行
- CI/CD 流水线会自动运行测试

## 状态

🚧 建设中
