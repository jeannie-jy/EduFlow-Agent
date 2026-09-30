# 第三阶段：权威外部来源的待审同步

此功能使用两个互相独立的门：管理员维护精确 URL 白名单；管理员审核候选后明确发布。后台每 24 小时检查到期 URL，但只保存页面 SHA-256、抓取时间、ETag 和 Last-Modified。网页原文不进入知识库，也不会自动生成摘要或调用付费 Embedding。正文仅接受管理员自行编写、人工核对的 30–4000 字摘要。

首批建议参见 [`agent/data/external_source_proposals.json`](../data/external_source_proposals.json)，包含 PostgreSQL 16 索引类型和 Python `bisect` 两个官方文档页面。此文件是候选清单，不等于许可或事实审核通过。RFC、NIST 和 MDN 暂不自动收录：RFC 的修改限制、NIST 部分词条的第三方版权和 MDN 的署名/相同方式共享要求需要逐项确认。

管理员流程：

1. `POST /api/admin/external-sources/allowlist`，提交精确 HTTPS URL、机构和来源许可核查备注。硬编码来源域名和版本路径边界阻止任意网站或内网地址进入白名单。
2. `POST /api/admin/external-sources/allowlist/{id}/sync` 可立即排队；后台也会定时排队。查看 `/api/background-jobs/{job_id}` 和 `GET /api/admin/external-sources/candidates`。新校验值产生 `pending` 草稿；无变化时不增加候选。
3. 用 `PUT /api/admin/external-sources/candidates/{id}` 填写标题、具体章节、适用文档版本、原创摘要、作者、文档发布日期（若可证实）和许可证。
4. 逐一确认版本、署名、许可和摘要原创性，然后 `POST /api/admin/external-sources/candidates/{id}/publish`，请求体的四个 `confirm_*` 字段均为 `true`。系统才建立可检索版本；未确认时返回 422。若远端校验值已变化，旧候选返回 409。
5. `POST /api/admin/external-sources/allowlist/{id}/retire` 立即撤回检索。远端内容变化也会暂时撤下旧版本，等待新候选复核。

同步接受官方域名下的指定路径、HTTPS、无凭据/端口/查询参数/重定向、最多 1 MB 的文本响应。生产网络还应以出口防火墙限制到对应官方域名。抓取失败记录任务错误和来源 `last_error`；管理员列表显示最后抓取时间及校验值。当前默认 `knowledge_v2_enabled=false`，发布的来源仅在显式开启新版检索后进入生成和知识 API；生产切换仍需评测与权限验收。

测试：`pytest -q tests/test_external_sources.py`；在已运行迁移的专用、可丢弃 PostgreSQL 上设置 `EDUFLOW_TEST_DATABASE_URL` 与 `EDUFLOW_TEST_DB_DISPOSABLE=1`，运行 `pytest -q tests/test_external_sources_postgres.py`。后者以合成指纹与原创摘要验证私有草稿、发布、内容变化、重新审核和撤回，不连接真实网站。
