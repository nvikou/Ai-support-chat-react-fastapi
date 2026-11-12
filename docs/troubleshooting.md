# Troubleshooting

## `docker compose up` fails on backend

- Check `OPENAI_API_KEY` and `SECRET_KEY` in `.env`.
- Wait for Postgres/Redis healthchecks; backend depends on both.
- Logs: `docker compose logs backend --tail=100`.

## Login works but chat never connects

1. Confirm `POST /auth/ws-ticket` returns 200 (auth cookie/header OK).
2. WS URL must match nginx/proxy upgrade config (Compose frontend
   proxies to backend).
3. Ticket is **one-time** and short-lived — reconnect needs a new
   ticket (ADR 0003).
4. Mixed content: HTTPS page cannot open `ws://` to localhost without
   a matching setup.

## Refresh / “logged out” loops

- Local HTTP: `COOKIE_SECURE=false`.
- Production HTTPS: `COOKIE_SECURE=true` and SameSite/domain aligned
  with the SPA origin.
- Clock skew: refresh row `expires_at` is UTC-aware.

## Knowledge upload stuck on `pending`

- Ingest runs in process BackgroundTasks — restarting the API drops
  in-flight jobs.
- Only one writer is supported; check `GET /admin/vector-store` and
  backend logs for `failed` reason (parse/embed errors).
- Large PDFs block a worker until done; see ADR 0001 limits.

## `FaissIntegrityError` / index won’t load

- `index.sha256` mismatch → refuse load (fail closed).
- Restore from trusted backup or re-ingest; do not hand-edit digests
  on a suspect volume ([security.md](security.md)).

## Low confidence / constant escalation

- Empty or tiny KB → retrieval miss → score capped (~0.3).
- Re-run `make eval` after chunking changes.
- Confirm escalation threshold settings vs ADR 0004.

## CI: `security-scan` / Trivy / pip-audit

- Bump the pinned vulnerable package (see recent `pypdf` / Alpine
  `apk upgrade` fixes) rather than blanked ignores when a fix exists.
- jose/ecdsa ignores are documented in `.github/workflows/ci.yml`
  only where no safe drop-in exists yet.

## Eval gate red

- Local: `make eval` and inspect `evaluation/reports/`.
- recall@5 must stay ≥ 0.35 on `nimbusdesk-v1`.
- Do not “fix” CI by raising thresholds without changing RESULTS
  honesty.
