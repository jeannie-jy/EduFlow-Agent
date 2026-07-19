# 贡献指南

## 分工

| 角色 | 负责人 | 主要产出 |
|------|--------|---------|
| 架构 | 仲嘉辉 | 系统设计、技术选型、任务拆分 |
| 需求 | 屠育玮 | 需求文档、用户故事、前端设计文档 |
| 前端 | 崔杰 | Web 交互界面、可视化渲染 |
| 后端 | 王婧瑜 | Agent 实现、API、数据库 |

模式：**专人主责 + 全员测评**。每人对自己的模块负责，代码提交前另一人交叉测试。

## 分支策略

```
main ───────●────────────── (稳定版本)
            ├── codex/xxx   (Codex 开发分支)
            ├── feature/xxx (功能分支)
            └── docs/xxx    (文档分支)
```

- `main`：稳定集成基线，通过 Pull Request 合入
- `codex/<任务名>`：Codex 创建的功能或重构分支
- `feature/<模块名>`：人工创建的功能分支
- `docs/<主题>`：仅修改文档的分支

## 日常流程

1. 更新远端信息，从 `main` 拉出任务分支
2. 开发 → 自测 → 提交 PR 到 `main`
3. 另一人交叉测试通过后合并
4. 合并后删除远端任务分支

## Commit 规范

使用 Conventional Commits：

```
<类型>: <描述>

类型：feat / fix / docs / refactor / chore
示例：
  feat(frontend): 实现推演参数编辑
  fix(frontend): 修复渲染帧状态不同步
  docs(frontend): 更新前端运行指南
```

## 代码风格

- **Python**：ruff 格式化，mypy 类型检查
- **前端**：Oxlint、TypeScript、Vitest、Vite 生产构建
- 风格配置随代码放在各自模块目录下，不在此赘述

前端提交前运行：

```bash
npm --prefix web run verify
npm --prefix web run lint
```

## 文档约定

- 需求文档、设计文档统一放在 `docs/` 目录
- 架构或接口变更时，同步更新设计文档
- 文档格式：Markdown
- 英文文档必须在同目录提供 `.zh-CN.md` 中文版并互相链接
- 前端运行和架构变更同步更新 `web/README.md`、`web/README.zh-CN.md` 与 `docs/前端架构与开发指南.md`
