-- ============================================================================
-- EduFlow-Agent 数据库初始化脚本
-- ============================================================================
-- 在 PostgreSQL + pgvector 容器首次启动时自动执行。
-- 表结构对齐设计文档 v1.0 第 10 节。
-- ============================================================================

-- pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. 项目
-- ============================================================================
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    topic VARCHAR(300),
    subject VARCHAR(200),
    course VARCHAR(300),
    audience VARCHAR(100) DEFAULT 'undergraduate_cs',
    difficulty VARCHAR(50) DEFAULT 'intermediate',
    owner_id VARCHAR(200),
    status VARCHAR(50) DEFAULT 'draft',
    -- 最新 DSL 快照（JSONB 便于快速读取完整状态）
    dsl_snapshot JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 2. 源材料（上传的课件/代码/文档）
-- ============================================================================
CREATE TABLE IF NOT EXISTS source_materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,          -- pdf / ppt / markdown / text / code
    filename VARCHAR(500),
    content_text TEXT,
    parsed_result JSONB,               -- 解析后的结构化内容
    metadata JSONB,
    size_bytes BIGINT,
    storage_path VARCHAR(1000),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 3. 教学计划（Planner Agent 产出）
-- ============================================================================
CREATE TABLE IF NOT EXISTS teaching_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    version INT NOT NULL DEFAULT 1,
    objectives JSONB,                  -- 教学目标列表
    prerequisites JSONB,               -- 先修知识
    outline JSONB,                     -- 知识点大纲
    strategy JSONB,                    -- 教学策略
    constraints JSONB,                 -- 教师约束
    estimated_duration_min INT,
    risk_notes JSONB,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 4. 帧（核心表，高频读写）
-- ============================================================================
CREATE TABLE IF NOT EXISTS frames (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    version INT NOT NULL DEFAULT 1,
    frame_id VARCHAR(50) NOT NULL,      -- "f_001"
    order_index INT NOT NULL,           -- 帧序号
    title VARCHAR(500),
    learning_goal TEXT,
    narration TEXT,
    visual_objects JSONB,               -- 画面元素定义列表
    state_snapshot JSONB,               -- 状态快照
    animations JSONB,                   -- 动画序列
    interaction_hooks JSONB,            -- 交互控件
    checks JSONB,                       -- 校验规则
    quality_status VARCHAR(50) DEFAULT 'pending',
    is_locked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, version, frame_id)
);

-- ============================================================================
-- 5. 参数
-- ============================================================================
CREATE TABLE IF NOT EXISTS parameters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    key VARCHAR(200) NOT NULL,
    label VARCHAR(500),
    param_type VARCHAR(50) NOT NULL,    -- number / string / boolean / enum / graph / array
    default_value JSONB,
    current_value JSONB,
    constraints JSONB,                  -- 取值范围、边界条件
    visibility VARCHAR(50) DEFAULT 'student',
    recompute_scope VARCHAR(50) DEFAULT 'all_frames',  -- local / all_frames
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, key)
);

-- ============================================================================
-- 6. 质量报告
-- ============================================================================
CREATE TABLE IF NOT EXISTS quality_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    version INT NOT NULL DEFAULT 1,
    scores JSONB,                       -- {correctness: 0.9, clarity: 0.85, ...}
    issues JSONB,                       -- [{frame_id, type, severity, description}]
    suggestions JSONB,                  -- 修复建议
    is_blocking BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 7. 导出任务
-- ============================================================================
CREATE TABLE IF NOT EXISTS export_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    target VARCHAR(50) NOT NULL,        -- manim_video
    status VARCHAR(50) DEFAULT 'queued',-- queued / rendering / completed / failed
    config JSONB,                       -- 分辨率、帧率、格式等
    progress_pct FLOAT DEFAULT 0,
    artifacts JSONB,                    -- 产物路径列表
    error_log TEXT,
    duration_ms INT,
    total_frames INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ============================================================================
-- 8. 用户反馈
-- ============================================================================
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    frame_id UUID,                      -- 可选，关联到具体帧
    type VARCHAR(50) NOT NULL,          -- rating / correction / suggestion
    content TEXT,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 9. 项目版本（用于版本管理）
-- ============================================================================
CREATE TABLE IF NOT EXISTS project_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    version INT NOT NULL,
    dsl_snapshot JSONB NOT NULL,        -- 该版本的完整 DSL
    change_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, version)
);

-- ============================================================================
-- 10. 知识库（pgvector 语义检索）
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept VARCHAR(500) NOT NULL,      -- 知识点名称
    content TEXT NOT NULL,              -- 结构化教学内容
    embedding VECTOR(1536),             -- text-embedding-3-small
    subject VARCHAR(200),               -- 学科分类
    difficulty INT CHECK (difficulty BETWEEN 1 AND 5),
    object_types TEXT[],                -- 涉及的可视化对象类型
    animation_types TEXT[],             -- 涉及的动画类型
    template_dsl JSONB,                 -- 关联的 DSL 模板
    usage_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 11. LangGraph Checkpointer 表（LangGraph 内建机制使用）
-- ============================================================================
CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_id, checkpoint_ns)
);

-- ============================================================================
-- 索引策略（对齐设计文档 10.3 节）
-- ============================================================================

-- 帧查询：按项目和序号
CREATE INDEX IF NOT EXISTS idx_frames_project_order
    ON frames (project_id, version, order_index);
CREATE INDEX IF NOT EXISTS idx_frames_frame_id
    ON frames (project_id, frame_id);

-- 参数查询：按项目
CREATE INDEX IF NOT EXISTS idx_params_project
    ON parameters (project_id);

-- 质量报告：按项目和时间
CREATE INDEX IF NOT EXISTS idx_quality_project
    ON quality_reports (project_id, created_at DESC);

-- 导出任务：按状态（队列轮询）
CREATE INDEX IF NOT EXISTS idx_export_status
    ON export_jobs (status, created_at);

-- 知识库：向量检索 + 学科筛选
CREATE INDEX IF NOT EXISTS idx_kb_embedding
    ON knowledge_base USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_kb_subject_difficulty
    ON knowledge_base (subject, difficulty);
CREATE INDEX IF NOT EXISTS idx_kb_object_types
    ON knowledge_base USING gin (object_types);

-- 反馈：按项目和帧
CREATE INDEX IF NOT EXISTS idx_feedback_project
    ON feedback (project_id);
CREATE INDEX IF NOT EXISTS idx_feedback_frame
    ON feedback (frame_id);

-- 源材料：按项目
CREATE INDEX IF NOT EXISTS idx_materials_project
    ON source_materials (project_id);

-- 版本：按项目
CREATE INDEX IF NOT EXISTS idx_versions_project
    ON project_versions (project_id, version DESC);

-- 项目列表：按状态和时间
CREATE INDEX IF NOT EXISTS idx_projects_status
    ON projects (status, updated_at DESC);
