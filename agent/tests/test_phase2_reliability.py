"""阶段 2 可靠性测试。

覆盖 v0.8 修复中的五组正确性保障：
1. manim_llm_adapter 字段白名单 — 图结构数据不再被剥光
2. dispatcher 全失败落库 — project.status 卡死与 module_errors 丢失问题
3. 生成器 validate 畸形输入 — LLM 输出非预期类型不再崩溃
4. frames 快照顶层提升 + resolve_export_dsl — 模块流项目可直接导出
5. Scene 幻觉方法确定性修复 — clear_current 等不存在方法渲染崩溃前置拦截
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from generators.registry import clear_registry, register_generator

# ============================================================================
# 1. manim_llm_adapter — visual_objects 字段白名单
# ============================================================================


class TestManimLLMAdapterWhitelist:
    """图结构数据（边/节点/根节点）必须完整传给 LLM。"""

    def _graph_dsl(self) -> dict:
        return {
            "topic": "Dijkstra 最短路径",
            "frames": [
                {
                    "frame_id": "f_001",
                    "title": "初始状态",
                    "narration": "展示图结构",
                    "state_snapshot": {"distances": {"a": 0}},
                    "visual_objects": [
                        {"id": "e1", "type": "edge", "source": "a", "target": "b",
                         "weight": 5, "directed": True},
                        {"id": "g1", "type": "graph",
                         "nodes": [{"id": "a"}, {"id": "b"}],
                         "edges": [{"source": "a", "target": "b", "weight": 5}]},
                        {"id": "m1", "type": "mindmap",
                         "root": {"name": "Dijkstra"}, "children": [{"name": "贪心"}]},
                    ],
                    "animations": [],
                }
            ],
        }

    def test_edge_fields_survive_whitelist(self):
        from adapters.manim_llm_adapter import _build_user_message

        msg = _build_user_message(self._graph_dsl(), None)
        assert '"source": "a"' in msg
        assert '"target": "b"' in msg
        assert '"weight": 5' in msg
        assert '"directed": true' in msg

    def test_graph_and_mindmap_structure_survive(self):
        from adapters.manim_llm_adapter import _build_user_message

        msg = _build_user_message(self._graph_dsl(), None)
        assert '"edges"' in msg
        assert '"nodes"' in msg
        assert '"root"' in msg
        assert '"children"' in msg


class TestSceneMethodFixes:
    """LLM 幻觉的 Scene 方法名确定性修复（clear_current → clear）。"""

    def test_clear_current_replaced(self):
        from adapters.manim_llm_adapter import _fix_scene_methods

        code = (
            "        formula_intro.next_to(graph, DOWN, buff=0.6)\n"
            "        self.clear_current()\n"
            "        self.play(FadeIn(graph))"
        )
        fixed = _fix_scene_methods(code)
        assert "self.clear()" in fixed
        assert "clear_current" not in fixed
        assert "self.play(FadeIn(graph))" in fixed

    def test_real_scene_methods_untouched(self):
        from adapters.manim_llm_adapter import _fix_scene_methods

        code = "self.play(FadeIn(t))\nself.wait(1)\nself.clear()"
        assert _fix_scene_methods(code) == code


# ============================================================================
# 2. dispatcher — 全模块失败落库
# ============================================================================


class _AlwaysFailGen:
    module_id = "always_fail"
    display_name = "Always Fail"
    description = "Always fails"
    icon = "fail"
    category = "visual"
    priority = 1
    version = "1.0.0"

    async def generate(self, **kwargs):
        raise RuntimeError("Simulated failure")

    def validate(self, output):
        return []

    def get_output_schema(self):
        return {"type": "object"}

    def get_system_prompt(self):
        return "Failing."


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


PROJECT_ID = "00000000-0000-0000-0000-000000000001"  # 合法 UUID（parse_project_id 要求）


def _make_state():
    return {
        "user_input": "Test topic",
        "project_id": PROJECT_ID,
        "teaching_plan": {"objectives": ["o1"], "outline": []},
        "knowledge_graph": {"concepts": [{"id": "c1", "name": "C", "type": "definition"}], "edges": []},
        "constraints": {},
        "status": "generating",
        "reflection_count": 0,
        "revision_history": [],
    }


class TestDispatchFailurePersistence:
    """全模块失败时 project.status 必须落 failed，module_errors 必须落库。"""

    async def test_all_failed_persists_failed_status_and_errors(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_AlwaysFailGen())

        # mock DB：async_session_factory 返回带 mock project 的 session
        mock_project = MagicMock()
        mock_project.dsl_snapshot = {}
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_project)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("db.database.async_session_factory", return_value=mock_cm):
            events = []
            async for evt in dispatch_modules(PROJECT_ID, _make_state(), ["always_fail"]):
                events.append(evt)

        # 状态机：无产出 + 有错误 → failed
        assert mock_project.status == "failed"
        snapshot = mock_project.dsl_snapshot
        assert "module_errors" in snapshot
        assert "always_fail" in snapshot["module_errors"]

        # done 事件携带错误信息
        last = events[-1]
        assert last["event"] == "done"
        import json
        payload = json.loads(last["data"])
        assert payload["module_errors"] is not None

    async def test_success_persists_done_status(self):
        from services.module_dispatcher import dispatch_modules

        class _OkGen:
            module_id = "always_ok"
            display_name = "Always OK"
            description = "OK"
            icon = "ok"
            category = "visual"
            priority = 1
            version = "1.0.0"

            async def generate(self, **kwargs):
                return {"status": "ok"}

            def validate(self, output):
                return []

            def get_output_schema(self):
                return {"type": "object"}

            def get_system_prompt(self):
                return "OK."

        register_generator(_OkGen())

        mock_project = MagicMock()
        mock_project.dsl_snapshot = {}
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_project)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("db.database.async_session_factory", return_value=mock_cm),
            patch("api.versions.save_version", new=AsyncMock()) as save_version,
        ):
            async for _ in dispatch_modules(PROJECT_ID, _make_state(), ["always_ok"]):
                pass

        assert mock_project.status == "done"
        assert "module_outputs" in mock_project.dsl_snapshot
        save_version.assert_awaited_once()


# ============================================================================
# 3. 生成器 validate — 畸形 LLM 输出
# ============================================================================


class TestGeneratorValidateMalformed:
    """LLM 返回非 dict 元素/非字符串时，validate 不得抛异常。"""

    @pytest.mark.parametrize("module_id,output,expected_issue_type", [
        ("frames", {
            "frames": [
                "not-a-dict-frame",
                {"frame_id": "f_001", "title": "t", "narration": "n", "visual_objects": []},
            ],
        }, "invalid_frame_object"),
        ("mindmap", {"root": "not-a-dict-root"}, "invalid_root"),
        ("cards", {
            "cards": [
                42,
                {"id": "c1", "title": "t", "definition": "d", "intuition": "i", "pitfalls": []},
            ],
        }, "invalid_card_object"),
        ("comparison", {
            "topic": "对比",
            "algorithms": [
                None,
                {"name": "A", "pros": ["p1", "p2"], "cons": ["c1"], "description": "d"},
            ],
            "dimensions": ["时间复杂度", "空间复杂度"],
            "comparison_table": [],
            "scenario_analysis": "这是一段足够长的场景分析文本，用于通过长度校验。",
        }, "invalid_algo_object"),
        ("interactive_demo", {"code": {"not": "a string"}}, "invalid_code_type"),
    ])
    @pytest.mark.asyncio
    async def test_malformed_input_no_crash(self, module_id, output, expected_issue_type):
        import importlib

        import generators.card_generator
        import generators.comparison_generator
        import generators.frames_generator
        import generators.interactive_demo_generator

        # autouse fixture 在每个测试前 clear_registry()，
        # 因此需要 reload 模块重新触发 register_generator（模块级 import 有缓存）
        import generators.mindmap_generator
        from generators.registry import get_generator

        for mod in (generators.mindmap_generator, generators.card_generator,
                    generators.frames_generator, generators.comparison_generator,
                    generators.interactive_demo_generator):
            importlib.reload(mod)

        gen = get_generator(module_id)
        assert gen is not None, f"generator {module_id} 未注册"

        # 不应抛异常
        issues = gen.validate(output)
        assert any(i.get("type") == expected_issue_type for i in issues), \
            f"期望 issue type={expected_issue_type}，实际: {[i.get('type') for i in issues]}"


# ============================================================================
# 4. frames 快照顶层提升 + resolve_export_dsl — 模块流项目可直接导出
# ============================================================================


class _FramesGen:
    """产出完整 DSL 的 frames 模块（模拟 frames_generator）。"""

    module_id = "frames"
    display_name = "推演脚本"
    description = "Mock frames"
    icon = "frames"
    category = "visual"
    priority = 1
    version = "1.0.0"

    async def generate(self, **kwargs):
        return {
            "topic": "Test topic",
            "frames": [{"frame_id": "f_001", "title": "初始", "narration": "n"}],
            "parameters": [{"id": "speed", "label": "速度", "value": 1.0}],
            "artifact_version": "abcd1234abcd",
            "schema_version": "1.0",
        }

    def validate(self, output):
        return []

    def get_output_schema(self):
        return {"type": "object"}

    def get_system_prompt(self):
        return "OK."


class TestFramesSnapshotPromotion:
    """模块流的 frames 产出必须提升到 dsl_snapshot 顶层（导出 API 读取处）。"""

    async def test_dispatch_promotes_frames_to_snapshot_top_level(self):
        from services.module_dispatcher import dispatch_modules

        register_generator(_FramesGen())

        mock_project = MagicMock()
        mock_project.dsl_snapshot = {}
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_project)
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("db.database.async_session_factory", return_value=mock_cm):
            async for _ in dispatch_modules(PROJECT_ID, _make_state(), ["frames"]):
                pass

        snapshot = mock_project.dsl_snapshot
        assert mock_project.status == "done"
        # frames 完整 DSL 提升到顶层，导出 API 不再 400
        assert snapshot["frames"] == [
            {"frame_id": "f_001", "title": "初始", "narration": "n"}
        ]
        assert snapshot["parameters"][0]["id"] == "speed"
        assert snapshot["artifact_version"] == "abcd1234abcd"
        assert snapshot["topic"] == "Test topic"
        # module_outputs.frames 仅保留不可变版本引用，不再重复存整组帧。
        frames_output = snapshot["module_outputs"]["frames"]
        assert "frames" not in frames_output
        assert frames_output["artifact_ref"]["type"] == "project_version_frames"
        uuid.UUID(frames_output["artifact_ref"]["version_id"])

        # frames 表同步写入（persist_frames_to_table 内 session.add(Frame)）
        added_frame_ids = [
            c.args[0].frame_id
            for c in mock_session.add.call_args_list
            if c.args and hasattr(c.args[0], "frame_id")
        ]
        assert "f_001" in added_frame_ids


class TestResolveExportDsl:
    """resolve_export_dsl 兼容顶层 frames 与 module_outputs.frames 两种快照形态。"""

    def test_top_level_frames_returned_as_is(self):
        from services.project_persistence import resolve_export_dsl

        snap = {"frames": [{"frame_id": "f_001"}], "topic": "T"}
        assert resolve_export_dsl(snap) is snap

    def test_module_outputs_frames_fallback_merged(self):
        from services.project_persistence import resolve_export_dsl

        snap = {
            "topic": "T",
            "module_outputs": {
                "frames": {
                    "topic": "T2",
                    "frames": [{"frame_id": "f_001"}],
                    "parameters": [{"id": "p1"}],
                    "artifact_version": "abcd1234abcd",
                }
            },
        }
        resolved = resolve_export_dsl(snap)
        assert resolved is not None
        assert resolved["frames"] == [{"frame_id": "f_001"}]
        # module_outputs.frames 是完整 DSL → 合并后补齐导出所需字段
        assert resolved["parameters"][0]["id"] == "p1"
        assert resolved["artifact_version"] == "abcd1234abcd"
        # 顶层字段保留，frames 产出字段优先
        assert resolved["topic"] == "T2"
        assert resolved["module_outputs"]["frames"]["frames"]

    def test_returns_none_when_no_frames_anywhere(self):
        from services.project_persistence import resolve_export_dsl

        assert resolve_export_dsl(None) is None
        assert resolve_export_dsl({}) is None
        assert resolve_export_dsl({"frames": []}) is None
        assert resolve_export_dsl({"module_outputs": {"frames": {"frames": []}}}) is None

    def test_skipped_frames_output_not_used(self):
        from services.project_persistence import resolve_export_dsl

        assert resolve_export_dsl(
            {"module_outputs": {"frames": {"status": "skipped"}}}
        ) is None

    async def test_active_reads_overlay_snapshot_caches_from_frame_table(self):
        from types import SimpleNamespace

        from services.project_persistence import load_canonical_project_dsl

        old = {"frame_id": "f_001", "title": "stale"}
        snapshot = {
            "frames": [old],
            "module_outputs": {
                "frames": {
                    "schema_version": "1.0",
                    "artifact_ref": {
                        "type": "project_version_frames",
                        "version_id": str(uuid.uuid4()),
                    },
                }
            },
        }
        project = SimpleNamespace(id=uuid.uuid4(), dsl_snapshot=snapshot)
        row = SimpleNamespace(
            frame_id="f_001",
            title="edited",
            learning_goal="goal",
            narration="new narration",
            visual_objects=[],
            state_snapshot={"step": 2},
            animations=[],
            interaction_hooks=[],
            checks=[],
            quality_status="ok",
            is_locked=True,
        )
        scalar_result = MagicMock()
        scalar_result.all.return_value = [row]
        result = MagicMock()
        result.scalars.return_value = scalar_result
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)

        canonical = await load_canonical_project_dsl(project, session)

        assert canonical["frames"][0]["title"] == "edited"
        assert canonical["frames"][0]["is_locked"] is True
        assert canonical["module_outputs"]["frames"]["frames"] == canonical["frames"]
        assert snapshot["frames"][0]["title"] == "stale"


class TestFramesArtifactReference:
    def test_compacts_duplicate_frames_without_mutating_input(self):
        from services.project_persistence import compact_frames_artifact_reference

        version_id = uuid.uuid4()
        source = {
            "frames": [{"frame_id": "f_001"}],
            "module_outputs": {
                "frames": {
                    "frames": [{"frame_id": "f_001"}],
                    "schema_version": "1.0",
                    "artifact_version": "abc123",
                },
                "quiz": {"questions": []},
            },
        }

        compacted = compact_frames_artifact_reference(source, version_id)

        assert compacted["frames"] == source["frames"]
        assert compacted["module_outputs"]["quiz"] == {"questions": []}
        frames_output = compacted["module_outputs"]["frames"]
        assert "frames" not in frames_output
        assert frames_output["schema_version"] == "1.0"
        assert frames_output["artifact_version"] == "abc123"
        assert frames_output["artifact_ref"] == {
            "type": "project_version_frames",
            "version_id": str(version_id),
        }
        assert source["module_outputs"]["frames"]["frames"] == [
            {"frame_id": "f_001"}
        ]

    def test_rebinds_an_existing_reference_to_the_new_version(self):
        from services.project_persistence import compact_frames_artifact_reference

        old_version_id = uuid.uuid4()
        new_version_id = uuid.uuid4()
        source = {
            "frames": [{"frame_id": "f_001"}],
            "module_outputs": {
                "frames": {
                    "schema_version": "1.0",
                    "artifact_ref": {
                        "type": "project_version_frames",
                        "version_id": str(old_version_id),
                    },
                }
            },
        }

        compacted = compact_frames_artifact_reference(source, new_version_id)

        assert compacted["module_outputs"]["frames"]["artifact_ref"] == {
            "type": "project_version_frames",
            "version_id": str(new_version_id),
        }
        assert source["module_outputs"]["frames"]["artifact_ref"][
            "version_id"
        ] == str(old_version_id)
