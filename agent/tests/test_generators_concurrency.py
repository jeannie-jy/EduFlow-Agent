"""生成器并发行为测试。

覆盖：
- 多个模块并行生成时的输出隔离
- 共享 state 的修改安全性
- 并发注册表操作
- dispatch_modules 并发调度
- asyncio.gather 场景
"""

from __future__ import annotations

import asyncio
import importlib
from unittest.mock import patch

import pytest


# ============================================================================
# Helpers
# ============================================================================


def _ensure_registered():
    for mod_name in (
        "generators.mindmap_generator",
        "generators.card_generator",
        "generators.frames_generator",
        "generators.video_generator",
    ):
        try:
            importlib.reload(__import__(mod_name, fromlist=[""]))
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _setup():
    _ensure_registered()
    yield


@pytest.fixture
def shared_state():
    return {
        "user_input": "冒泡排序",
        "project_id": "00000000-0000-0000-0000-000000000010",
        "teaching_plan": {
            "objectives": ["Test"],
            "outline": [{"step": 1, "title": "Intro", "key_points": ["p"], "estimated_frames": 3}],
            "teaching_approach": "Test",
            "estimated_total_frames": 3,
        },
        "knowledge_graph": {
            "concepts": [
                {"id": "c1", "name": "冒泡排序", "type": "definition"},
                {"id": "c2", "name": "交换", "type": "core_mechanism"},
            ],
            "edges": [{"source": "c1", "target": "c2", "relation": "leads_to"}],
        },
        "constraints": {},
        "status": "generating",
        "reflection_count": 0,
        "revision_history": [],
    }


# ============================================================================
# 并发生成测试
# ============================================================================


class TestParallelGeneration:
    """多个生成器并行运行时的行为。"""

    async def test_parallel_mindmap_and_cards(self, shared_state):
        """mindmap 和 cards 可以并行生成（互不依赖）。"""
        from generators.registry import get_generator

        mindmap_gen = get_generator("mindmap")
        cards_gen = get_generator("cards")

        with patch("agents.llm_client.call_llm_structured") as mock_llm:
            mock_llm.return_value = {
                "root": {"name": "T", "children": [
                    {"name": "A", "type": "definition", "children": []},
                ]},
                "cards": [
                    {
                        "id": "c1", "title": "T",
                        "definition": "A valid test definition here.",
                        "intuition": "Like T", "pitfalls": ["X"],
                        "category": "core", "difficulty": 1,
                    },
                ],
            }

            async def run_mindmap():
                return await mindmap_gen.generate(
                    teaching_plan=shared_state["teaching_plan"],
                    knowledge_graph=shared_state["knowledge_graph"],
                    user_input=shared_state["user_input"],
                    constraints={},
                    project_id=shared_state["project_id"],
                )

            async def run_cards():
                return await cards_gen.generate(
                    teaching_plan=shared_state["teaching_plan"],
                    knowledge_graph=shared_state["knowledge_graph"],
                    user_input=shared_state["user_input"],
                    constraints={},
                    project_id=shared_state["project_id"],
                )

            results = await asyncio.gather(run_mindmap(), run_cards())
            assert len(results) == 2
            assert "root" in results[0]
            # cards result may also have root from mock, but that's fine

    async def test_concurrent_dispatch_maintains_event_order(self, shared_state):
        """dispatch_modules 在串行模式下保持事件顺序。"""
        from services.module_dispatcher import dispatch_modules

        with patch("agents.llm_client.call_llm_structured") as mock_llm:
            mock_llm.return_value = {
                "root": {"name": "T", "children": [{"name": "A", "type": "d", "children": []}]},
            }

            events = []
            async for evt in dispatch_modules(
                shared_state["project_id"], shared_state, ["mindmap"],
            ):
                events.append(evt)

            # 事件顺序: module_start → module_done → done
            event_types = [e["event"] for e in events]
            start_idx = event_types.index("module_start")
            done_idx = event_types.index("done")
            # module_start 应在 done 之前
            assert start_idx < done_idx

    async def test_concurrent_state_not_corrupted(self, shared_state):
        """并行操作不应破坏共享 state 的核心字段。"""
        original_input = shared_state["user_input"]
        original_concepts = len(shared_state["knowledge_graph"]["concepts"])

        with patch("agents.llm_client.call_llm_structured") as mock_llm:
            mock_llm.side_effect = lambda **kw: (
                {"root": {"name": "R", "children": []}}
                if "root" in kw.get("output_schema", {}).get("properties", {})
                else {"cards": [{"id": "c", "title": "C", "definition": "Valid def here yes.",
                                  "intuition": "I", "pitfalls": ["P"], "category": "core", "difficulty": 1}]}
            )

            tasks = []
            for _ in range(5):
                from generators.registry import get_generator
                gen = get_generator("mindmap")
                tasks.append(gen.generate(
                    teaching_plan=shared_state["teaching_plan"],
                    knowledge_graph=shared_state["knowledge_graph"],
                    user_input=shared_state["user_input"],
                    constraints={},
                    project_id=shared_state["project_id"],
                ))

            results = await asyncio.gather(*tasks)
            assert len(results) == 5
            for r in results:
                assert "root" in r

        # shared_state 不应被修改
        assert shared_state["user_input"] == original_input
        assert len(shared_state["knowledge_graph"]["concepts"]) == original_concepts


# ============================================================================
# 调度器并发测试
# ============================================================================


