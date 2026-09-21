#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-10000}"
if [[ -z "${PUBLIC_ORIGIN:-}" ]]; then
  if [[ -z "${RENDER_EXTERNAL_HOSTNAME:-}" ]]; then
    printf 'PUBLIC_ORIGIN or RENDER_EXTERNAL_HOSTNAME is required\n' >&2
    exit 1
  fi
  export PUBLIC_ORIGIN="https://${RENDER_EXTERNAL_HOSTNAME}"
fi

envsubst '${PORT}' \
  < /etc/eduflow/nginx.conf.template \
  > /tmp/nginx.conf

# Free Render services do not support pre-deploy commands. This limited
# deployment has one web instance, so migrations run before either process starts.
alembic upgrade head

uvicorn main:app --host 127.0.0.1 --port 8000 &
api_pid=$!
nginx -c /tmp/nginx.conf -g 'daemon off;' &
nginx_pid=$!

shutdown() {
  kill -TERM "$api_pid" "$nginx_pid" 2>/dev/null || true
  wait "$api_pid" "$nginx_pid" 2>/dev/null || true
}
trap shutdown TERM INT EXIT

wait -n "$api_pid" "$nginx_pid"
exit_code=$?
shutdown
exit "$exit_code"

