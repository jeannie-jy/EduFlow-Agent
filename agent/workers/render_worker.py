"""Manim Render Worker — Redis 队列消费者。

流程:
1. 从 Redis 队列 (manim:queue) 取任务
2. 将 DSL 转换为 Manim 脚本
3. Docker 容器内执行 manim CLI 渲染
4. 上传产物 → 回调更新 export_jobs 状态
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("manim-worker")

# ── 配置 ─────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
MANIM_QUEUE = "manim:queue"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/output"))
SCRIPTS_DIR = Path(os.getenv("SCRIPTS_DIR", "/app/scripts"))
MANIM_TIMEOUT = int(os.getenv("MANIM_TIMEOUT", "600"))  # 10 分钟

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    """主消费循环。"""
    r = redis.from_url(REDIS_URL, decode_responses=True)
    logger.info("Manim Worker 启动 | queue=%s", MANIM_QUEUE)

    while True:
        try:
            # 阻塞等待任务（超时 30s 后可检查健康状态）
            result = r.blpop(MANIM_QUEUE, timeout=30)
            if result is None:
                continue

            _, task_json = result
            task = json.loads(task_json)
            process_task(r, task)

        except redis.ConnectionError:
            logger.error("Redis 连接断开，5 秒后重试...")
            time.sleep(5)
        except Exception:
            logger.exception("未预期的异常")


def process_task(r: redis.Redis, task: dict) -> None:
    """处理单个渲染任务。"""
    job_id = task.get("job_id", str(uuid.uuid4()))
    dsl = task.get("dsl", {})
    config = task.get("config", {})

    logger.info("开始渲染 | job=%s | topic=%s", job_id, dsl.get("topic", "unknown"))

    # 更新状态到 Redis（前端通过 export API 轮询）
    _update_status(r, job_id, "rendering", progress=0)

    try:
        # 1. DSL → Manim 脚本
        from adapters.manim_adapter import convert_dsl_to_manim
        files = convert_dsl_to_manim(dsl)

        script_dir = SCRIPTS_DIR / job_id
        script_dir.mkdir(parents=True, exist_ok=True)

        main_py_path = script_dir / "main.py"
        main_py_path.write_text(files["main.py"], encoding="utf-8")
        (script_dir / "render_config.json").write_text(files["render_config.json"], encoding="utf-8")
        (script_dir / "subtitles.srt").write_text(files["subtitles.srt"], encoding="utf-8")

        _update_status(r, job_id, "rendering", progress=30)

        # 2. 执行 Manim 渲染
        quality = config.get("quality", "h")
        fps = config.get("fps", 30)

        quality_flags = {
            "l": "-ql",
            "m": "-qm",
            "h": "-qh",
            "k": "-qk",
        }

        cmd = [
            sys.executable, "-m", "manim",
            str(main_py_path),
            quality_flags.get(quality, "-qh"),
            f"--fps={fps}",
            "--format=mp4",
            f"--media_dir={OUTPUT_DIR}",
        ]

        logger.info("Manim CLI: %s", " ".join(cmd))

        _update_status(r, job_id, "rendering", progress=50)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=MANIM_TIMEOUT,
            cwd=str(script_dir),
        )

        _update_status(r, job_id, "rendering", progress=85)

        if result.returncode != 0:
            logger.error("Manim 渲染失败: %s", result.stderr[:500])
            _update_status(r, job_id, "failed", progress=0, error=result.stderr[:1000])
            return

        # 3. 收集产物
        _update_status(r, job_id, "rendering", progress=95)

        # 查找输出的 mp4 文件
        mp4_files = list(OUTPUT_DIR.rglob("*.mp4"))
        artifacts = []
        for mp4 in mp4_files:
            size = mp4.stat().st_size
            artifacts.append({
                "type": "mp4",
                "filename": mp4.name,
                "path": str(mp4),
                "size_bytes": size,
            })

        # 也包含源码和字幕
        artifacts.append({"type": "manim_source", "filename": "main.py", "path": str(main_py_path)})
        subtitles_path = script_dir / "subtitles.srt"
        if subtitles_path.exists():
            artifacts.append({"type": "subtitle", "filename": "subtitles.srt", "path": str(subtitles_path)})

        _update_status(r, job_id, "completed", progress=100, artifacts=artifacts)
        logger.info("渲染完成 | job=%s | artifacts=%d", job_id, len(artifacts))

    except subprocess.TimeoutExpired:
        logger.error("Manim 渲染超时 (%ds) | job=%s", MANIM_TIMEOUT, job_id)
        _update_status(r, job_id, "failed", error=f"渲染超时 ({MANIM_TIMEOUT}s)")
    except Exception as exc:
        logger.exception("渲染异常 | job=%s", job_id)
        _update_status(r, job_id, "failed", error=str(exc)[:500])


def _update_status(
    r: redis.Redis,
    job_id: str,
    status: str,
    progress: float = 0,
    artifacts: list[dict] | None = None,
    error: str | None = None,
) -> None:
    """更新任务状态到 Redis。"""
    key = f"manim:job:{job_id}"
    data = {
        "job_id": job_id,
        "status": status,
        "progress_pct": progress,
        "updated_at": time.time(),
    }
    if artifacts is not None:
        data["artifacts"] = artifacts
    if error is not None:
        data["error_log"] = error

    r.setex(key, 86400, json.dumps(data))  # 24h TTL


if __name__ == "__main__":
    main()
