# ADR 0003: WebSocket for interactive chat (not SSE or polling)

- **Status:** Accepted
- **Date:** 2026-11-12
- **Deciders:** VateCon engineering
- **Related code:** `backend/app/routes/chat.py`,
  `frontend/src/hooks/useChat.ts`, `ws_tickets.py`

## Context

The product UX needs bidirectional chat: user messages, typing
indicators, streamed/batched assistant payloads, escalation banners,
and session continuity. HTTP request/response alone is a poor fit for
long-lived “conversation room” semantics.

We also cannot put long-lived JWTs in WebSocket query strings (they
leak into access logs and browser history) — auth must use a short
Redis ticket consumed on connect.

## Decision

**Use a single authenticated WebSocket** per chat session
(`GET /ws/chat/{session_id}` after `POST /auth/ws-ticket`).

JSON message types carry chat events (user/assistant/typing/error/
escalation). REST remains for auth, history, admin, and knowledge.

## Options considered

### A. WebSocket (chosen)

- **Pros:** True duplex; one connection for typing + replies +
  escalation; matches the existing React hook model; works behind the
  nginx upgrade path already in Compose.
- **Cons:** Sticky connection state; harder to cache; reconnect /
  ticket refresh logic on the client; some corporate proxies are
  hostile to long-lived upgrades.

### B. Server-Sent Events (SSE) — serious alternative

- **Pros:** Simpler one-way stream over HTTP; easy to reason about for
  token streaming; automatic reconnect patterns in browsers.
- **Cons:** Client→server still needs separate POSTs for every user
  message; typing indicators and mid-turn cancellation become a second
  channel; duplex features (agent pushing escalation while user types)
  need awkward coordination.
- **Rejected because:** Chat is inherently duplex. Splitting
  “send message” HTTP and “receive stream” SSE doubles failure modes
  (ticket/auth on two paths) for little gain at our message rates.

### C. Short polling — serious alternative for admin only

- **Pros:** Trivial ops; works everywhere.
- **Cons:** Latency floor = poll interval; wasteful under load; cannot
  express typing without chatter.
- **Rejected for end-user chat** (kept only where honesty needs a
  poll: Knowledge Base `pending` ingest status every 2s). Chat
  UX would feel lagged and burn Redis/DB under concurrent users.

## Consequences

- Frontends must obtain a one-time WS ticket over HTTPS, then connect;
  replaying the ticket fails closed.
- Load balancers must support WebSocket upgrades (or terminate WS at
  the edge that understands them).
- Future token-level streaming can still ride the same socket without
  changing the transport ADR.
