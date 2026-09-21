# Limited Render deployment

This deployment is intentionally a demonstration environment, not the production
topology described in `ops/production/README.md`.

It deploys one combined Web/API Docker service, one free Render Postgres 16
database, and one free Render Key Value instance in Singapore. Nginx and FastAPI
run in the same container so the browser uses same-origin `/api` requests.

Included capabilities:

- landing page and React application;
- authentication and user-owned provider credentials;
- PostgreSQL persistence, pgvector, projects, versions, and resumable SSE;
- synchronous Agent generation using the user's BYOK provider.

Deliberately limited or unavailable:

- no durable task worker, so material parsing and feedback-triggered reflection
  jobs remain queued;
- no isolated material parser or generated-code sandbox;
- no video rendering;
- local artifact files are ephemeral across Render deploys/restarts;
- local development KEK instead of the production KMS Bridge;
- no email verification, SMTP, metrics backend, PITR guarantee, or HA;
- the free database expires after 30 days and the free web service can spin down.

## Deploy

1. Push the branch containing `render.yaml` to the connected GitHub repository.
2. In Render, create a new Blueprint and select this repository and branch.
3. Review the three free resources and apply the Blueprint.
4. Wait for the Web service health check at `/api/health` to pass.
5. Register the first user, add generation and embedding credentials under model
   access settings, and run a small generation smoke test.

Do not upload important materials to this limited environment. Do not upgrade a
resource to a paid plan without reviewing current Render pricing and the full
production requirements.

