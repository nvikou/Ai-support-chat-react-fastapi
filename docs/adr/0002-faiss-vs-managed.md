# ADR 0002: Prefer FAISS until concrete scale signals trip

- **Status:** Accepted
- **Date:** 2026-11-12
- **Deciders:** VateCon engineering
- **Related:** [ADR 0001](0001-vector-store.md) (containment),
  `backend/app/services/faiss_store.py`,
  `GET /admin/vector-store`

## Context

ADR 0001 decided to **keep** FAISS and harden ingest. This ADR records
the *selection* rationale: why FAISS was chosen over pgvector or
Qdrant for the current product stage, and the measurable point at
which that choice becomes the wrong default.

The README and sales materials must not imply a managed vector
platform. Operators need a written threshold so “we should migrate”
is a metric event, not a vibe.

## Decision

**Default vector backend remains local FAISS** for single-writer,
shared-volume deployments under the migration table in ADR 0001.

Default migration target when any hard threshold trips: **pgvector**,
unless payload filters / multi-tenant collections dominate — then
**Qdrant**.

## Options considered

### A. FAISS local index (chosen)

- **Pros:** No extra service; sub-ms in-process search for small KB;
  already wired through `VectorStore` Protocol; zero egress cost.
- **Cons:** Shared filesystem for multi-reader; pickle trust boundary;
  no first-class filters; BackgroundTasks are not a durable queue.
- **Stay while:** ≤ 50 000 vectors, ≤ ~20 search QPS average, one
  ingest writer, single shared KB (full table in ADR 0001).

### B. pgvector (serious alternative — deferred)

- **Pros:** Same Postgres backup domain as users/conversations;
  multi-instance without a shared FAISS volume; transactional delete
  with the document row.
- **Cons:** Extension + ANN index ops on every environment; migration
  of embeddings; slower time-to-demo for a portfolio repo.
- **Rejected for now because:** We already have one writer and a small
  synthetic KB; paying extension/ops cost before any threshold trips
  buys little reliability. **Revisit when** `index.ntotal` > 50 000,
  rebuild > 5 minutes, or a second ingest-capable replica is required.

### C. Qdrant self-hosted (serious alternative — deferred)

- **Pros:** Collections, payload filters, snapshots, clearer horizontal
  story than FAISS files.
- **Cons:** New stateful service to patch, back up, and network-harden;
  every retrieval becomes a network hop.
- **Rejected for now because:** The product is a single shared KB with
  no per-tenant filter requirement. Qdrant wins when isolation or
  metadata filters become first-class — not for “looks enterprise.”

## Consequences

- ADR 0001 containment (locks, digest, mtime reload, async ingest UI)
  remains mandatory while FAISS is default.
- Crossing **any** ADR 0001 migration row schedules a spike; default
  implementation order is Protocol → dual-write/re-embed → flip
  settings → keep FAISS until recall smoke passes.
- Docs and `/admin/vector-store` expose the signals so the decision
  can be reopened with data, not opinion.
