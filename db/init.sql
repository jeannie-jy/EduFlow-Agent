-- EduFlow-Agent 数据库初始化脚本
-- 在 PostgreSQL + pgvector 容器首次启动时自动执行。
--
-- 注意：业务表（projects/frames/parameters/quality_reports/export_jobs/
-- feedback/source_materials/project_versions/knowledge_base）由 Alembic 管理，
-- 在 agent-api 启动时通过 `alembic upgrade head` 创建（见 agent/alembic/versions/0001_baseline.py）。
-- 这里只负责数据库实例级别的扩展，避免出现「init.sql 与 ORM 双真源」的 schema 漂移。

-- pgvector 扩展（knowledge_base.embedding 向量检索依赖）
CREATE EXTENSION IF NOT EXISTS vector;
