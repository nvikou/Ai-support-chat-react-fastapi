# Security

This document describes known risks in VateCon AI Support, the threat
model that motivates mitigations, and how to report issues responsibly.

## Scope

In scope:

- Backend API (`backend/app`), WebSocket chat, knowledge upload
- Authentication / session handling
- Redis-backed tickets and rate limits
- On-disk FAISS vector index used by the support agent

Out of scope (for now):

- Client-side XSS in third-party browser extensions
- Physical access to operator workstations
- Supply-chain compromise of upstream PyPI packages (tracked separately)

## Threat model

| Actor | Capabilities | Goals |
|-------|--------------|-------|
| Anonymous internet client | Hit public HTTP/WS endpoints | Stuff credentials, flood resources, probe errors |
| Authenticated user | Chat WebSocket, own history | Steal other users' data, abuse LLM cost |
| Compromised admin | Knowledge upload, admin APIs | Persist malware via uploads, poison KB |
| Host / volume attacker | Write to Docker volumes / disk (`faiss_data`) | Plant a malicious FAISS pickle for RCE on next boot |
| Insider with log access | Read reverse-proxy / access logs | Harvest secrets that appear in URLs or error bodies |

Assumptions:

- TLS terminates at the edge in production
- Redis and Postgres are not exposed publicly
- Only trusted operators mount or write the FAISS volume

## FAISS pickle deserialization

### Risk

`FAISS.load_local(..., allow_dangerous_deserialization=True)` unpickles
`index.pkl`. Pickle can execute arbitrary code during load. If an
attacker can modify files under the FAISS data directory (Docker volume
`faiss_data`, bind mount, backup restore, shared host path), they can
replace `index.pkl` with a malicious payload and gain code execution
when the backend process starts or reloads the index.

### Who can write the index volume?

- Anyone with write access to the host path / named volume
- A compromised container that mounts the same volume
- A malicious or careless restore from an untrusted backup
- Supply-chain or admin tooling that drops files into `faiss_db/`

### Mitigation

1. **Integrity digest** — after every `save_local`, the backend writes
   `index.sha256` covering `index.faiss` and `index.pkl`. On load, the
   digest is verified **before** calling `load_local`. Mismatch or a
   missing digest refuses startup/load (`FaissIntegrityError`).
2. **Volume hardening** — restrict filesystem permissions; do not share
   the FAISS volume with untrusted workloads.
3. **Residual risk** — LangChain still requires
   `allow_dangerous_deserialization=True` to read its own format. The
   digest does not remove pickle; it detects unauthorized modification
   relative to the last trusted write by this application.

Operational note: if you must rebuild a lost digest for a known-good
index, run a controlled rewrite via the application's save path (or
re-ingest) rather than hand-editing `index.sha256` on a suspect tree.

## Other mitigations already in place

- WebSocket auth uses one-time Redis tickets (no JWT in query strings)
- Client-facing errors carry correlation IDs only (no raw exceptions)
- Production rejects missing/weak `SECRET_KEY`
- Knowledge uploads are size-capped and sniffed via magic bytes
- Sliding-window rate limits on login, register, upload, and chat
- Timestamps use timezone-aware UTC (`datetime.now(timezone.utc)`),
  not deprecated naive `datetime.utcnow()`

## Responsible disclosure

Email security findings to the repository owner (GitHub profile contact)
with:

1. Description and affected component
2. Steps to reproduce
3. Impact assessment
4. Any suggested fix

Please allow reasonable time for a fix before public disclosure.
Do not use production customer data in PoCs.
