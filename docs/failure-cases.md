# 故障案例与防护矩阵

以下条目来自现有实现和自动化测试，不代表尚未运行的线上模型质量结论。

| 故障 | 原始风险 | 当前处理 | 验证入口 |
|---|---|---|---|
| LLM 429/5xx/timeout | 请求直接失败或重试风暴 | 错误分类、指数退避+jitter、并发上限、provider 熔断与 fallback | `test_llm_gateway.py` |
| 结构化输出截断/非法 JSON | 节点产物不可解析 | 有界解析重试与节点 Token 硬预算，耗尽后明确失败 | `test_llm_client.py`, `test_llm_gateway.py` |
| 检索无结果/Embedding 失败 | Agent 编造来源或主链中断 | 记录 degraded 状态，空证据继续生成，不伪造 citation | `test_workflow_retrieval.py` |
| Tool 参数错误/越权/未知工具 | 访问其他租户或扩大执行面 | Pydantic 参数校验、服务端身份注入、owner 二次校验、只读 Registry、标准错误 ToolResult | `test_tool_runtime.py`, `test_tool_eval.py` |
| Prompt Injection 来自材料/检索 | 不可信文本改变系统目标 | XML 信任边界、工具结果作为 data、禁止执行材料中的指令、专项数据集 | `test_workflow_retrieval.py`, `injection_cases.jsonl` |
| 参数依赖缺失 | 局部重算漏掉状态后继 | 无法证明依赖时 fail-closed 到全量；显式/推断依赖从最早帧向后传播 | `test_parameter_validation.py` |
| 预览后并发编辑 | 按过期范围覆盖新状态 | 预览内容指纹；执行前不匹配即 409，且不产生 DB 写入 | `test_parameter_validation.py` |
| SSE 网络断开/API 崩溃 | 重复执行、丢进度或重复终态 | 事件先落库、单调 ID、Last-Event-ID、producer lease、终态重放 | `test_sse_ledger.py`, `sse.test.ts` |
| Worker 中途崩溃 | 任务永久 running | lease/heartbeat/attempt、超时重领、迟到结果拒绝 | `test_export_worker.py`, `test_task_worker.py` |
| 生成代码读文件/联网/fork | 凭据泄漏或资源耗尽 | 无网络无凭据沙箱、只读根、cap drop、PID/CPU/内存/磁盘/超时限制 | `test_export_security.py` + Compose 静态检查 |
| 不可信 PDF/PPTX 解析漏洞 | 读取凭据、联网、ZIP 炸弹或资源耗尽 | 下载/签名与解析权限拆分；无网络无凭据材料沙箱；路径、压缩比、解压体积、结果 Schema/大小限制 | `test_material_sandbox.py`, `test_phase2_materials.py` |
| 对象上传成功但 DB 提交失败/任务被取消 | 孤儿对象或已取消任务泄漏产物 | 素材与导出均在终态写入失败时执行对象存储补偿删除 | `test_phase2_materials.py`, `test_export_security.py` |

## 尚未完成的故障验证

- 仓库已提供 `agent/scripts/compose_fault_smoke.py` 与手动工作流
  `.github/workflows/fault-injection.yml`，用于真实停止 Redis、PostgreSQL、MinIO
  容器并验证 liveness、依赖级 readiness 和恢复；当前开发环境无可用 Docker
  daemon，因此脚本已实现但尚未产出一次真实运行报告；
- Manim 容器崩溃、执行超时与恢复的真实故障注入；
- fork bomb、OOM、超大产物的持续压力测试；
- 已提供 `http_capacity_smoke.py` 和 60 秒手动 CI 容量门禁，记录只读端点的
  RPS、错误率和 p50/p95/p99；多副本 API/Worker 携带真实任务的长时间 soak 仍待运行；
- 真实模型 Tool/质量 Bench 与至少 20% 人工校准。
