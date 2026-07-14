-- EduFlow-Agent 数据库初始化脚本
-- 在 PostgreSQL + pgvector 容器首次启动时自动执行

-- pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 长期记忆表
CREATE TABLE IF NOT EXISTS long_term_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    memory_type VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    importance_score FLOAT DEFAULT 0.0,
    access_count INT DEFAULT 0,
    success_rate FLOAT DEFAULT 0.0,
    user_rating INT,
    concept_tags TEXT[],
    related_memory_ids UUID[],
    source_trajectory JSONB,
    status VARCHAR(20) DEFAULT 'active',
    last_accessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    decayed_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ
);

-- 知识库表
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept VARCHAR(500) NOT NULL,
    definition TEXT,
    syllabus JSONB,
    common_pitfalls JSONB,
    prerequisites TEXT[],
    difficulty INT DEFAULT 3,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 轨迹表
CREATE TABLE IF NOT EXISTS trajectories (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_query TEXT NOT NULL,
    task_graph_id UUID,
    steps JSONB NOT NULL,
    final_outcome VARCHAR(20),
    total_latency_ms INT,
    total_input_tokens INT,
    total_output_tokens INT,
    human_interventions INT DEFAULT 0,
    reflection_attempts INT DEFAULT 0,
    memory_writes INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 工具调用日志表
CREATE TABLE IF NOT EXISTS tool_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES trajectories(session_id),
    step_index INT,
    tool_name VARCHAR(100),
    params JSONB,
    result JSONB,
    success BOOLEAN,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_memories_embedding
    ON long_term_memories USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_memories_concept_tags
    ON long_term_memories USING gin (concept_tags);
CREATE INDEX IF NOT EXISTS idx_memories_importance
    ON long_term_memories (importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON knowledge_base USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_trajectories_outcome
    ON trajectories (final_outcome);
CREATE INDEX IF NOT EXISTS idx_trajectories_created
    ON trajectories (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_logs_session
    ON tool_call_logs (session_id, step_index);
CREATE INDEX IF NOT EXISTS idx_tool_logs_tool
    ON tool_call_logs (tool_name, success);
