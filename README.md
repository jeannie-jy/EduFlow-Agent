# EduFlow-Agent

> **面向计算机科学教育的 Agent 教学推演系统**
>
> 以学生为核心用户，将抽象 CS 概念转化为可交互的逐帧推演序列，帮助直观理解算法与数据结构。支持导出为教学视频。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)

---

## 项目简介

EduFlow-Agent 是一个 AI 驱动的教学推演系统。用户通过自然语言输入想学习的 CS 概念（如"AVL 树的插入过程"），系统自主规划教学步骤，生成可交互的可视化推演，并可按需导出为视频。

**当前阶段：** 需求分析与架构设计。MVP 聚焦学生用户的知识理解场景。

## 核心特点

- **自主规划**：Agent 自动将 CS 知识点拆解为教学步骤
- **交互式推演**：不是被动看视频，而是可暂停、可回退、可修改参数的实时推演
- **视频导出**：按需将推演序列导出为视频文件（辅助功能）
- **自然语言交互**：输入想学什么，系统自主规划如何教

## 技术概览（初步）

| 层次 | 技术 | 说明 |
|------|------|------|
| **大模型** | DeepSeek-Coder-V3 (主) / Qwen2.5-Coder-7B (轻量) | API 调用（兼容 OpenAI 接口），复杂场景可切换 Claude Sonnet 5 / GPT-4o |
| **嵌入模型** | text-embedding-3-small (1536维) | API 调用，向量检索 |
| **Agent 框架** | Python（框架待定） | 多 Agent 架构方案设计中 |
| **前端** | Web（框架待定） | 交互式可视化渲染 |
| **数据库** | PostgreSQL + pgvector + Redis | 向量检索 + 缓存 |
| **视频导出** | Manim CE + FFmpeg | 可选辅助功能 |

## 快速开始（开发中）

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/EduFlow-Agent.git
cd EduFlow-Agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key

# 3. 启动基础设施（数据库）
docker compose up -d
```

## 文档索引

| 文档 | 说明 | 状态 |
|------|------|------|
| [需求文档](docs/requirements.md) | 用户故事、用例、功能边界 | 🔜 撰写中 |
| [设计文档](docs/智能教学推演系统设计文档.md) | 完整技术方案（基于需求文档推导） | 📝 v1.0 |
| [术语表](docs/GLOSSARY.md) | 中英术语对照 | ✅ |
| [贡献指南](CONTRIBUTING.md) | 分支策略与协作规范 | ✅ |

## 团队与分工

| 角色 | 负责人 | 职责 |
|------|--------|------|
| **架构** | 待定 | 系统架构设计、技术选型、多 Agent 方案 |
| **需求** | 屠育玮 | 需求分析、用户故事、市场调研 |
| **前端** | 待定 | Web 交互界面、可视化渲染 |
| **后端** | 待定 | Agent 实现、API 服务、数据库 |

## 开发流程

```
需求分析 → 架构设计 → 开发（前端+后端并行）→ 测试
```

Git 分支策略：`main` → `develop` → 按功能模块分分支。

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[Apache 2.0](LICENSE)
