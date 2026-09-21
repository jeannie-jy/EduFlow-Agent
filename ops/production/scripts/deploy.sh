#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-/etc/eduflow/production.env}"
BASE_COMPOSE="$ROOT_DIR/docker-compose.yml"
PROD_COMPOSE="$ROOT_DIR/ops/production/compose.production.yaml"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$BASE_COMPOSE" -f "$PROD_COMPOSE")

"$ROOT_DIR/ops/production/scripts/preflight.sh" "$ENV_FILE"

"${COMPOSE[@]}" pull web migrate agent-api task-worker maintenance material-sandbox
"${COMPOSE[@]}" run --rm migrate
"${COMPOSE[@]}" up -d --remove-orphans material-sandbox agent-api web task-worker maintenance

web_port="$({ docker compose --env-file "$ENV_FILE" -f "$BASE_COMPOSE" -f "$PROD_COMPOSE" \
  config --environment; } 2>/dev/null \
  | awk -F= '$1 == "WEB_PORT" {sub(/^[^=]*=/, ""); print; exit}')"
health_url="http://127.0.0.1:${web_port:-5173}/api/ready"
for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 5 "$health_url" >/dev/null; then
    printf 'Deployment ready: %s\n' "$health_url"
    "${COMPOSE[@]}" ps
    exit 0
  fi
  sleep 2
done

"${COMPOSE[@]}" ps >&2
"${COMPOSE[@]}" logs --tail 100 agent-api >&2
printf 'ERROR: deployment did not become ready: %s\n' "$health_url" >&2
exit 1
