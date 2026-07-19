"""Phase 2 种子知识库数据完整性测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def seed_data() -> list[dict]:
    seed_path = Path(__file__).resolve().parent.parent / "data" / "seed_knowledge.json"
    return json.loads(seed_path.read_text(encoding="utf-8"))


class TestSeedDataIntegrity:
    """种子数据完整性验证。"""

    def test_exactly_22_entries(self, seed_data):
        assert len(seed_data) == 22, f"Expected 22, got {len(seed_data)}"

    def test_every_entry_has_required_fields(self, seed_data):
        for entry in seed_data:
            assert "concept" in entry, f"Missing 'concept' in {entry.get('id', '?')}"
            assert "content" in entry, f"Missing 'content' in {entry.get('concept', '?')}"
            assert "subject" in entry, f"Missing 'subject' in {entry.get('concept', '?')}"
            assert "difficulty" in entry, f"Missing 'difficulty' in {entry.get('concept', '?')}"
            assert "object_types" in entry, f"Missing 'object_types' in {entry.get('concept', '?')}"
            assert "animation_types" in entry, f"Missing 'animation_types' in {entry.get('concept', '?')}"

    def test_difficulty_range(self, seed_data):
        for entry in seed_data:
            assert 1 <= entry["difficulty"] <= 5, \
                f"Difficulty {entry['difficulty']} out of range for {entry['concept']}"

    def test_subject_values_valid(self, seed_data):
        valid_subjects = {
            "algorithm", "data_structure", "operating_system",
            "computer_network", "database", "software_engineering",
        }
        for entry in seed_data:
            assert entry["subject"] in valid_subjects, \
                f"Invalid subject '{entry['subject']}' for {entry['concept']}"

    def test_object_types_valid(self, seed_data):
        from schema.dsl import VisualObjectType
        valid_types = {vt.value for vt in VisualObjectType}
        for entry in seed_data:
            for ot in entry.get("object_types", []):
                assert ot in valid_types, \
                    f"Invalid object_type '{ot}' in {entry['concept']}"

    def test_animation_types_valid(self, seed_data):
        from schema.dsl import AnimationType
        valid = {at.value for at in AnimationType}
        for entry in seed_data:
            for at in entry.get("animation_types", []):
                assert at in valid, \
                    f"Invalid animation_type '{at}' in {entry['concept']}"

    def test_no_duplicate_concepts(self, seed_data):
        concepts = [e["concept"] for e in seed_data]
        duplicates = [c for c in concepts if concepts.count(c) > 1]
        assert len(set(duplicates)) == 0, f"Duplicate concepts: {set(duplicates)}"

    def test_content_not_empty(self, seed_data):
        for entry in seed_data:
            assert len(entry["content"]) > 50, \
                f"Content too short for {entry['concept']}: {len(entry['content'])} chars"

    def test_subject_coverage(self, seed_data):
        """确保 6 个学科分类都有覆盖。"""
        subjects = {e["subject"] for e in seed_data}
        expected = {
            "algorithm", "data_structure", "operating_system",
            "computer_network", "database", "software_engineering",
        }
        missing = expected - subjects
        assert not missing, f"Missing subjects: {missing}"

    def test_subject_distribution(self, seed_data):
        """统计各学科条目数。"""
        from collections import Counter
        counts = Counter(e["subject"] for e in seed_data)
        # 算法至少 5 条
        assert counts.get("algorithm", 0) >= 5
        # 数据结构至少 3 条
        assert counts.get("data_structure", 0) >= 3
        # 每个学科至少 1 条
        for subject in counts:
            assert counts[subject] >= 1, f"Subject {subject} has only {counts[subject]} entries"

    def test_difficulty_distribution(self, seed_data):
        """确保包含从简单到困难的知识点。"""
        difficulties = {e["difficulty"] for e in seed_data}
        assert 1 in difficulties or 2 in difficulties, "Should have easy topics"
        assert 3 in difficulties, "Should have intermediate topics"
        assert 4 in difficulties, "Should have hard topics"


class TestConceptCoverage:
    """核心 CS 知识点覆盖检查。"""

    def test_essential_algorithms(self, seed_data):
        concepts = {e["concept"] for e in seed_data}
        must_have = ["冒泡排序", "快速排序", "归并排序", "二分查找", "动态规划", "Dijkstra最短路径算法"]
        for c in must_have:
            assert c in concepts, f"Missing essential concept: {c}"

    def test_essential_data_structures(self, seed_data):
        concepts = {e["concept"] for e in seed_data}
        must_have = ["哈希表", "二叉树与AVL树", "栈与队列", "红黑树插入"]
        for c in must_have:
            assert c in concepts, f"Missing essential DS concept: {c}"

    def test_essential_os(self, seed_data):
        concepts = {e["concept"] for e in seed_data}
        must_have = ["进程调度", "死锁", "同步与互斥", "分页与虚拟内存"]
        for c in must_have:
            assert c in concepts, f"Missing essential OS concept: {c}"

    def test_essential_network(self, seed_data):
        concepts = {e["concept"] for e in seed_data}
        must_have = ["TCP三次握手", "HTTP协议"]
        for c in must_have:
            assert c in concepts, f"Missing essential network concept: {c}"

    def test_essential_database(self, seed_data):
        concepts = {e["concept"] for e in seed_data}
        must_have = ["数据库索引与B+树", "数据库事务与隔离级别"]
        for c in must_have:
            assert c in concepts, f"Missing essential DB concept: {c}"

    def test_essential_se(self, seed_data):
        concepts = {e["concept"] for e in seed_data}
        must_have = ["设计模式"]
        for c in must_have:
            assert c in concepts, f"Missing essential SE concept: {c}"
