#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-/etc/eduflow/production.env}"
BASE_COMPOSE="$ROOT_DIR/docker-compose.yml"
PROD_COMPOSE="$ROOT_DIR/ops/production/compose.production.yaml"

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "docker is not installed"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is not available"
[ -r "$ENV_FILE" ] || fail "environment file is not readable: $ENV_FILE"

compose_version="$(docker compose version --short | sed 's/^v//')"
compose_major="${compose_version%%.*}"
compose_minor="$(printf '%s' "$compose_version" | cut -d. -f2)"
if [ "$compose_major" -lt 2 ] || { [ "$compose_major" -eq 2 ] && [ "$compose_minor" -lt 24 ]; }; then
  fail "Docker Compose 2.24+ is required; found $compose_version"
fi

file_mode="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || true)"
case "$file_mode" in
  600|400) ;;
  *) fail "$ENV_FILE must have mode 600 or 400 (found ${file_mode:-unknown})" ;;
esac

required=(
  AGENT_IMAGE WEB_IMAGE PUBLIC_ORIGIN TRUSTED_PROXY_IPS DATABASE_URL REDIS_URL
  MINIO_ENDPOINT MINIO_PUBLIC_ENDPOINT MINIO_ACCESS_KEY MINIO_SECRET_KEY
  AUTH_REGISTRATION_CHALLENGE_SECRET SMTP_HOST SMTP_USERNAME SMTP_PASSWORD SMTP_FROM
  CREDENTIAL_KMS_WRAP_URL CREDENTIAL_KMS_UNWRAP_URL CREDENTIAL_KMS_BEARER_TOKEN
  CREDENTIAL_FINGERPRINT_KEY_B64 CREDENTIAL_KEK_VERSION METRICS_ACCESS_TOKEN
  AUDIT_ARCHIVE_HMAC_KEY
)

compose_environment="$({ docker compose \
  --env-file "$ENV_FILE" \
  -f "$BASE_COMPOSE" \
  -f "$PROD_COMPOSE" \
  config --environment; } 2>/dev/null)"

env_value() {
  local requested="$1"
  awk -F= -v key="$requested" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' \
    <<<"$compose_environment"
}

for name in "${required[@]}"; do
  value="$(env_value "$name")"
  [ -n "$value" ] || fail "$name is required"
  case "$value" in
    *replace-me*|*replace-with*|*your-org*|*example.com*)
      fail "$name still contains an example value"
      ;;
  esac
done

PUBLIC_ORIGIN="$(env_value PUBLIC_ORIGIN)"
CREDENTIAL_KMS_WRAP_URL="$(env_value CREDENTIAL_KMS_WRAP_URL)"
CREDENTIAL_KMS_UNWRAP_URL="$(env_value CREDENTIAL_KMS_UNWRAP_URL)"
DATABASE_URL="$(env_value DATABASE_URL)"
REDIS_URL="$(env_value REDIS_URL)"
MINIO_SECURE="$(env_value MINIO_SECURE)"

case "$PUBLIC_ORIGIN" in https://*) ;; *) fail "PUBLIC_ORIGIN must use https" ;; esac
case "$CREDENTIAL_KMS_WRAP_URL" in https://*) ;; *) fail "KMS wrap URL must use https" ;; esac
case "$CREDENTIAL_KMS_UNWRAP_URL" in https://*) ;; *) fail "KMS unwrap URL must use https" ;; esac
case "$DATABASE_URL" in postgresql://*|postgresql+asyncpg://*) ;; *) fail "DATABASE_URL must be PostgreSQL" ;; esac
case "$REDIS_URL" in rediss://*) ;; *) fail "production REDIS_URL must use rediss://" ;; esac
case "$DATABASE_URL" in *ssl=require*|*sslmode=require*|*ssl=true*) ;; *) fail "DATABASE_URL must require TLS" ;; esac
case "$MINIO_SECURE" in true|TRUE|1) ;; *) fail "MINIO_SECURE must be true" ;; esac

docker compose \
  --env-file "$ENV_FILE" \
  -f "$BASE_COMPOSE" \
  -f "$PROD_COMPOSE" \
  config --quiet

printf 'Preflight passed for %s\n' "$ENV_FILE"
