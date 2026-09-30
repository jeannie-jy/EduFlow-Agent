# 第三阶段外部来源待审同步验收（2026-09-30）

无持久卷、仅监听 `127.0.0.1:55435` 的临时 `pgvector/pgvector:0.8.6-pg16` 容器，从空库迁移到 `0029_external_source_review`。`EDUFLOW_TEST_DB_DISPOSABLE=1` 与专用数据库 URL 下，外部来源、教师长文档、跨教师隔离集成测试共 `17 passed`；常规后端回归（排除本机未装 Manim 的渲染专测）为 `1343 passed, 4 skipped`。

合成数据验收覆盖：定时任务仅排队到期白名单 URL；后台校验值同步创建不可检索候选；缺少四项明确确认无法发布；填写原创摘要与版本后发布，检索带 URL、章节、版本、作者和许可；远端校验值变化时旧来源暂停检索，重新审核新版本后恢复；管理员撤回后零召回。发布过程未调用 Embedding。

另外以真实 HTTPS 对 [PostgreSQL 16 索引类型](https://www.postgresql.org/docs/16/indexes-types.html)和 [Python `bisect` 文档](https://docs.python.org/3/library/bisect.html)执行受限抓取，只将校验值及 HTTP 元数据写入临时库，得到两个 `pending` 候选。Python 来源无发布记录；PostgreSQL URL 在先前合成用例中曾发布测试摘要，真实页面校验值变化后被标记为 `retired`。两者均未以真实网页正文或未经审核的摘要进入当前检索结果。本测试没有对真实页面的教学摘要作事实或许可签核。

临时容器测试后停止并通过 `--rm` 删除。生产仍须完成独立的人工/法务复核、网络出口限制和质量评测，再开启 `knowledge_v2_enabled` 或发布真实候选。
