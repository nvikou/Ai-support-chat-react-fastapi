# Deployment

## Local (Docker Compose)

```bash
cp .env.example .env
# Set OPENAI_API_KEY and a strong SECRET_KEY
docker compose up --build
```

| Service | URL |
|---------|-----|
| App UI | http://localhost:3000 |
| API / OpenAPI | http://localhost:8000/docs |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

First boot creates the admin user from `ADMIN_EMAIL` /
`ADMIN_PASSWORD`.

## Required production settings

| Variable | Guidance |
|----------|----------|
| `SECRET_KEY` | Long random; rejected if weak when not in debug |
| `COOKIE_SECURE` | `true` behind HTTPS |
| `ALLOWED_ORIGINS` | Exact frontend origin(s), comma-separated |
| `OPENAI_API_KEY` | From a secrets manager, not a git-tracked `.env` |
| `DATABASE_URL` / Redis | Private network only |

## Volumes

- `postgres_data` — durable app state
- `faiss_data` — FAISS index + `index.sha256` digest

**Do not** share `faiss_data` with untrusted writers. Multi-replica
readers need one shared volume and still only **one** ingest writer
until a durable queue ships (ADR 0001).

## Health and ops probes

- Liveness/readiness: lightweight `GET /health`
- Vector scale signals: authenticated `GET /admin/vector-store`
- Metrics: `GET /metrics` (Prometheus)

## Images

CI builds backend/frontend images and runs Trivy (CRITICAL) plus
`pip-audit` / `npm audit`. Prefer releasing from green `main` CI.

## Horizontal scaling (honest limits)

- Stateless API replicas **reading** FAISS: possible on a shared
  volume with mtime reload lag (~3s).
- Replicas that **ingest**: not safe yet — BackgroundTasks are
  process-local. Add ARQ/Celery before scaling writers.

See [architecture.md](architecture.md) and ADR 0001 / 0002.
