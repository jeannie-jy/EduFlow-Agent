"""Manim adapter 自测 — 不经过 HTTP，直接验证脚本生成和渲染。

用法:
  python test_adapter.py                        # 用内置 SAMPLE_DSL 自测
  python test_adapter.py --render               # 自测 + 实际 Manim 渲染验证
  python test_adapter.py --all-types            # 覆盖所有 visual_objects 类型
  python test_adapter.py path/to/dsl.json       # 检测外部 DSL 文件
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 确保可以 import adapters
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.manim_adapter import convert_dsl_to_manim, _HAS_LATEX, _find_ffmpeg, _has_cjk
from adapters.manim_validator import validate_script, has_errors

# ═══════════════════════════════════════════════════════════════
# Test DSLs
# ═══════════════════════════════════════════════════════════════

SAMPLE_DSL = {
    "project_id": "test",
    "topic": "测试",
    "frames": [
        {
            "frame_id": "f_001",
            "title": "测试帧",
            "narration": "测试讲解",
            "visual_objects": [
                {"id": "node1", "type": "node", "label": "A", "position": {"x": 100, "y": 200}},
                {"id": "formula1", "type": "formula", "latex": "E=mc^2"},
                {"id": "formula2", "type": "formula", "latex": "\\text{升序排列}"},
                {"id": "code1", "type": "code_block", "code": "for i in range(n):\n    print(i)", "language": "pseudocode"},
                {"id": "table1", "type": "table", "headers": ["节点", "距离"], "rows": [["A", "0"], ["B", "3"]]},
            ],
            "animations": [
                {"type": "appear", "target": "node1", "duration_ms": 500},
                {"type": "highlight", "target": "node1", "duration_ms": 300},
            ],
            "state_snapshot": {},
        },
    ],
    "parameters": [],
}

# 覆盖所有 visual_objects 类型
ALL_TYPES_DSL = {
    "project_id": "all_types_test",
    "topic": "全类型测试",
    "frames": [
        {
            "frame_id": "f_001",
            "title": "全部类型",
            "narration": "全类型覆盖测试",
            "visual_objects": [
                {"id": "n", "type": "node", "label": "A", "position": {"x": 50, "y": 100}},
                {"id": "e", "type": "edge", "label": "5", "position": {"x": 300, "y": 100},
                 "directed": True},
                {"id": "e2", "type": "edge", "label": "2", "position": {"x": 300, "y": 250},
                 "directed": False},
                {"id": "arr", "type": "array", "label": "[0,1,2]", "position": {"x": 100, "y": 300}},
                {"id": "ll", "type": "linked_list", "label": "head", "position": {"x": 500, "y": 100}},
                {"id": "tbl", "type": "table", "headers": ["Key", "Val"],
                 "rows": [["a", "1"], ["b", "2"]], "position": {"x": 300, "y": 400}},
                {"id": "cd", "type": "code_block", "code": "def foo():\n    pass",
                 "language": "python", "position": {"x": 500, "y": 300}},
                {"id": "mem", "type": "memory_block", "label": "0x1000",
                 "position": {"x": 100, "y": 500}},
                {"id": "proc", "type": "process", "label": "sort()",
                 "position": {"x": 500, "y": 500}},
                {"id": "tl", "type": "timeline", "position": {"x": 300, "y": 600}},
                {"id": "fm", "type": "formula", "latex": "O(n\\log n)",
                 "position": {"x": 100, "y": 650}},
                {"id": "cd2", "type": "card", "label": "result",
                 "position": {"x": 500, "y": 650}},
            ],
            "animations": [
                {"type": "appear", "target": "n", "duration_ms": 300},
                {"type": "appear", "target": "tbl", "duration_ms": 300},
                {"type": "disappear", "target": "n", "duration_ms": 300},
                {"type": "highlight", "target": "cd", "duration_ms": 300},
            ],
            "state_snapshot": {},
        },
    ],
    "parameters": [],
}

# ── 渲染专用：最小 DSL（不含 formula/MathTex，避免 LaTeX 依赖）──
MINIMAL_RENDER_DSL = {
    "project_id": "render_test",
    "topic": "渲染测试",
    "frames": [
        {
            "frame_id": "f_001",
            "title": "渲染验证",
            "narration": "",
            "visual_objects": [
                {"id": "node1", "type": "node", "label": "Root",
                 "position": {"x": 300, "y": 200}},
                {"id": "node2", "type": "node", "label": "Child",
                 "position": {"x": 100, "y": 400}},
                {"id": "edge1", "type": "edge",
                 "position": {"x": 200, "y": 300}, "directed": True},
            ],
            "animations": [
                {"type": "appear", "target": "node1", "duration_ms": 300},
                {"type": "appear", "target": "node2", "duration_ms": 300},
                {"type": "appear", "target": "edge1", "duration_ms": 300},
                {"type": "highlight", "target": "node1", "duration_ms": 200},
            ],
            "state_snapshot": {},
        },
    ],
    "parameters": [],
}


# ═══════════════════════════════════════════════════════════════
# 代码质量测试
# ═══════════════════════════════════════════════════════════════


def test_generate(dsl: dict) -> dict:
    """DSL → Manim 脚本生成。"""
    files = convert_dsl_to_manim(dsl)
    assert "main.py" in files, "缺少 main.py"
    assert "render_config.json" in files, "缺少 render_config.json"
    assert "subtitles.srt" in files, "缺少 subtitles.srt"
    return files


def test_syntax(main_py: str) -> None:
    """生成脚本 Python 语法合法。"""
    try:
        ast.parse(main_py)
    except SyntaxError as e:
        _print_error_context(main_py, e.lineno or 1, str(e))
        raise


def test_validator(main_py: str) -> list[dict]:
    """校验器检测已知问题。"""
    issues = validate_script(main_py)
    if has_errors(issues):
        for i in issues:
            if i["severity"] == "error":
                raise AssertionError(f"[{i['rule']}] L{i['line']}: {i['detail']}")
    return issues


def test_no_mathtex_cjk(main_py: str) -> None:
    """MathTex 不含 CJK 字符（与 validator CJK 检测范围一致）。"""
    if "MathTex" in main_py:
        for m in __import__("re").finditer(r"MathTex\(([^)]+)\)", main_py):
            for ch in m.group(1):
                if _has_cjk(ch):
                    raise AssertionError(f"MathTex 含 CJK: {m.group(1)[:80]}")


def test_no_pseudocode(main_py: str) -> None:
    """language='pseudocode' 已降级。"""
    if "language='pseudocode'" in main_py:
        raise AssertionError("pseudocode 未降级为 text")


def test_code_api(main_py: str) -> None:
    """使用 code_string= 而非 code=。"""
    if "Code(code='" in main_py or 'Code(code="' in main_py:
        raise AssertionError("Code 仍使用 code=，应为 code_string=")


def test_no_mathtex_without_latex(main_py: str) -> None:
    """LaTeX 不可用时，脚本不应使用 MathTex。"""
    if not _HAS_LATEX and "MathTex(" in main_py:
        raise AssertionError("LaTeX 未安装但脚本包含 MathTex，应回退为 Text")


# ═══════════════════════════════════════════════════════════════
# 渲染测试
# ═══════════════════════════════════════════════════════════════


def test_render(dsl: dict | None = None, timeout: int = 120) -> str | None:
    """用 Manim 实际渲染生成的脚本，验证产出 MP4。

    Returns: 输出 MP4 路径，失败返回 None。
    """
    if dsl is None:
        dsl = MINIMAL_RENDER_DSL

    files = convert_dsl_to_manim(dsl)
    main_py = files["main.py"]

    tmpdir = Path(tempfile.mkdtemp(prefix="manim_test_"))
    script_path = tmpdir / "main.py"
    script_path.write_text(main_py, encoding="utf-8")

    env = os.environ.copy()
    # 注入 ffmpeg PATH
    ffmpeg_dir = _find_ffmpeg()
    if ffmpeg_dir:
        env["PATH"] = ffmpeg_dir + os.pathsep + env.get("PATH", "")

    print(f"  渲染中: {script_path}")
    result = subprocess.run(
        [sys.executable, "-m", "manim", str(script_path),
         "-ql", "--fps=15", "--format=mp4", f"--media_dir={tmpdir}"],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(tmpdir), env=env,
    )

    if result.returncode != 0:
        print(f"  [FAIL] Manim 返回码={result.returncode}")
        stderr_tail = result.stderr.strip().split("\n")[-10:]
        for line in stderr_tail:
            print(f"    {line}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None

    # 搜索产物
    mp4_files = list(tmpdir.rglob("*.mp4"))
    mp4_files = [m for m in mp4_files if "partial_movie_files" not in str(m)]

    if not mp4_files:
        print(f"  [FAIL] 渲染完成但未找到 MP4")
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None

    mp4 = mp4_files[0]
    size_kb = mp4.stat().st_size / 1024
    print(f"  [OK] 渲染成功: {mp4.name} ({size_kb:.1f} KB)")

    # 清理（保留文件路径返回）
    result_path = str(mp4)
    return result_path


# ═══════════════════════════════════════════════════════════════
# DSL 文件检测
# ═══════════════════════════════════════════════════════════════


def check_dsl_file(dsl_path: str) -> int:
    """检测单个 DSL JSON 文件，打印报告，返回问题数。"""
    print(f"\n{'='*60}")
    print(f"检测: {dsl_path}")

    try:
        with open(dsl_path, "r", encoding="utf-8") as f:
            dsl = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[FATAL] 无法读取 DSL: {e}")
        return 1

    frames = dsl.get("frames", [])
    print(f"  项目: {dsl.get('topic', 'unknown')} | 帧数: {len(frames)}")

    files = convert_dsl_to_manim(dsl)
    main_py = files["main.py"]

    issues = validate_script(main_py)
    if not issues:
        print(f"  [OK] 校验通过，无问题")
        return 0

    errors = [i for i in issues if i["severity"] == "error"]
    warns = [i for i in issues if i["severity"] == "warn"]

    for i in errors:
        print(f"  [ERROR] {i['rule']} L{i['line']}: {i['detail']}")
    for i in warns:
        print(f"  [WARN]  {i['rule']} L{i['line']}: {i['detail']}")

    print(f"  → {len(errors)} errors, {len(warns)} warnings")
    return len(errors)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _print_error_context(source: str, lineno: int, msg: str) -> None:
    """打印语法错误上下文。"""
    print(f"[FAIL] 语法错误 L{lineno}: {msg}")
    lines = source.split("\n")
    for i in range(max(0, lineno - 3), min(len(lines), lineno + 2)):
        prefix = ">>>" if i + 1 == lineno else "   "
        print(f"  {prefix} {i + 1}: {lines[i]}")


def _run_code_tests(main_py: str) -> int:
    """运行所有代码质量测试，返回失败数。"""
    failures = 0

    checks = [
        ("Python 语法合法", test_syntax, main_py),
        ("校验器通过", test_validator, main_py),
        ("MathTex 不含中文", test_no_mathtex_cjk, main_py),
        ("pseudocode 降级", test_no_pseudocode, main_py),
        ("Code code_string=", test_code_api, main_py),
    ]
    if not _HAS_LATEX:
        checks.append(("无需 LaTeX", test_no_mathtex_without_latex, main_py))

    for name, func, *args in checks:
        try:
            result = func(*args)
            # 特殊处理 test_validator 输出：复用第一次调用的结果打印 warn
            if func is test_validator:
                warns = [i for i in result if i["severity"] == "warn"]
                for w in warns:
                    print(f"  [WARN] [{w['rule']}] L{w['line']}: {w['detail']}")
            print(f"  [OK] {name}")
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            failures += 1

    return failures


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    do_render = "--render" in sys.argv
    do_all_types = "--all-types" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # 外部 DSL 文件检测模式
    if args:
        total_errors = 0
        for path in args:
            for p in Path().glob(path) if "*" in path or "?" in path else [Path(path)]:
                total_errors += check_dsl_file(str(p.resolve()))
        print(f"\n{'='*60}")
        print(f"总计: {total_errors} errors")
        sys.exit(1 if total_errors > 0 else 0)

    # 自测模式
    print("=== Manim Adapter 自测 ===\n")
    print(f"  LaTeX: {'可用' if _HAS_LATEX else '未安装 (MathTex → Text 回退)'}")
    print(f"  Manim: {__import__('manim').__version__}")

    exit_code = 0

    # ── SAMPLE_DSL 测试 ──
    print(f"\n--- SAMPLE_DSL ({SAMPLE_DSL['topic']}) ---")
    files = test_generate(SAMPLE_DSL)
    main_py = files["main.py"]
    print(f"  脚本: {len(main_py)} 字符\n")
    f1 = _run_code_tests(main_py)
    exit_code |= f1

    # ── ALL_TYPES_DSL 测试 ──
    if do_all_types:
        print(f"\n--- ALL_TYPES_DSL ({ALL_TYPES_DSL['topic']}) ---")
        files2 = test_generate(ALL_TYPES_DSL)
        main_py2 = files2["main.py"]
        print(f"  脚本: {len(main_py2)} 字符\n")
        f2 = _run_code_tests(main_py2)
        exit_code |= f2

    # ── 渲染测试 ──
    if do_render:
        print(f"\n--- Manim 渲染测试 ---")
        mp4 = test_render()
        if mp4 is None:
            print("\n[FAIL] 渲染测试失败")
            exit_code = 1
        else:
            print(f"\n[OK] 渲染测试通过: {mp4}")
            # 保留产物供检查
            print(f"  (产物保留，可手动检查)")
        # 也要测 SAMPLE_DSL 渲染（包含更多类型）
        print(f"\n--- SAMPLE_DSL 渲染测试 ---")
        mp4_2 = test_render(SAMPLE_DSL)
        if mp4_2 is None:
            print("\n[FAIL] SAMPLE_DSL 渲染失败")
            exit_code = 1
        else:
            print(f"\n[OK] SAMPLE_DSL 渲染通过: {mp4_2}")

    if exit_code == 0:
        print("\n=== 全部通过 ===")
    else:
        print(f"\n=== 存在失败 (exit={exit_code}) ===")
    sys.exit(exit_code)
