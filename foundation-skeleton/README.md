# Foundation Skeleton

Section 1 scaffold for a tenant-aware product foundation:

- frontend: Next.js app router login shell
- backend: FastAPI with JWT auth
- postgres: primary datastore
- redis: cache/connectivity check
- docker compose: local boot with one command
- alembic: migrations
- seed script: default tenant and users
- OpenTelemetry: traces and logs wired in backend

## Quick start

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build` from the repo root.
3. Open `http://localhost:3000` for the frontend.
4. Open `http://localhost:8000/docs` for the API.

Default seeded users:

- `owner@example.com` / `changeme123`
- `member@example.com` / `changeme123`

Seeded tenant:

- `Acme Corp` (`acme`)

## Health endpoints

- `GET /health/live`
- `GET /health/ready`

## Database conventions

- Global tables use UUID primary keys.
- Tenant-scoped tables should inherit `TenantScopedMixin`.
- Tenant-local uniqueness should be declared with `tenant_id` in unique constraints.
- Cross-tenant reads should always filter by tenant membership or explicit tenant_id.

## Useful commands

- `docker compose up --build`
- `docker compose exec backend alembic upgrade head`
- `docker compose exec backend python -m app.seed`
