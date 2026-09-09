# ADR 0005：用数据库状态、lease 与事件账本实现可恢复执行

- 状态：Accepted
- 日期：2026-09-05

## 背景

Agent 生成、材料解析和视频导出均可能持续数十秒到数分钟，并跨越教师审批。只依赖 API
进程内 Task、Redis 临时状态或浏览器 SSE 连接，会在进程崩溃、网络断开和 Worker 迟到
写入时造成丢任务、重复执行或终态覆盖。

## 决策

按状态类型使用不同持久化机制：LangGraph PostgreSQL Checkpointer 保存工作流和 HITL
恢复点；`background_jobs`/`export_jobs` 以 attempt、lease、heartbeat、退避时间和幂等键
驱动 Worker；SSE 事件先写 PostgreSQL 账本，再向客户端发送，并用 producer lease 保证同一
stream 只有一个执行者。客户端携带 `Last-Event-ID` 重放，丢失本地游标时可按 owner 查询
活动 stream。所有终态更新均校验当前 attempt/lease，已取消或被接管任务拒绝迟到结果；对象
已经发布但终态写入失败时执行补偿删除。

## 结果

- API/浏览器断线不等于取消任务，HITL 可在重启后继续；
- Worker 崩溃后任务可被重领，旧 Worker 不能覆盖新 attempt 或取消终态；
- SSE 支持单调事件 ID、去重、重放、单终态和跨设备活动流发现；
- PostgreSQL 是任务与事件事实源，Redis 只承担速率限制和导出热状态等可降级职责；
- 当前非主 Graph 模块只在模块边界 checkpoint，多副本长时间 soak 和执行中数据库重启仍需
  真实容器环境验证。

## 被否决方案

- FastAPI `BackgroundTasks`/进程内队列：无法跨进程恢复；
- Redis 作为唯一任务与 SSE 事实源：保留、审计和终态事务边界不足；
- SSE 断线即重新调用 Graph：会重复扣费并产生并发版本；
- 仅按任务状态更新、不校验 lease/attempt：迟到 Worker 可覆盖正确终态。
