## 变更描述

<!-- 一句话概括这个 PR 做了什么 -->

## 变更类型

- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 重构 (refactor)
- [ ] 文档 (docs)
- [ ] 性能优化 (perf)
- [ ] 测试 (test)
- [ ] 构建/工具 (chore)

## 关联

<!-- 关联的 Issue 编号或设计文档章节 -->

- Issue: #
- 设计文档: §

## 模块影响

<!-- 勾选受影响的模块 -->

- [ ] 后端 `agent/`（FastAPI + LangGraph）
- [ ] 前端 `web/`（React + TypeScript）
- [ ] 数据库 / 迁移（Alembic）
- [ ] Docker 部署 / 启动脚本
- [ ] 文档

## 接口变更检查

<!-- 如果此 PR 修改了前后端接口或 DSL 契约，必须完成以下检查 -->

- [ ] 无接口变更
- [ ] 有接口变更 → 已同步更新 `docs/开发任务与接口规范.md`（API 契约 / DSL Schema 速查）

## 测试

<!-- 说明测试情况 -->

- [ ] 后端：`cd agent && python -m pytest` 全绿
- [ ] 前端：`cd web && npm run verify`（typecheck + 测试 + 构建）全绿
- [ ] 手动测试步骤：

## Checklist

- [ ] 代码通过 Lint（后端 ruff / 前端 oxlint）
- [ ] 类型检查通过（前端 `npm run typecheck`，即 `tsc -b`）
- [ ] 代码风格一致（中文注释、`fix:/feat:/refactor:` 提交前缀）
- [ ] 无硬编码敏感信息（密钥、密码等）
- [ ] 设计文档已同步更新（如涉及架构变更）

## 截图/演示

<!-- 如涉及 UI 变更，提供截图或 GIF -->
