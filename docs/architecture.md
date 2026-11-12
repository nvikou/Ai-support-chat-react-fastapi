# Architecture

VateCon is a RAG support agent: React SPA, FastAPI API, Postgres,
Redis, and an on-disk FAISS index. This page is the map; decisions
live in [docs/adr/](adr/README.md).

## Runtime components

| Component | Role |
|-----------|------|
| **frontend** (nginx + React) | Auth UI, chat, history, admin, knowledge |
| **backend** (FastAPI / uvicorn) | REST, WebSocket chat, ingest, metrics |
| **Postgres** | Users, refresh tokens, conversations, knowledge rows |
| **Redis** | WS tickets, rate limits |
| **FAISS volume** | Local vector index (`faiss_data`) |

Compose wiring: [docker-compose.yml](../docker-compose.yml).

## Request paths

1. **HTTP (REST)** — login/register/refresh, history, admin, knowledge
   upload, Prometheus `/metrics`, health.
2. **WebSocket** — after `POST /auth/ws-ticket`, client connects to
   `/ws/chat/{session_id}`; ticket is consumed once (ADR 0003, 0006).

## Answer pipeline (happy path)

Client → WS (ticket auth) → `SupportAgent` → FAISS retrieval → LLM
(with timeout/retry/fallback/circuit) → groundedness → composite
confidence → escalate or persist → client event.

See Mermaid diagrams in the root [README](../README.md#architecture).

## Trust and quality boundaries

- **Confidence** is composite, not model self-report (ADR 0004).
- **Vector store** is FAISS with explicit migration thresholds
  (ADR 0001 / 0002); not a managed ANN service.
- **Evaluation** is offline and reproducible
  ([evaluation.md](evaluation.md)) — not a marketed automation %.

## Related docs

- [deployment.md](deployment.md) — run and configure
- [security.md](security.md) — threats and mitigations
- [development.md](development.md) — local contrib loop
- [troubleshooting.md](troubleshooting.md) — common failures
- [OBSERVABILITY.md](OBSERVABILITY.md) — logs, metrics, cost, OTel
