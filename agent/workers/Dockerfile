FROM python:3.12-slim

LABEL description="EduFlow-Agent Manim Render Worker"

# 系统依赖（Manim 需要 ffmpeg + cairo 等渲染库）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libcairo2-dev \
        libpango1.0-dev \
        pkg-config \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Manim 社区版
RUN pip install --no-cache-dir \
    manim \
    redis \
    boto3 \
    requests

WORKDIR /app

# Worker 脚本
COPY render_worker.py .

# 渲染输出目录
RUN mkdir -p /app/output /app/scripts

CMD ["python", "render_worker.py"]
