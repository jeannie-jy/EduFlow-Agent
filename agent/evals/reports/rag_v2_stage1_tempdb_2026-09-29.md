# RAG v2 临时数据库验收记录（2026-09-29）

范围：隔离的 `pgvector/pgvector:0.8.6-pg16` 临时容器，无持久卷；仅导入原有 22 条 `legacy` 种子，未导入第 1、2 批待审草稿，未生成 Embedding，未连接生产库。测试后已停止并由 `--rm` 自动移除。

| 检查 | 结果 |
| --- | --- |
| 从空库执行 `alembic upgrade head` | 成功到 `0028_knowledge_library` |
| 执行 `seed_knowledge_v2` | 来源、版本、片段各 22；向量 0 |
| 重复执行 `seed_knowledge_v2` | 仍各 22，确认数据库结果幂等；脚本当前输出的“Imported 22”表示处理数量，不代表新增数量 |
| `alembic downgrade -1` 后再 `upgrade head` 并回填 | 成功，最终版本 `0028_knowledge_library`，各 22，向量 0 |
| 词法检索“二分查找” | 命中稳定 ID `algo_binary_search` |
| 库外英文标识 `zzzxqv_missing_topic_928341` | 初次意外命中 `ds_hash_table`；修复英文长词被切成 n-gram 的问题后，重新测试返回空结果 |
| 临时容器清理 | `docker stop eduflow-rag-v2-test-20260929` 后 `docker ps -a --filter name=...` 无结果 |

限制：新建测试库的旧 `knowledge_base` 表为空，且本次没有付费 Embedding，因此没有运行有意义的旧/新向量检索排名比对，也不能声称 Recall@5、引用正确率或真实查询延迟达标。第 1、2 批的来源签核、正式测试库导入和生产读取切换仍未完成。
