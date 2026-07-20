# EduFlow-Agent 自动修复实施计划

> 基于 [文档验证报告](../文档验证报告.md) 的 70 项检查结果，按优先级分阶段实施。

---

## 修复总览

| 优先级 | 问题数 | 涉及模块 | 预期工作量 |
|--------|:------:|---------|:----------:|
| 🔴 P0 高优 | 4 | 后端错误处理、前端动画/渲染/状态机 | 核心功能阻塞 |
| 🟡 P1 中优 | 6 | 知识库、Checkpointer、前端页面完善 | 功能闭环 |
| 🟢 P2 低优 | 4 | Agent 扩展、插件机制、版本对比 | 远期完善 |

---

## 🔴 Phase 1: 高优先级修复（核心功能）

### 1.1 全局错误响应格式统一

**问题：** 仅 deps.py 对 422 做了包装，其他错误使用 FastAPI 默认 `{"detail": "..."}` 格式，不符合接口规范 `{"error": {"code": "...", "message": "...", "details": {}}}`。

**实施：**
- 新建 `agent/api/error_handlers.py` — 全局异常处理程序
- 注册 `HTTPException`、`RequestValidationError`、通用 `Exception` 处理器
- 统一返回 `{"error": {"code": "ERROR_CODE", "message": "...", "details": {}}}` 格式
- 在 `agent/main.py` 的 `create_app()` 中注册异常处理器

**涉及文件：**
- `agent/api/error_handlers.py`（新建）
- `agent/main.py`（修改）

---

### 1.2 前端动画系统

**问题：** `simulation-model.ts` 当前仅支持 CSS 类切换（highlight），无补间动画系统。设计文档 7.1.4 节要求支持 16 种动画的前端实现。

**MVP 实施（4 种核心动画）：**
- `appear` — framer-motion `AnimatePresence` fadeIn
- `disappear` — framer-motion `AnimatePresence` fadeOut
- `highlight` — CSS `box-shadow` pulse + 颜色闪烁（已有基础）
- `update_value` — CSS transition 颜色闪烁 + 数字变化
- `move` — framer-motion `animate` 位移动画

**涉及文件：**
- `web/src/components/workbench/simulation-model.ts`（修改）
- `web/src/components/workbench/SimulationGraph.tsx`（修改）
- `web/src/components/workbench/SimulationPreview.tsx`（修改）

---

### 1.3 前端视觉对象渲染

**问题：** 当前仅支持 node 和 edge（5 种中 2 种），缺少 array/table/code_block 渲染。

**实施：**
- `ArrayObject` — DOM flex 排列，每个 cell 是一个 div，支持值变化闪烁
- `TableObject` — HTML `<table>`，单元格可单独高亮
- `CodeBlockObject` — 使用 Shiki 或纯 `<pre>` 语法高亮，支持逐行高亮

**涉及文件：**
- `web/src/components/workbench/` 下新建 `visual-objects/` 目录
- `web/src/components/workbench/SimulationPreview.tsx`（修改）

---

### 1.4 播放状态机

**问题：** 当前仅 `isPlaying` 布尔值，无 IDLE/PLAYING/PAUSE/WAITING/RECOMPUTE 状态机。

**实施：**
- 在 `simulation-model.ts` 中定义 `PlayState` 枚举
- 实现状态转换逻辑：
  - IDLE → PLAYING（点击播放）
  - PLAYING → PAUSE（暂停）
  - PLAYING → WAITING（到达交互帧）
  - WAITING → PLAYING（用户完成交互）
  - 参数变更 → RECOMPUTE → PLAYING

**涉及文件：**
- `web/src/components/workbench/simulation-model.ts`（修改）

---

## 🟡 Phase 2: 中优先级修复（功能闭环）

### 2.1 知识库接入 pgvector 向量检索

**问题：** 当前 `api/knowledge.py` 使用关键词匹配，pgvector 基础设施（表、索引）已在 `init.sql` 中定义就绪。

**实施：**
- 新建 `agent/services/knowledge_service.py` — 向量检索服务
- 实现 `seed_knowledge.json` → 生成 embedding → 写入 `knowledge_base` 表的迁移脚本
- 修改 `search_knowledge` API 调用 `pgvector` 的 `<->` 余弦距离操作符
- 保留关键词匹配作为降级方案

**涉及文件：**
- `agent/services/knowledge_service.py`（新建）
- `agent/api/knowledge.py`（修改）
- `agent/scripts/seed_embeddings.py`（新建）

---

### 2.2 LangGraph Checkpointer 持久化

**问题：** `graph.py` 的 `compile()` 未传入 checkpointer，会话状态仅存内存，重启丢失。

