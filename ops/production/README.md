# EduFlow production deployment contract

This directory defines the checks a managed-cloud deployment must satisfy. It
does not pretend to provision vendor resources without a selected cloud account.

## Stage-one single-node deployment

The repository includes a production overlay for one Linux application node
connected to managed PostgreSQL, Redis, and S3-compatible object storage:

- `compose.production.yaml` replaces local builds with immutable release images,
  removes runtime dependencies on local stateful containers, constrains resources,
  rotates container logs, and keeps the Web listener on loopback by default.
- `stage1.env.example` is the operator-facing environment template. Store the
  populated file outside the repository with mode `600`.
- `scripts/preflight.sh` rejects placeholders, unsafe protocols, old Compose
  versions, insecure file permissions, and invalid merged Compose configuration.
- `scripts/deploy.sh` validates, pulls, migrates, starts, and waits for readiness.
- `scripts/rollback.sh` restores the previous immutable application images but
  deliberately does not reverse database migrations.
- `nginx/eduflow.conf.example` terminates host TLS, routes `/api` directly to
  the loopback-only API listener, strips client forwarding headers, and preserves
  resumable SSE behavior. Other requests go to the loopback-only Web listener.

On the Linux host:

```bash
sudo install -d -m 700 /etc/eduflow
sudo install -m 600 ops/production/stage1.env.example /etc/eduflow/production.env
sudo editor /etc/eduflow/production.env

chmod +x ops/production/scripts/*.sh
ops/production/scripts/preflight.sh /etc/eduflow/production.env
ops/production/scripts/deploy.sh /etc/eduflow/production.env
```

The host reverse proxy or managed load balancer should forward HTTPS traffic to
`127.0.0.1:5173`, while `/api` must route to `127.0.0.1:8000` as shown in the
included Nginx example. Before changing image digests, copy the current file to
`/etc/eduflow/production.previous.env`; that file is the rollback input.

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
