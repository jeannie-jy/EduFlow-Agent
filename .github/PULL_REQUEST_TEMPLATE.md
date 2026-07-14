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

- [ ] Python Agent Runtime
- [ ] Java Spring Boot
- [ ] Next.js 前端
- [ ] MCP Server
- [ ] Manim 视频渲染
- [ ] Docker 部署
- [ ] 数据库
- [ ] 文档

## 接口变更检查

<!-- 如果此 PR 修改了组件间接口，必须完成以下检查 -->

- [ ] 无接口变更
- [ ] 有接口变更 → 已同步更新 `docs/INTERFACES.md`
- [ ] 有 gRPC proto 变更 → 已同步更新 `.proto` 文件和生成代码
- [ ] 有 MCP Tool 变更 → 已同步更新 Tool Schema 定义

## 测试

<!-- 说明测试情况 -->

- [ ] 新增测试覆盖
- [ ] 已有测试全部通过
- [ ] Golden Dataset 场景测试通过
- [ ] 手动测试步骤：

## Checklist

- [ ] 代码通过 Lint (`ruff check` / `./mvnw checkstyle:check` / `pnpm lint`)
- [ ] 类型检查通过 (`mypy` / `pnpm type-check`)
- [ ] 代码风格一致
- [ ] 无硬编码敏感信息（密钥、密码等）
- [ ] Commit 符合 Conventional Commits 规范
- [ ] 设计文档已同步更新（如涉及架构变更）

## 截图/演示

<!-- 如涉及 UI 变更，提供截图或 GIF -->
