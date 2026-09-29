# 第二阶段教师资料库临时库验收（2026-09-29）

使用无持久卷、仅绑定 `127.0.0.1:55433` 的 `pgvector/pgvector:0.8.6-pg16` 临时容器，从空库执行 `alembic upgrade head` 到 `0028_knowledge_library`。仅写入合成教师、项目、材料和原创测试片段；没有真实用户资料、外部来源、付费 Embedding 或远端模型调用。测试后停止容器，`--rm` 自动删除；`docker ps -a --filter name=eduflow-teacher-library-test-20260929` 没有残留。

运行 `EDUFLOW_TEST_DATABASE_URL=... python -m pytest tests/test_teacher_library_postgres.py -q`，1 个 PostgreSQL 集成用例通过。测试脚本随后增加 `EDUFLOW_TEST_DB_DISPOSABLE=1` 的显式保护标志，今后运行必须同时设置该标志：

- 两位教师、三个项目分别建立资料库来源；同一教师可在两个本人项目复用资料。
- 关联 SQL 对项目、资料和知识来源同时检查所有者；跨教师或跨项目关联失败。
- 相同关联和相同来源版本重复执行保持幂等；原始资料没有被索引任务自动调用付费 Embedding。
- 检索只在数据库查询阶段返回当前项目授权的片段，结果带资料名和 `page:2;char:0-20` 定位；其他项目和教师零召回。
- 从一个项目移除关联不影响另一个项目；删除资料后外键级联清除来源和关联，重新检索零召回。

局限：这是手工构造片段的词法检索及授权链路验收，不证明后台索引任务、长 PDF 解析、向量检索、OCR 或前端引用展示已完成。后续仍须实现教师显式索引授权、后台状态/重试与端到端 UI 结果。集成测试默认跳过，只有同时提供专用 `EDUFLOW_TEST_DATABASE_URL` 和 `EDUFLOW_TEST_DB_DISPOSABLE=1` 时运行，防止误写开发或生产数据库。