**实施：**
- 使用 `langgraph.checkpoint.postgres.aio.AsyncPostgresSaver`
- 在 `build_graph()` 中创建 checkpointer 并传入 `compile(checkpointer=...)`
- 在 `generate_service.py` 中正确使用 `thread_id` 配置

**涉及文件：**
- `agent/agents/graph.py`（修改）
- `agent/services/generate_service.py`（修改）

---

### 2.3 前端文件上传页面

**问题：** 验证报告标记 F2.7 文件上传缺失。

**实施：**
- 在 `NewProject.tsx` 中添加文件上传 Tab（拖拽 + 点击上传）
- 对接 `POST /api/materials/upload` 和 `POST /api/materials/{id}/parse`
- 展示解析结果，支持选择主题

**涉及文件：**
- `web/src/pages/NewProject.tsx`（修改）
- `web/src/components/` 下新建 `FileUploader.tsx`（新建）

---

### 2.4 前端反馈 UI

**问题：** 验证报告标记 F3.2 反馈 UI 缺失。

**实施：**
- 在 `Player.tsx` 中添加帧级反馈按钮
- 实现评分（1-5 星）+ 纠错 + 建议三种反馈类型
- 对接 `POST /api/projects/{id}/feedback`

**涉及文件：**
- `web/src/pages/Player.tsx`（修改）
- `web/src/components/` 下新建 `FeedbackPanel.tsx`（新建）

---

### 2.5 前端参数面板完善

**问题：** 验证报告标记 F1.6 参数面板缺少滑块等控件。

**实施：**
- 实现 Slider 控件（数字类型参数）
- 实现 Select 控件（枚举类型参数）
- 实现 Switch 控件（布尔类型参数）
- 实现参数修改后的本地重算（recompute_scope=local）vs 服务端重算（all_frames）分流

**涉及文件：**
- `web/src/components/workbench/SimulationPreview.tsx`（修改）
- `web/src/components/` 下新建 `ParamControls.tsx`（新建）

---

### 2.6 前端知识卡片组件

**问题：** 验证报告标记 F3.1 知识卡片/思维导图缺失。

**实施：**
- 实现 `KnowledgeCard` 组件：定义/直观解释/常见误区/公式
- 实现 `MindmapView` 组件：树形结构展示概念关系
- 在播放器侧边栏集成展示

**涉及文件：**
- `web/src/components/workbench/` 下新建 `KnowledgeCard.tsx`（新建）
- `web/src/components/workbench/` 下新建 `MindmapView.tsx`（新建）

---

## 🟢 Phase 3: 低优先级（远期完善）

### 3.1 Parameter Agent 独立实现

**问题：** 设计文档定义 Parameter Agent 为 Coder 的可调用 Tool，当前代码中 Coder 直接生成 parameters。

**实施：**
- 新建 `parameter_node` 作为独立 Agent 节点
- 定义 `design_parameters` Tool 函数
- 在 `graph.py` 中可选择性地将 Parameter Agent 作为 Coder 的子图

**涉及文件：**
- `agent/agents/nodes.py`（修改）
- `agent/tools/` 下新建 `design_parameters.py`（新建）

### 3.2 Resource Agent 独立实现

**问题：** 同上，Resource Agent 用于生成知识卡片/思维导图等。

**实施：**
- 新建 `resource_node` 作为独立 Agent 节点
- 定义 `generate_asset` Tool 函数

**涉及文件：**
- `agent/agents/nodes.py`（修改）
- `agent/tools/` 下新建 `generate_asset.py`（新建）

### 3.3 DomainPlugin 协议

**问题：** 设计文档 Section 8 定义的插件接口未实现。

**实施：**
- 定义 `DomainPlugin` Protocol 类
- 实现 CS 插件作为默认内置插件
- 重构知识库/参数规则/质量规则为插件化

### 3.4 前端版本对比界面

**问题：** 版本历史已实现列表+恢复，但缺少并排对比。

**实施：**
- 在 `VersionHistory.tsx` 中添加 diff 视图
- 使用简单的 JSON diff 展示两个版本的差异

---

## 实施顺序

```
Phase 1（先做，阻塞项）:
  1.1 错误响应格式 → 1.2 动画系统 → 1.3 视觉对象 → 1.4 播放状态机

Phase 2（然后，功能闭环）:
  2.1 pgvector → 2.2 Checkpointer → 2.3 文件上传 → 2.4 反馈UI → 2.5 参数面板 → 2.6 知识卡片

Phase 3（最后，远期完善）:
  3.1 Parameter Agent → 3.2 Resource Agent → 3.3 DomainPlugin → 3.4 版本对比
```

---

## 验证方式

每个 Phase 完成后：
1. 后端：`cd agent && python -m pytest tests/ -v`
2. 前端：`cd web && npm run typecheck && npm run test`
3. 端到端：启动 `docker compose up -d`，验证核心链路可用