# Security

Canonical deep dive (FAISS pickle threat, reporting): root
[SECURITY.md](../SECURITY.md). This page is the operator checklist.

## Authn / session

- Access JWT ~15 minutes (Authorization header).
- Refresh token in **httpOnly** cookie; hashed in Postgres
  (ADR 0006).
- WebSocket auth via one-time Redis ticket — **no JWT in query
  strings** (ADR 0003).

## Abuse controls

- Sliding-window rate limits: login, register, upload, chat.
- Knowledge uploads: size cap + magic-byte type sniff.
- Production rejects missing/weak `SECRET_KEY`.
- Client errors expose correlation IDs, not stack traces.

## Data / index integrity

- FAISS `index.pkl` is pickle-based; load verifies `index.sha256`
  before deserialize (fail closed on mismatch).
- Restrict who can write the `faiss_data` volume.
- Logs redact secrets (API keys, tokens, passwords); never log raw
  user message bodies in structured fields intended for ops.

## Dependencies

- CI: `pip-audit`, `npm audit`, Trivy image scan, detect-secrets
  pre-commit.
- Dependabot + CodeQL workflows keep the backlog visible.

## Out of scope (today)

- Full SOC2 control set
- Customer-managed encryption keys
- Multi-tenant KB isolation (single shared knowledge base)

Report vulnerabilities privately as described in
[SECURITY.md](../SECURITY.md).
