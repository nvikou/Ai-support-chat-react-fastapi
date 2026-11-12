# ADR 0006: Short JWT access + httpOnly refresh cookie

- **Status:** Accepted
- **Date:** 2026-11-12
- **Deciders:** VateCon engineering
- **Related code:** `backend/app/security.py`, `routes/auth.py`,
  `frontend/src/lib/api.ts`, `frontend/src/context/AuthContext.tsx`

## Context

SPA chat needs authenticated HTTP and WebSocket flows. A long-lived
token in `localStorage` is XSS-stealing bait. Putting the session JWT
in the WebSocket query string leaked into proxy logs (fixed with
Redis tickets — see ADR 0003).

We need: short blast radius if an access token leaks, refresh without
re-login, and CSRF-conscious cookie handling for the refresh path.

## Decision

| Piece | Choice |
|-------|--------|
| Access token | JWT in memory / Authorization header, **15 minutes** |
| Refresh token | Opaque token, **httpOnly** cookie (`refresh_token`), **7 days**, hashed at rest in Postgres |
| WebSocket | One-time Redis ticket from authenticated HTTP — **never** JWT in query string |
| Cookie flags | `HttpOnly`; `Secure` when `COOKIE_SECURE=true` (production HTTPS) |

Refresh rotates via `POST /auth/refresh`; logout clears cookie and
revokes server-side hash rows as implemented.

## Options considered

### A. Short JWT + httpOnly refresh (chosen)

- **Pros:** Access token XSS window ≤ 15 min; refresh not readable by
  JS; server can revoke refresh hashes; fits SPA + cookie domain on
  same site / proxied setup.
- **Cons:** CSRF must be considered on cookie-authenticated refresh
  (SameSite + origin checks / pairing with access header patterns);
  mobile native clients need a deliberate cookie story.

### B. Long-lived JWT in localStorage only — rejected

- **Pros:** Trivial frontend; no cookie/CSRF story.
- **Cons:** Any XSS exfiltrates a multi-day credential; no clean
  server-side revoke without a denylist the size of traffic.
- **Rejected because:** Support admins upload docs and see all
  conversations — session theft impact is high.

### C. Session cookie only (server sessions in Redis) — serious alternative

- **Pros:** Classic revoke-by-delete; no JWT crypto on every request.
- **Cons:** Every API instance must hit Redis for session; harder for
  pure Bearer API clients; larger rewrite of existing JWT middleware.
- **Rejected for now:** We already ship JWT middleware and admin/API
  docs assuming Bearer access tokens. Refresh cookies give revoke for
  the long-lived half without abandoning Bearer for the short half.
  Revisit if we standardize on BFF-only access.

## Consequences

- Local HTTP demos keep `COOKIE_SECURE=false`; production **must**
  set `COOKIE_SECURE=true` behind TLS.
- Frontends refresh silently on 401; users should not paste JWTs into
  URLs.
- WS ticket TTL stays short (≈60s) so a leaked ticket is useless after
  connect or expiry.
