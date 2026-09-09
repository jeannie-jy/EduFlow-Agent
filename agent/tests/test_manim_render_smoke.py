"""真实渲染 smoke 测试 — 验证「视频导出」整条工具链（manim CLI + cairo + ffmpeg）。

Golden 脚本按 DSL 可视化类型各一（array/table/code_block/formula/graph），
均不含 LaTeX 与 CJK（与项目「无 LaTeX」约束一致）。

本地运行（需安装 manim + ffmpeg）：
    python -m pytest tests/test_manim_render_smoke.py -m render -v

CI：.github/workflows/backend-ci.yml 的 render-smoke job（安装完整
requirements.txt + 系统库）执行本文件。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from adapters.manim_validator import has_errors, validate_script

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "manim_golden"

pytestmark = pytest.mark.render


def _golden_scripts() -> list[Path]:
    return sorted(GOLDEN_DIR.glob("*.py"), key=lambda p: p.name)


def test_golden_scripts_pass_project_validator():
    """golden 脚本必须通过项目自身校验器 —— 防止 validator 误伤可渲染路径。"""
    pytest.importorskip("manim")
    assert _golden_scripts(), "未找到 golden 脚本"
    for script in _golden_scripts():
        issues = validate_script(script.read_text(encoding="utf-8"))
        assert not has_errors(issues), f"{script.name}: {issues}"


@pytest.mark.parametrize("script_path", _golden_scripts(), ids=lambda p: p.stem)
def test_golden_script_renders_mp4(script_path: Path, tmp_path):
    pytest.importorskip("manim")
    result = subprocess.run(
        [sys.executable, "-m", "manim", str(script_path), "-ql",
         "--format=mp4", f"--media_dir={tmp_path}"],
        capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, (
        f"{script_path.name} 渲染失败:\n{result.stderr[-3000:]}"
    )
    mp4s = [
        p for p in tmp_path.rglob("*.mp4")
        if "partial_movie_files" not in str(p)
    ]
    assert mp4s, f"{script_path.name} 渲染完成但未产出 MP4"
    assert max(p.stat().st_size for p in mp4s) > 0, f"{script_path.name} 的 MP4 为空文件"
