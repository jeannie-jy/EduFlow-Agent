"""Manim LLM Adapter — 使用 LLM 将 DSL 转化为高质量 Manim 代码。

LLM 拥有完全创作自由，根据教学语义自主设计可视化、布局、配色和动画。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.prompts import MANIM_CODER_SYSTEM_PROMPT
from adapters.manim_adapter import generate_render_config, generate_subtitles_srt

logger = logging.getLogger(__name__)


def _extract_python_code(raw: str) -> str:
    """从 LLM 响应中提取 Python 代码。"""
    md = re.search(r"```(?:python)?\s*\n(.*?)```", raw, re.DOTALL)
    if md:
        return md.group(1).strip()
    for marker in ("from manim import", "#!/usr/bin/env python"):
        idx = raw.find(marker)
        if idx >= 0:
            return raw[idx:].strip()
    return raw.strip()


def _strip_font_size_from_code(code: str) -> str:
    """仅从 Code() 调用中移除 font_size 参数。"""
    lines = code.split("\n")
    result: list[str] = []
    depth = 0
    for line in lines:
        if "Code(" in line and depth == 0:
            depth = line.count("(") - line.count(")")
            line = re.sub(r",?\s*font_size\s*=\s*\d+\s*", "", line)
        elif depth > 0:
            depth += line.count("(") - line.count(")")
            line = re.sub(r",?\s*font_size\s*=\s*\d+\s*", "", line)
        result.append(line)
    return "\n".join(result)


def _build_user_message(dsl: dict[str, Any], teaching_plan: dict[str, Any] | None) -> str:
    """构建发送给 LLM 的上下文消息。"""
    compact_frames = []
    for f in dsl.get("frames", []):
        cf: dict[str, Any] = {
            "frame_id": f.get("frame_id", ""),
            "title": f.get("title", ""),
            "narration": f.get("narration", ""),
        }
        # 包含 state_snapshot（算法状态数据，对可视化至关重要）
        snap = f.get("state_snapshot", {})
        if snap:
            cf["state_snapshot"] = snap

        # 精简 visual_objects：保留所有字段，LLM 自主决定如何使用
        vos = []
        for vo in f.get("visual_objects", []):
            vos.append({
                k: v for k, v in vo.items()
                if k in ("id", "type", "label", "code", "language",
                         "latex", "headers", "rows", "cells", "values",
                         "position", "style", "directed")
            })
        cf["visual_objects"] = vos

        # 精简 animations
        anis = []
        for a in f.get("animations", []):
            anis.append({
                k: v for k, v in a.items()
                if k in ("type", "target", "target_2", "duration_ms",
                         "from_value", "to_value")
            })
        cf["animations"] = anis
        compact_frames.append(cf)

    input_data: dict[str, Any] = {
        "topic": dsl.get("topic", ""),
        "total_frames": len(compact_frames),
        "frames": compact_frames,
    }
    if teaching_plan:
        input_data["teaching_plan"] = {
            "objectives": teaching_plan.get("objectives", []),
            "approach": teaching_plan.get("teaching_approach", ""),
            "outline": teaching_plan.get("outline", []),
            "audience": teaching_plan.get("target_audience_level", "undergraduate"),
        }

    return json.dumps(input_data, ensure_ascii=False, indent=2)


async def convert_dsl_to_manim_llm(
    dsl: dict[str, Any],
    teaching_plan: dict[str, Any] | None = None,
) -> dict[str, str]:
    """用 LLM 将 DSL 转化为 Manim 工程文件。

     LLM 拥有完全创作自由：
     - 根据教学语义设计可视化（数组/树/链表/状态表等）
     - 自主选择配色、布局、动画节奏
     - DSL 中的 visual_objects type 仅作参考

    Returns:
        {"main.py": str, "render_config.json": str, "subtitles.srt": str}

    Raises:
        RuntimeError: LLM 调用或校验失败
    """
    from adapters.manim_validator import validate_script, has_errors

    user_message = _build_user_message(dsl, teaching_plan)

    from agents.llm_client import call_llm

    for attempt in range(2):
        response = await call_llm(
            system_prompt=MANIM_CODER_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.3,
            max_tokens=16384,
        )

        raw = response.get("content", "")
        if not raw:
            raise RuntimeError("LLM 返回空内容，无法生成 Manim 代码")

        main_py = _extract_python_code(raw)
        main_py = "\n".join(line.rstrip() for line in main_py.split("\n"))

        # ── 自动修正 ──
        main_py = re.sub(r"\bCode\(\s*code\s*=\s*", "Code(code_string=", main_py)
        main_py = _strip_font_size_from_code(main_py)
        for bad in ("pseudocode", "plaintext", "csharp", "typescript", "go", "rust"):
            main_py = main_py.replace(f"language='{bad}'", "language='text'")
            main_py = main_py.replace(f'language="{bad}"', 'language="text"')

        # ── 校验 ──
        issues = validate_script(main_py)
        if not has_errors(issues):
            if issues:
                for i in issues:
                    logger.info("LLM 代码 warn: [%s] %s", i["rule"], i["detail"])
            break  # 通过

        if attempt == 0:
            # 将错误反馈给 LLM 重试一次
            error_detail = "; ".join(
                f"[{i['rule']}] {i['detail']}"
                for i in issues if i["severity"] == "error"
            )
            logger.warning("LLM 代码校验失败，重试: %s", error_detail)
            user_message = (
                f"你上一次生成的代码未通过语法校验，错误如下：\n{error_detail}\n\n"
                f"请仔细检查并修复这些错误，重新生成完整的 Manim 代码。\n\n"
                f"原始任务：\n{user_message}"
            )
        else:
            detail = "; ".join(
                f"[{i['rule']}] {i['detail']}"
                for i in issues if i["severity"] == "error"
            )
            raise RuntimeError(f"LLM 生成的代码校验未通过（重试后仍失败）: {detail}")

    config = generate_render_config(dsl)
    subtitles = generate_subtitles_srt(dsl)

    logger.info("LLM 生成 Manim 代码: %d 字符", len(main_py))

    return {
        "main.py": main_py,
        "render_config.json": json.dumps(config, ensure_ascii=False, indent=2),
        "subtitles.srt": subtitles,
    }
