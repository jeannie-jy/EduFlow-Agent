# EduFlow 安全威胁模型

- 版本：0.8
- 日期：2026-09-05
- 范围：素材上传/解析、Agent Prompt 与 Tool Calling、视频代码执行、产物下载

## 1. 信任边界与资产

需要保护的资产包括用户教学材料、项目/DSL、数据库和对象存储凭据、模型密钥、会话、
Tool 执行权限、生成成本以及导出产物。系统把浏览器输入、上传文件、检索片段、ToolResult、
LLM 输出和模型生成代码都视为不可信；API、数据库约束、owner 策略和无凭据沙箱是执行边界。

```text
Browser (untrusted input)
  -> FastAPI auth/RBAC/owner boundary
  -> PostgreSQL + MinIO (trusted persistence)
  -> LLM/Embedding providers (external processors)
  -> Tool Runtime (allowlisted read-only capabilities)
  -> credentialed Worker -> signed shared task -> credential-free Sandbox
```

## 2. 分链路威胁与控制

| 链路 | 主要威胁 | 当前控制 | 已知剩余风险 |
|---|---|---|---|
| 上传 | 超大请求、伪造扩展名、路径穿越、PPTX ZIP bomb、跨 owner 读取 | 分块大小上限、扩展名+magic 校验、安全文件名、PPTX 成员/解压体积/压缩比/加密检查、owner ID、MinIO key 规范化 | 杀毒/CDR 未实现；旧本地文件未迁移 |
| 解析 | 恶意 PDF/PPTX 利用解析器读取凭据、联网、耗尽 CPU/内存/PID | 带凭据 Worker 只负责下载和 SHA-256 签名；无网络无凭据材料沙箱验签后解析；只读根、tmpfs、CPU/内存/PID/超时/结果大小限制 | 当前是常驻容器；真实 OOM/fork-bomb 压测待运行 |
| Prompt/RAG | 用户、材料或检索结果关闭边界、伪造系统角色、诱导泄密或 Tool 滥用 | Prompt 标记字符编码；系统策略明确所有外部内容为不可信数据；Tool Registry 只读 allowlist；服务端注入 actor/project；结果回填保持 `trust=untrusted`；专项回归数据集 | Prompt 防护不能作为绝对安全边界；真实模型注入基线和人工校准待运行 |
| Tool Calling | 未注册能力、参数注入、跨租户访问、调用风暴、结果注入 | Pydantic `extra=forbid`、owner 二次校验、只读 Registry、轮数/调用数/共享并发/超时/结果预算、脱敏 Trace | MCP/Skill 和写工具未实现；未来写工具必须增加审批、幂等和补偿 |
| 视频代码执行 | 模型代码访问密钥/网络/宿主文件、fork bomb、磁盘填满、迟到结果覆盖 | API/准备器不执行代码；无网络无凭据沙箱复核脚本摘要；非 root、只读根、cap drop、PID/CPU/内存/时间/文件数/字节限制；lease/attempt 校验 | 共享卷与常驻沙箱弱于每任务临时容器；真实恶意样本压力报告待补 |
| 下载 | 猜测 job/material ID、路径穿越、永久公开链接、已取消任务泄漏产物 | owner/project 联合查询、规范化对象 key、短期 presigned URL、固定产物清单、终态/attempt 校验 | 外部 CDN/WAF、下载审计归档和一次性 URL 未实现 |

## 3. Prompt Injection 数据流规则

1. 用户字符串进入 XML-like Prompt 前把 `<`、`>`、`&` 编码为字面 `\uXXXX`，避免创建
   同级标签；结构化对象先 JSON 序列化再执行同样编码。
2. System Prompt 明确主题、材料、旧 DSL、反馈、检索片段和 ToolResult 仅是任务数据，
   不得改变角色、访问环境/文件/网络或泄露凭据。
3. 模型不能直接获得 actor、owner 或数据库连接；Tool Runtime 从服务端上下文注入身份。
4. 模型输出仍须经过 DSL Schema、状态不变量、锁帧/范围合并或沙箱，而不是因 Prompt
   声明而被信任。

## 4. 验证证据

- `test_prompt_boundaries.py`：用户主题、材料和检索文本无法关闭 Prompt 数据边界；
- `test_prompt_injection.py` 与 `evals/datasets/injection_cases.jsonl`：角色伪造、泄密、
  Tool 滥用、冲突材料、XSS 和引用伪造；
- `test_tool_runtime.py`/`test_tool_eval.py`：参数、权限、超时、并发、预算和 allowlist；
- `test_material_sandbox.py`/`test_export_security.py`：摘要篡改、路径、配额、隔离与补偿；
- `test_auth.py` 及 API 集成测试：会话、role、owner 和跨项目不可见性。

这些是确定性工程证据，不等于真实模型攻击成功率或容器逃逸证明。真实在线 Bench、
容器恶意样本和多副本压力测试仍须单独记录报告。
