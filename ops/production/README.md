# EduFlow production deployment contract

This directory defines the checks a managed-cloud deployment must satisfy. It
does not pretend to provision vendor resources without a selected cloud account.

## Release topology

- Public traffic terminates at a managed CDN/WAF/load balancer on HTTPS 443.
- The load balancer is the only network peer allowed to reach Web/API services.
- API replicas are stateless. Run `alembic upgrade head` as one pre-deploy Job;
  never run migrations independently in every replica.
- Run the retention/account-deletion loop as one dedicated maintenance worker
  (or an equivalent singleton scheduler), and set `RUN_MAINTENANCE=false` on
  every horizontally scaled API replica.
- General task workers and render workers use separate identities and scaling
  policies. Material/render sandboxes receive no database, KMS, model, SMTP, or
  object-store credentials.
- Use managed multi-zone PostgreSQL, managed HA Redis, versioned object storage,
  a secret manager, and an internal HTTPS KMS Bridge backed by the selected
  cloud KMS. The Bridge contract is documented in the BYOK threat model.

## Required gates

Resolve every secret reference in `ops/production.env.example` at deployment
time. Staging and production processes intentionally refuse to start unless
authentication, secure cookies, same-origin checks, HTTPS origin, BYOK, hidden
API docs, trusted proxy ranges, email verification, SMTP, and credential
encryption are configured. Startup also initializes the PostgreSQL LangGraph
checkpointer; deployed environments never fall back to process-local memory.
Account deletion remains pending and is retried if Redis or persistent
checkpoint cleanup is unavailable, so a relational delete cannot orphan
runtime user data.

The ingress must strip inbound forwarding headers and set its own
`X-Forwarded-For` and `X-Forwarded-Proto`. `TRUSTED_PROXY_IPS` must contain only
the ingress subnet. Do not publish PostgreSQL, Redis, object storage consoles,
Prometheus, Grafana, `/docs`, `/openapi.json`, or `/api/metrics*`. Configure
internal Prometheus scrapes with `Authorization: Bearer …` via
`bearer_token_file` from the Secret Manager-mounted file named by
`METRICS_TOKEN_FILE`; production requests without the matching token receive
404.

## Backup and recovery

- PostgreSQL: multi-zone, continuous WAL/PITR with an RPO of 15 minutes, plus a
  daily retained backup. Encrypt backups with a key separate from application
  secrets.
- Object storage: enable versioning, server-side encryption, and lifecycle rules
  separately for `materials/`, `exports/`, and `audit-archives/`.
- KMS: retain disabled wrapping-key versions for at least the longest credential
  rotation window. The Bridge must continue to unwrap records by their stored
  `key_version`. Deleting a KMS version before rotating stored credentials is
  permanent data loss.
- Run a monthly restore into an isolated account. Apply migrations, run
  `python -m scripts.audit_artifact_consistency`, sample-download material and
  export objects, validate the audit archive chain, and record measured RPO/RTO.
- Promotion gate: measured RPO must be <=15 minutes and service RTO <=2 hours.

## Rollout

1. Deploy to an isolated staging account and run offline tests, migration smoke,
   fault injection, security scans, and real-provider opt-in benchmarks.
2. Canary one API replica with registration disabled. Verify provider, KMS,
   quota, queue, SSE, SMTP, deletion and alert telemetry.
3. Enable public registration and email verification. Keep video exports behind
   a feature flag and the configured daily/monthly quotas.
4. Roll back application images independently from schema. Database migrations
   must remain backward compatible until the previous image is retired.

## Operational ownership

External alerts must cover HTTP 5xx, authentication attacks, provider 429/5xx,
KMS failures, quota rejects, queue age, worker lease expiry, storage growth,
backup/PITR health and missing telemetry. Every alert needs a named owner and a
linked runbook before public registration is enabled.
