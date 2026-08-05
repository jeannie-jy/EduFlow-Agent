FROM python:3.12-slim

LABEL description="EduFlow-Agent API Service"

WORKDIR /app

# 系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/uploads /app/data/exports

EXPOSE 8000

# 启动前先执行数据库迁移（业务表由 Alembic 管理，见 alembic/versions/0001_baseline.py）
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
