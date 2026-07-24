"""数据库集成测试。

使用 SQLite 内存数据库进行 CRUD 操作、约束验证、事务回滚测试。
通过 patch PostgreSQL 特有类型兼容 SQLite，CI 友好。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, func, schema, types
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from db.models import (
    Base,
    Project,
    Frame,
    ParameterModel,
    QualityReportModel,
    ExportJobModel,
    Feedback,
    SourceMaterial,
    ProjectVersion,
    User,
    AuthSession,
)


# ============================================================================
# Authentication models
# ============================================================================


@pytest.mark.asyncio
async def test_user_email_normalized_is_unique(db_session: AsyncSession):
    first = User(
        email="Student@example.com",
        email_normalized="student@example.com",
        nickname="Student",
        password_hash="encoded",
    )
    db_session.add(first)
    await db_session.flush()

    db_session.add(
        User(
            email="student@example.com",
            email_normalized="student@example.com",
            nickname="Other",
            password_hash="encoded",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_auth_session_is_deleted_with_user(db_session: AsyncSession):
    user = User(
        email="user@example.com",
        email_normalized="user@example.com",
        nickname="User",
        password_hash="encoded",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        AuthSession(
            user_id=user.id,
            family_id=uuid.uuid4(),
            refresh_token_hash="a" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    await db_session.flush()
    await db_session.delete(user)
    await db_session.flush()
    assert await db_session.scalar(select(func.count(AuthSession.id))) == 0


# ============================================================================
# Helpers
# ============================================================================

_replaced = False


def _make_sqlite_compatible():
    """将 ORM 模型中 PostgreSQL 特有类型替换为 SQLite 兼容类型。"""
    global _replaced
    if _replaced:
        return
    from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID as PG_UUID

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = types.JSON()
            elif isinstance(col.type, ARRAY):
                col.type = types.JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = types.Uuid(as_uuid=True)
                if col.server_default is not None:
                    col.server_default = None
                if col.default is None and col.primary_key:
                    col.default = schema.ColumnDefault(uuid.uuid4)
            elif col.type.__class__.__name__ == "VECTOR":
                col.type = types.JSON()
    _replaced = True


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """创建 SQLite 内存数据库会话。"""
    _make_sqlite_compatible()

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


# ============================================================================
# Project CRUD
# ============================================================================


class TestProjectCRUD:
    """项目 CRUD 操作测试。"""

    @pytest.mark.asyncio
    async def test_create_project(self, db_session: AsyncSession):
        """创建项目并验证持久化。"""
        p = Project(
            title="冒泡排序教学",
            topic="排序算法",
            audience="undergraduate_cs",
            difficulty="beginner",
            status="draft",
        )
        db_session.add(p)
        await db_session.flush()

        result = await db_session.execute(
            select(Project).where(Project.title == "冒泡排序教学")
        )
        fetched = result.scalar_one()
        assert fetched.topic == "排序算法"
        assert fetched.audience == "undergraduate_cs"
        assert fetched.status == "draft"

    @pytest.mark.asyncio
    async def test_project_default_values(self, db_session: AsyncSession):
        """默认值应正确设置。"""
        p = Project(title="最小项目")
        db_session.add(p)
        await db_session.flush()

        result = await db_session.execute(
            select(Project).where(Project.title == "最小项目")
        )
        fetched = result.scalar_one()
        assert fetched.audience == "undergraduate_cs"
        assert fetched.difficulty == "intermediate"
        assert fetched.status == "draft"

    @pytest.mark.asyncio
    async def test_update_project(self, db_session: AsyncSession):
        """更新项目字段。"""
        p = Project(title="原始标题", status="draft")
        db_session.add(p)
        await db_session.flush()

        p.title = "更新后的标题"
        p.status = "planning"
        await db_session.flush()

        result = await db_session.execute(
            select(Project).where(Project.id == p.id)
        )
        fetched = result.scalar_one()
        assert fetched.title == "更新后的标题"
        assert fetched.status == "planning"

    @pytest.mark.asyncio
    async def test_delete_project(self, db_session: AsyncSession):
        """删除项目。"""
        p = Project(title="待删除")
        db_session.add(p)
        await db_session.flush()
        pid = p.id

        await db_session.delete(p)
        await db_session.flush()

        result = await db_session.execute(select(Project).where(Project.id == pid))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_list_projects(self, db_session: AsyncSession):
        """列表查询应返回正确数量。"""
        for i in range(5):
            db_session.add(Project(title=f"项目{i}"))
        await db_session.flush()

        result = await db_session.execute(select(func.count(Project.id)))
        count = result.scalar()
        assert count == 5

    @pytest.mark.asyncio
    async def test_list_projects_with_filter(self, db_session: AsyncSession):
        """按状态过滤。"""
        db_session.add(Project(title="draft1", status="draft"))
        db_session.add(Project(title="done1", status="done"))
        db_session.add(Project(title="done2", status="done"))
        await db_session.flush()

        result = await db_session.execute(
            select(func.count(Project.id)).where(Project.status == "done")
        )
        count = result.scalar()
        assert count == 2

    @pytest.mark.asyncio
    async def test_project_dsl_snapshot_json(self, db_session: AsyncSession):
        """JSON 字段应正确存储和读取。"""
        dsl = {"frames": [{"frame_id": "f_001"}], "parameters": []}
        p = Project(title="JSON测试", dsl_snapshot=dsl)
        db_session.add(p)
        await db_session.flush()

        result = await db_session.execute(
            select(Project).where(Project.title == "JSON测试")
        )
        fetched = result.scalar_one()
        assert fetched.dsl_snapshot is not None
        assert len(fetched.dsl_snapshot["frames"]) == 1


# ============================================================================
# Frame CRUD
# ============================================================================


class TestFrameCRUD:
    """帧 CRUD 操作测试。"""

    async def _create_project(self, db_session: AsyncSession) -> Project:
        p = Project(title="测试项目", status="draft")
        db_session.add(p)
        await db_session.flush()
        return p

    @pytest.mark.asyncio
    async def test_create_frame(self, db_session: AsyncSession):
        """创建帧并关联项目。"""
        proj = await self._create_project(db_session)
        f = Frame(
            project_id=proj.id,
            version=1,
            frame_id="f_001",
            order_index=1,
            title="初始化",
            narration="将源节点距离设为0",
            quality_status="ok",
        )
        db_session.add(f)
        await db_session.flush()

        result = await db_session.execute(
            select(Frame).where(Frame.project_id == proj.id)
        )
        frames = result.scalars().all()
        assert len(frames) == 1
        assert frames[0].frame_id == "f_001"

    @pytest.mark.asyncio
    async def test_frame_ordering(self, db_session: AsyncSession):
        """帧应按 order_index 排序。"""
        proj = await self._create_project(db_session)
        for i in range(3):
            db_session.add(Frame(
                project_id=proj.id, version=1,
                frame_id=f"f_{i:03d}", order_index=i + 1,
                title=f"帧{i}", narration="",
            ))
        await db_session.flush()

        result = await db_session.execute(
            select(Frame)
            .where(Frame.project_id == proj.id)
            .order_by(Frame.order_index)
        )
        frames = result.scalars().all()
        assert len(frames) == 3
        assert frames[0].order_index == 1
        assert frames[2].order_index == 3

    @pytest.mark.asyncio
    async def test_frame_unique_constraint(self, db_session: AsyncSession):
        """同一 project_id + version + frame_id 不能重复。"""
        proj = await self._create_project(db_session)
        db_session.add(Frame(
            project_id=proj.id, version=1, frame_id="f_001",
            order_index=1, title="帧1", narration="",
        ))
        await db_session.flush()

        db_session.add(Frame(
            project_id=proj.id, version=1, frame_id="f_001",
            order_index=2, title="重复帧", narration="",
        ))
        with pytest.raises(Exception):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_frame_lock(self, db_session: AsyncSession):
        """锁定帧操作。"""
        proj = await self._create_project(db_session)
        f = Frame(
            project_id=proj.id, version=1, frame_id="f_001",
            order_index=1, title="原始", narration="", is_locked=False,
        )
        db_session.add(f)
        await db_session.flush()

        f.is_locked = True
        await db_session.flush()

        result = await db_session.execute(
            select(Frame).where(Frame.project_id == proj.id)
        )
        fetched = result.scalar_one()
        assert fetched.is_locked is True

    @pytest.mark.asyncio
    async def test_frame_cascade_delete(self, db_session: AsyncSession):
        """删除项目时帧应级联删除。"""
        # SQLite 需要显式启用外键约束
        await db_session.execute(select(1))  # ensure connection
        conn = await db_session.connection()
        await conn.exec_driver_sql("PRAGMA foreign_keys = ON")

        proj = await self._create_project(db_session)
        db_session.add(Frame(
            project_id=proj.id, version=1, frame_id="f_001",
            order_index=1, title="帧", narration="",
        ))
        await db_session.flush()

        await db_session.delete(proj)
        await db_session.flush()

        result = await db_session.execute(select(Frame))
        assert len(result.scalars().all()) == 0


# ============================================================================
# Parameter CRUD
# ============================================================================


class TestParameterCRUD:
    """参数 CRUD 操作测试。"""

    async def _create_project(self, db_session: AsyncSession) -> Project:
        p = Project(title="参数测试项目")
        db_session.add(p)
        await db_session.flush()
        return p

    @pytest.mark.asyncio
    async def test_create_parameter(self, db_session: AsyncSession):
        """创建参数。"""
        proj = await self._create_project(db_session)
        p = ParameterModel(
            project_id=proj.id,
            key="graph_data",
            label="图结构",
            param_type="graph",
            default_value={"nodes": 6},
            current_value={"nodes": 6},
            recompute_scope="all_frames",
        )
        db_session.add(p)
        await db_session.flush()

        result = await db_session.execute(
            select(ParameterModel).where(ParameterModel.project_id == proj.id)
        )
        params = result.scalars().all()
        assert len(params) == 1
        assert params[0].key == "graph_data"

    @pytest.mark.asyncio
    async def test_parameter_unique_key(self, db_session: AsyncSession):
        """同一项目下 key 不能重复。"""
        proj = await self._create_project(db_session)
        db_session.add(ParameterModel(
            project_id=proj.id, key="speed", label="速度", param_type="number",
        ))
        await db_session.flush()

        db_session.add(ParameterModel(
            project_id=proj.id, key="speed", label="重复速度", param_type="number",
        ))
        with pytest.raises(Exception):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_parameter_default_values(self, db_session: AsyncSession):
        """参数默认值。"""
        proj = await self._create_project(db_session)
        p = ParameterModel(
            project_id=proj.id, key="test", label="测试", param_type="number",
        )
        db_session.add(p)
        await db_session.flush()

        result = await db_session.execute(
            select(ParameterModel).where(ParameterModel.key == "test")
        )
        fetched = result.scalar_one()
        assert fetched.visibility == "student"
        assert fetched.recompute_scope == "all_frames"


# ============================================================================
# Feedback
# ============================================================================


class TestFeedbackCRUD:
    """反馈 CRUD 操作测试。"""

    async def _create_project(self, db_session: AsyncSession) -> Project:
        p = Project(title="反馈测试项目")
        db_session.add(p)
        await db_session.flush()
        return p

    @pytest.mark.asyncio
    async def test_create_feedback(self, db_session: AsyncSession):
        """创建反馈。"""
        proj = await self._create_project(db_session)
        f = Feedback(
            project_id=proj.id,
            type="correction",
            content="旋转方向画反了",
            resolved=False,
        )
        db_session.add(f)
        await db_session.flush()

        result = await db_session.execute(
            select(Feedback).where(Feedback.project_id == proj.id)
        )
        items = result.scalars().all()
        assert len(items) == 1
        assert items[0].type == "correction"
        assert items[0].content == "旋转方向画反了"

    @pytest.mark.asyncio
    async def test_feedback_with_rating(self, db_session: AsyncSession):
        """评分反馈。"""
        proj = await self._create_project(db_session)
        f = Feedback(
            project_id=proj.id,
            type="rating",
            content="很好",
            rating=5,
        )
        db_session.add(f)
        await db_session.flush()

        result = await db_session.execute(
            select(Feedback).where(Feedback.type == "rating")
        )
        fetched = result.scalar_one()
        assert fetched.rating == 5

    @pytest.mark.asyncio
    async def test_feedback_with_frame(self, db_session: AsyncSession):
        """关联到帧的反馈。"""
        proj = await self._create_project(db_session)
        frame = Frame(
            project_id=proj.id, version=1, frame_id="f_001",
            order_index=1, title="帧", narration="",
        )
        db_session.add(frame)
        await db_session.flush()

        f = Feedback(
            project_id=proj.id,
            frame_id=frame.id,
            type="correction",
            content="这帧的动画有问题",
        )
        db_session.add(f)
        await db_session.flush()

        result = await db_session.execute(
            select(Feedback).where(Feedback.frame_id == frame.id)
        )
        fetched = result.scalar_one()
        assert fetched.frame_id == frame.id

    @pytest.mark.asyncio
    async def test_feedback_resolved_flag(self, db_session: AsyncSession):
        """resolved 标记应正确切换。"""
        proj = await self._create_project(db_session)
        f = Feedback(
            project_id=proj.id, type="suggestion", content="建议",
        )
        db_session.add(f)
        await db_session.flush()

        f.resolved = True
        await db_session.flush()

        result = await db_session.execute(
            select(Feedback).where(Feedback.id == f.id)
        )
        fetched = result.scalar_one()
        assert fetched.resolved is True


# ============================================================================
# Version Management
# ============================================================================


class TestVersionManagement:
    """版本管理测试。"""

    async def _create_project(self, db_session: AsyncSession) -> Project:
        p = Project(title="版本测试项目")
        db_session.add(p)
        await db_session.flush()
        return p

    @pytest.mark.asyncio
    async def test_create_version(self, db_session: AsyncSession):
        """创建版本快照。"""
        proj = await self._create_project(db_session)
        v = ProjectVersion(
            project_id=proj.id,
            version=1,
            dsl_snapshot={"frames": [{"frame_id": "f_001"}]},
            change_summary="初始版本",
        )
        db_session.add(v)
        await db_session.flush()

        result = await db_session.execute(
            select(ProjectVersion).where(ProjectVersion.project_id == proj.id)
        )
        versions = result.scalars().all()
        assert len(versions) == 1
        assert versions[0].version == 1
        assert versions[0].change_summary == "初始版本"

    @pytest.mark.asyncio
    async def test_version_unique_constraint(self, db_session: AsyncSession):
        """同一 project_id + version 不能重复。"""
        proj = await self._create_project(db_session)
        db_session.add(ProjectVersion(
            project_id=proj.id, version=1,
            dsl_snapshot={"frames": []}, change_summary="v1",
        ))
        await db_session.flush()

        db_session.add(ProjectVersion(
            project_id=proj.id, version=1,
            dsl_snapshot={"frames": []}, change_summary="重复v1",
        ))
        with pytest.raises(Exception):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_version_ordering(self, db_session: AsyncSession):
        """版本应按版本号排序。"""
        proj = await self._create_project(db_session)
        for ver in [1, 2, 3]:
            db_session.add(ProjectVersion(
                project_id=proj.id, version=ver,
                dsl_snapshot={"frames": [{"frame_id": f"f_{ver:03d}"}]},
                change_summary=f"v{ver}",
            ))
        await db_session.flush()

        result = await db_session.execute(
            select(ProjectVersion)
            .where(ProjectVersion.project_id == proj.id)
            .order_by(ProjectVersion.version.desc())
        )
        versions = result.scalars().all()
        assert len(versions) == 3
        assert versions[0].version == 3
        assert versions[2].version == 1


# ============================================================================
# Source Material
# ============================================================================


class TestSourceMaterialCRUD:
    """素材 CRUD 测试。"""

    async def _create_project(self, db_session: AsyncSession) -> Project:
        p = Project(title="素材测试项目")
        db_session.add(p)
        await db_session.flush()
        return p

    @pytest.mark.asyncio
    async def test_create_material(self, db_session: AsyncSession):
        """创建素材记录。"""
        proj = await self._create_project(db_session)
        m = SourceMaterial(
            project_id=proj.id,
            type="pdf",
            filename="课件.pdf",
            content_text="图论基础...",
            size_bytes=102400,
            storage_path="/data/uploads/abc.pdf",
        )
        db_session.add(m)
        await db_session.flush()

        result = await db_session.execute(
            select(SourceMaterial).where(SourceMaterial.project_id == proj.id)
        )
        items = result.scalars().all()
        assert len(items) == 1
        assert items[0].type == "pdf"

    @pytest.mark.asyncio
    async def test_material_parsed_result(self, db_session: AsyncSession):
        """解析结果 JSON 存储。"""
        proj = await self._create_project(db_session)
        parsed = {"topics": ["图", "Dijkstra"], "raw_text": "图论..."}
        m = SourceMaterial(
            project_id=proj.id, type="pdf",
            filename="课件.pdf", parsed_result=parsed,
        )
        db_session.add(m)
        await db_session.flush()

        result = await db_session.execute(
            select(SourceMaterial).where(SourceMaterial.project_id == proj.id)
        )
        fetched = result.scalar_one()
        assert fetched.parsed_result is not None
        assert len(fetched.parsed_result["topics"]) == 2


# ============================================================================
# Export Job
# ============================================================================


class TestExportJobCRUD:
    """导出任务测试。"""

    async def _create_project(self, db_session: AsyncSession) -> Project:
        p = Project(title="导出测试项目")
        db_session.add(p)
        await db_session.flush()
        return p

    @pytest.mark.asyncio
    async def test_create_export_job(self, db_session: AsyncSession):
        """创建导出任务。"""
        proj = await self._create_project(db_session)
        job = ExportJobModel(
            project_id=proj.id,
            target="manim_video",
            status="queued",
            config={"quality": "h", "fps": 30},
            progress_pct=0.0,
        )
        db_session.add(job)
        await db_session.flush()

        result = await db_session.execute(
            select(ExportJobModel).where(ExportJobModel.project_id == proj.id)
        )
        jobs = result.scalars().all()
        assert len(jobs) == 1
        assert jobs[0].target == "manim_video"
        assert jobs[0].status == "queued"

    @pytest.mark.asyncio
    async def test_export_job_status_flow(self, db_session: AsyncSession):
        """导出任务状态流转。"""
        proj = await self._create_project(db_session)
        job = ExportJobModel(
            project_id=proj.id, target="manim_video",
            status="queued", progress_pct=0.0,
        )
        db_session.add(job)
        await db_session.flush()

        job.status = "rendering"
        job.progress_pct = 50.0
        await db_session.flush()

        job.status = "completed"
        job.progress_pct = 100.0
        job.completed_at = datetime.now(timezone.utc)
        await db_session.flush()

        result = await db_session.execute(
            select(ExportJobModel).where(ExportJobModel.id == job.id)
        )
        fetched = result.scalar_one()
        assert fetched.status == "completed"
        assert fetched.completed_at is not None


# ============================================================================
# Quality Report
# ============================================================================


class TestQualityReportCRUD:
    """质量报告测试。"""

    async def _create_project(self, db_session: AsyncSession) -> Project:
        p = Project(title="质量报告测试项目")
        db_session.add(p)
        await db_session.flush()
        return p

    @pytest.mark.asyncio
    async def test_create_quality_report(self, db_session: AsyncSession):
        """创建质量报告。"""
        proj = await self._create_project(db_session)
        qr = QualityReportModel(
            project_id=proj.id,
            version=1,
            scores={"correctness": 0.9, "clarity": 0.85},
            issues=[{"severity": "high", "description": "概念错误"}],
            suggestions=["修正第一帧"],
            is_blocking=True,
        )
        db_session.add(qr)
        await db_session.flush()

        result = await db_session.execute(
            select(QualityReportModel).where(QualityReportModel.project_id == proj.id)
        )
        reports = result.scalars().all()
        assert len(reports) == 1
        assert reports[0].is_blocking is True
        assert reports[0].scores["correctness"] == 0.9


# ============================================================================
# Transaction & Session
# ============================================================================


class TestTransactionBehavior:
    """事务与会话行为测试。"""

    @pytest.mark.asyncio
    async def test_bulk_insert(self, db_session: AsyncSession):
        """批量插入。"""
        for i in range(10):
            db_session.add(Project(title=f"批量{i}"))
        await db_session.flush()

        result = await db_session.execute(select(func.count(Project.id)))
        count = result.scalar()
        assert count == 10

    @pytest.mark.asyncio
    async def test_nullable_fields(self, db_session: AsyncSession):
        """可空字段应接受 None 值。"""
        p = Project(
            title="可空测试",
            topic=None,
            subject=None,
            course=None,
            owner_id=None,
        )
        db_session.add(p)
        await db_session.flush()

        result = await db_session.execute(
            select(Project).where(Project.title == "可空测试")
        )
        fetched = result.scalar_one()
        assert fetched.topic is None
        assert fetched.owner_id is None
