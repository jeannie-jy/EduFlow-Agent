# 贡献指南

## 分工

| 角色 | 负责人 | 主要产出 |
|------|--------|---------|
| 架构 | [@jiahuizhong205](https://github.com/jiahuizhong205) | 系统设计、技术选型、任务拆分 |
| 需求 | [@fishtailtu](https://github.com/fishtailtu) | 需求文档、用户故事、前端设计文档 |
| 前端 | [@smwy-cj](https://github.com/smwy-cj) | Web 交互界面、可视化渲染 |
| 后端 | [@jeannie-jy](https://github.com/jeannie-jy) | Agent 实现、API、数据库 |

模式：**专人主责 + 全员测评**。每人对自己的模块负责，代码提交前另一人交叉测试。

## 分支策略

```
main ───────●────────────── (稳定版本)
            └── develop ─── (集成分支)
                  ├── feature/xxx  (功能模块分支)
                  └── docs/xxx     (文档分支)
```

- `main`：只从 `develop` 合并，保持可运行
- `develop`：日常集成
- `feature/<模块名>`：按功能模块分，完成后合并回 `develop`

## 日常流程

1. 从 `develop` 拉出 feature 分支
2. 开发 → 自测 → 提交 PR 到 `develop`
3. 另一人交叉测试通过后合并
4. 阶段性从 `develop` 合并到 `main`

## Commit 规范

简洁即可：

```
<类型>: <描述>

类型：feat / fix / docs / refactor / chore
示例：
  feat: 实现知识库语义检索
  fix: 修复渲染帧时间戳偏移
  docs: 更新需求文档用户故事
```

## 代码风格

- **Python**：ruff 格式化，mypy 类型检查
- **前端**：ESLint + Prettier
- 风格配置随代码放在各自模块目录下，不在此赘述

## 文档约定

- 需求文档、设计文档统一放在 `docs/` 目录
- 架构或接口变更时，同步更新设计文档
- 文档格式：Markdown