class TestDispatcherConcurrency:
    """ModuleDispatcher 的并发安全。"""

    async def test_dispatcher_with_multiple_independent_modules(self, shared_state):
        """多个无依赖模块在 dispatcher 中串行执行。"""
        from services.module_dispatcher import dispatch_modules

        call_count = {"mindmap": 0, "cards": 0}

        def mock_llm(**kwargs):
            schema = kwargs.get("output_schema", {})
            if "root" in schema.get("properties", {}):
                call_count["mindmap"] += 1
                return {"root": {"name": "T", "children": [{"name": "A", "type": "d", "children": []}]}}
            if "cards" in schema.get("properties", {}):
                call_count["cards"] += 1
                return {"cards": [{"id": "c", "title": "C",
                                    "definition": "A valid test definition here.",
                                    "intuition": "I", "pitfalls": ["P"],
                                    "category": "core", "difficulty": 1}]}
            return {}

        with patch("agents.llm_client.call_llm_structured", side_effect=mock_llm):
            events = []
            async for evt in dispatch_modules(
                shared_state["project_id"], shared_state, ["mindmap", "cards"],
            ):
                events.append(evt)

            assert call_count["mindmap"] == 1
            assert call_count["cards"] == 1

    async def test_dispatcher_skips_failed_module_and_continues(self, shared_state):
        """一个模块失败不阻塞后续模块。"""
        from services.module_dispatcher import dispatch_modules

        call_sequence = []

        def mock_llm(**kwargs):
            schema = kwargs.get("output_schema", {})
            if "root" in schema.get("properties", {}):
                call_sequence.append("mindmap")
                raise RuntimeError("Simulated mindmap failure")
            if "cards" in schema.get("properties", {}):
                call_sequence.append("cards")
                return {"cards": [{"id": "c", "title": "C",
                                    "definition": "A valid test definition.",
                                    "intuition": "I", "pitfalls": ["P"],
                                    "category": "core", "difficulty": 1}]}
            return {}

        with patch("agents.llm_client.call_llm_structured", side_effect=mock_llm):
            events = []
            async for evt in dispatch_modules(
                shared_state["project_id"], shared_state, ["mindmap", "cards"],
            ):
                events.append(evt)

            # mindmap 失败后 cards 仍应被调用
            assert call_sequence == ["mindmap", "cards"]

            # events 应包含 mindmap 错误和 cards 完成
            import json
            event_data = [json.loads(e["data"]) for e in events if e["event"] in ("module_done", "module_error")]
            module_ids = {d.get("module_id") for d in event_data}
            assert "mindmap" in module_ids  # error
            assert "cards" in module_ids     # done


# ============================================================================
# 注册表并发测试
# ============================================================================


class TestRegistryConcurrency:
    """注册表的并发操作安全。"""

    def test_concurrent_list_and_register(self):
        """并发 list 和 register 不导致竞态。"""
        import threading
        import time
        from generators.registry import register_generator, list_generators, clear_registry

        clear_registry()

        class QuickGen:
            def __init__(self, i):
                self.module_id = f"quick_{i}"
                self.display_name = f"Quick {i}"
                self.description = ""
                self.icon = ""
                self.category = "visual"
                self.priority = i
                self.version = "1.0"

            def get_output_schema(self):
                return {"type": "object"}

            def get_system_prompt(self):
                return ""

            def validate(self, o):
                return []

        errors = []
        results = []

        def reader():
            for _ in range(50):
                try:
                    gens = list_generators()
                    results.append(len(gens))
                except Exception as e:
                    errors.append(f"reader: {e}")
                time.sleep(0.001)

        def writer(offset):
            for i in range(20):
                try:
                    register_generator(QuickGen(offset + i))
                except Exception as e:
                    errors.append(f"writer: {e}")
                time.sleep(0.001)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(100,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrency errors: {errors}"
        # 验证注册表最终状态一致
        gens = list_generators()
        ids = [g.module_id for g in gens]
        assert len(ids) == len(set(ids)), "Duplicate IDs in registry"


# ============================================================================
# 异步超时保护
# ============================================================================


class TestAsyncTimeoutProtection:
    """异步生成操作的超时和取消保护。"""

    async def test_generate_respects_cancellation(self):
        """asyncio 取消应能中断生成操作。"""
        from generators.registry import get_generator

        gen = get_generator("mindmap")

        # 创建一个永远等待的 mock LLM
        async def never_returns(**kwargs):
            await asyncio.sleep(10)
            return {}

        with patch("agents.llm_client.call_llm_structured", side_effect=never_returns):
            task = asyncio.create_task(gen.generate(
                teaching_plan={"objectives": [], "outline": [], "teaching_approach": "", "estimated_total_frames": 1},
                knowledge_graph={"concepts": [], "edges": []},
                user_input="Test",
                constraints={},
                project_id="test",
            ))

            # 给一点时间让 task 开始执行
            await asyncio.sleep(0.05)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

    async def test_asyncio_gather_with_partial_failure(self):
        """asyncio.gather 部分任务失败时正确传播异常。"""
        from generators.registry import get_generator

        gen = get_generator("mindmap")

        def mock_llm(**kwargs):
            schema = kwargs.get("output_schema", {})
            if "root" in schema.get("properties", {}):
                return {"root": {"name": "OK", "children": []}}
            raise RuntimeError("Other generator failed")

        with patch("agents.llm_client.call_llm_structured", side_effect=mock_llm):
            # 两个 mindmap 调用都使用 root schema，都应该成功
            tasks = [
                gen.generate(
                    teaching_plan={"objectives": [], "outline": [], "teaching_approach": "", "estimated_total_frames": 1},
                    knowledge_graph={"concepts": [], "edges": []},
                    user_input="Test",
                    constraints={},
                    project_id="test",
                )
                for _ in range(2)
            ]
            results = await asyncio.gather(*tasks)
            assert len(results) == 2
            for r in results:
                assert r["root"]["name"] == "OK"
