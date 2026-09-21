FROM node:20.19.6-alpine3.22 AS web-build

WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build


FROM python:3.12-slim AS python-build

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
COPY agent/requirements.lock.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.lock.txt


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ffmpeg \
        fontconfig \
        fonts-noto-cjk \
        gettext-base \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpq5 \
        nginx \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

WORKDIR /app
COPY agent/ /app/
COPY --from=web-build /web/dist /srv/web
COPY ops/render/nginx.conf.template /etc/eduflow/nginx.conf.template
COPY ops/render/start.sh /usr/local/bin/eduflow-render-start

RUN groupadd --gid 10001 eduflow \
    && useradd --uid 10001 --gid eduflow --no-create-home --shell /usr/sbin/nologin eduflow \
    && mkdir -p /app/data/uploads /app/data/exports /app/data/artifacts /tmp/nginx \
    && chown -R eduflow:eduflow /app /tmp/nginx \
    && chmod 0555 /usr/local/bin/eduflow-render-start

USER eduflow
EXPOSE 10000

CMD ["/usr/local/bin/eduflow-render-start"]

