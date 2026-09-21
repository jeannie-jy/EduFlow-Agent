#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-/etc/eduflow/production.env}"
PREVIOUS_ENV_FILE="${2:-/etc/eduflow/production.previous.env}"
BASE_COMPOSE="$ROOT_DIR/docker-compose.yml"
PROD_COMPOSE="$ROOT_DIR/ops/production/compose.production.yaml"

[ -r "$PREVIOUS_ENV_FILE" ] || {
  printf 'ERROR: previous release environment is not readable: %s\n' "$PREVIOUS_ENV_FILE" >&2
  exit 1
}

"$ROOT_DIR/ops/production/scripts/preflight.sh" "$PREVIOUS_ENV_FILE"

docker compose \
  --env-file "$PREVIOUS_ENV_FILE" \
  -f "$BASE_COMPOSE" \
  -f "$PROD_COMPOSE" \
  pull web agent-api task-worker maintenance material-sandbox

# Database migrations are intentionally not reversed. Releases must preserve
# backward compatibility with the immediately previous application image.
docker compose \
  --env-file "$PREVIOUS_ENV_FILE" \
  -f "$BASE_COMPOSE" \
  -f "$PROD_COMPOSE" \
  up -d --no-deps web agent-api task-worker maintenance material-sandbox

printf '%s\n' \
  'Application images rolled back. Database migrations were not reversed.' \
  "The active environment file was not overwritten; promote $PREVIOUS_ENV_FILE manually after verification."
