# 第二阶段后台索引临时库验收（2026-09-30）

使用本机无持久卷、仅绑定 `127.0.0.1:55434` 的 `pgvector/pgvector:0.8.6-pg16` 一次性容器，从空库执行 `alembic upgrade head` 至 `0028_knowledge_library`。数据库只包含合成教师、项目、材料和原创测试文本。运行命令为 `EDUFLOW_TEST_DATABASE_URL=... EDUFLOW_TEST_DB_DISPOSABLE=1 pytest -q agent/tests/test_material_index_postgres.py agent/tests/test_teacher_library_postgres.py`，结果 `2 passed`。

新增用例通过真实数据库调用 `material_index` 后台执行器：

- 原创 Markdown 超过旧解析预览的 10 万字符上限，索引生成超过 100 个片段；尾部章节仍可按关键词检索到，返回 `long-lecture.md` 与 `section:2` 定位。
- 同一内容重复执行完整后台索引后只有一个知识版本，两个任务均完成；测试将 `generate_embedding` 设为若被调用即被发现，实际未调用。
- 另一个教师的项目无法召回该资料；删除材料后来源、版本、片段经外键级联清除，原项目重新检索也为零召回。
- 原有多教师、三项目、关联幂等及删除隔离测试再次通过。

这证明了“本地关键词索引 + 数据库授权过滤”的路径，不代表生产沙箱部署、OCR、真实模型生成质量或付费语义检索已验收。生产读取开关与外部来源发布仍须单独验收。
