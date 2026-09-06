FROM python:3.12-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libcairo2-dev \
        libpango1.0-dev \
        pkg-config \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.lock.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.lock.txt


FROM python:3.12-slim AS runtime

LABEL description="EduFlow-Agent API Service"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

WORKDIR /app

RUN groupadd --gid 10001 eduflow \
    && useradd --uid 10001 --gid eduflow --no-create-home --shell /usr/sbin/nologin eduflow \
    && mkdir -p /app/data/uploads /app/data/exports /app/data/artifacts \
    && chown -R eduflow:eduflow /app

# 应用代码
COPY --chown=eduflow:eduflow . .

USER eduflow

EXPOSE 8000

# 开发 Compose 兼容入口；生产多副本部署应将迁移拆成单独 Job。
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
