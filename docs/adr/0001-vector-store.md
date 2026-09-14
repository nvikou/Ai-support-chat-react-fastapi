# ADR 0001: Keep FAISS as the local vector store (with hard scale-out limits)

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** VateCon engineering (support agent KB path)
- **Related code:** `backend/app/services/vector_store.py`,
  `faiss_store.py`, `ingest_jobs.py`, `agent.py`,
  `docs` consumers via Knowledge UI polling

## Context

The support agent retrieves answers from an on-disk FAISS index loaded
into each API process. Historically that meant:

1. Ingest ran on the HTTP request path (`add_documents` + `save_local`),
   blocking a worker on large PDFs.
2. Concurrent writers could interleave saves and corrupt `index.faiss` /
   `index.pkl`.
3. Multi-worker uvicorn left newly ingested chunks invisible to peers
   until process restart.
4. Horizontal scale-out looked possible in Compose/K8s diagrams but was
   not actually safe.

We needed concurrency-safe indexing and an **honest** architecture:
keep FAISS if it fits the product stage, but name the limits in writing
instead of pretending a local index is a managed vector DB.

Constraint from product: **do not** migrate to a managed vector service
just to look cloud-native. Prefer identifying, containing, testing, and
documenting the FAISS boundary.

## Decision

**Keep FAISS as the production `VectorStore` backend**, behind a
Protocol, with the following containment:

| Concern | Containment |
|---------|-------------|
| Agent coupling | `VectorStore` Protocol; agent never calls LangChain FAISS APIs directly |
| Concurrent writers | `threading.RLock` (same process) + portable file lock (cross-process) around add+save |
| Crash mid-write | Stage under `.staging/`, then `os.replace` + SHA-256 digest (see `SECURITY.md`) |
| Multi-instance reads | mtime watcher with ~3s TTL reloads before search |
| Blocking HTTP | Upload → DB `pending` + **202**; BackgroundTasks ingest → `indexed`/`failed` |
| UI honesty | Knowledge page polls every 2s **only while** status is `pending` |

Tests (InMemory + concurrent FAISS + ingest status edges) are part of
the acceptance criteria for this decision, not optional follow-up.

## Options considered

### A. FAISS on local/shared volume (chosen)

- **Pros:** Zero extra infra; already in the stack; low latency for
  single-node chat; digest + atomic publish keep integrity enforceable.
- **Cons:** Shared filesystem required for multi-instance; pickle
  deserialization remains a host-trust boundary; no rich filtering /
  hybrid search; BackgroundTasks are not a durable queue.

### B. pgvector (Postgres extension)

- **Pros:** Reuses existing Postgres; transactional ingest with the
  document row; natural multi-instance; backup/restore with the DB.
- **Cons:** Needs extension enablement and ANN tuning; embedding
  dimension + index type choices; ops cost on every environment; larger
  migration than “harden FAISS”.
- **When it wins:** We already pay for Postgres HA and want one backup
  domain for KB + app data.

### C. Qdrant (self-hosted)

- **Pros:** Purpose-built ANN; collections, payload filters, snapshots;
  clear horizontal story.
- **Cons:** New stateful service to run, monitor, and secure; network
  hop on every retrieval; overkill for a small KB.
- **When it wins:** Multiple collections/tenants or filter-heavy
  retrieval become first-class.

### D. Pinecone (managed)

- **Pros:** No vector ops; elastic QPS.
- **Cons:** Vendor lock-in, per-query cost, data residency / DPA review;
  contradicts “no managed vector service yet”.
- **When it wins:** Sustained multi-region traffic where vector ops
  staff cost exceeds Pinecone spend.

## Consequences (accepted)

**Positive**

- Single-instance (and carefully shared-volume multi-reader) deployments
  are concurrency-safe for ingest.
- Failure modes are visible (`pending` / `indexed` / `failed`) instead
  of silent 200 + blocked worker.
- Swapping backends later is a new `VectorStore` implementation, not an
  agent rewrite.

**Negative / residual risk**

- BackgroundTasks die with the process, are invisible across workers,
  and have no durable retry. **Before >1 app instance that accepts
  uploads**, replace with Celery/ARQ/RQ (+ Redis/Postgres broker).
- All writers must share one filesystem for the FAISS volume; two
  replicas with local disks will diverge forever.
- Digest verification refuses a tampered index (fail closed) — operators
  must rebuild from source documents if the volume is compromised.
- mtime TTL (default 3s) means a peer may serve slightly stale retrieval
  briefly after another worker publishes.

## Migration thresholds (concrete)

Leave FAISS **only while all** of the following hold. Crossing **any**
row is a trigger to schedule a migration spike (default target: **B
pgvector** unless filters/tenancy push toward Qdrant).

| Signal | Stay on FAISS while… | Migrate when… | Why that number |
|--------|----------------------|---------------|-----------------|
| Indexed chunks | ≤ **50 000** vectors in `index.ntotal` | Sustained > **50 000**, or full rebuild > **5 minutes** | Local HNSW/flat load + memory stay comfortable on a 2 GB API container; rebuild time starts to hurt deploy/rollback |
| Chat retrieval QPS | ≤ **20** search QPS average, peaks ≤ **50** | p95 search > **80 ms** on the API box **or** sustained > **50** QPS | Leaves headroom for LLM I/O; FAISS is in-process and competes with uvicorn workers for CPU |
| App instances that **read** | ≤ **3** replicas on **one** shared `faiss_data` volume | **4+** readers, or any reader without shared volume | mtime polling + lock chatter stay simple; beyond that prefer a networked store |
| App instances that **write/ingest** | Exactly **1** writer process (Compose default) | Second replica that runs upload/ingest | BackgroundTasks and file locks are not a multi-writer control plane — introduce a queue first; if writes remain hot, move vectors to pgvector/Qdrant |
| Ingest rate | ≤ **30** successful uploads / hour, median PDF < **20 MB** | Backlog of `pending` > **10** for > **15 minutes**, or ingest CPU > **50%** of a worker for > **10 minutes**/hour | Shows BackgroundTasks saturation; queue + dedicated worker (still FAISS) is the interim step before changing backend |
| Multi-tenancy / filters | Single shared KB | Per-tenant isolation or metadata filters on every query | FAISS-as-used has no first-class payload filtering |

### Interim step (still FAISS)

If the **ingest** or **writer-count** threshold trips first, migrate
**scheduling** only:

1. Replace `BackgroundTasks` with ARQ or Celery (Redis already present).
2. Keep a single ingest consumer (or shard by document id with the file
   lock retained).
3. Re-evaluate the table after 2 weeks of metrics.

Do **not** add more API replicas that both ingest until step 1 ships.

### Backend migration order (when the table trips)

1. Implement `PgVectorStore` (or `QdrantVectorStore`) against the
   Protocol.
2. Dual-write or offline re-embed from `knowledge_documents` + source
   files.
3. Flip `SupportAgent` construction to the new backend via settings.
4. Keep FAISS code until one release proves parity on recall smoke tests.

## Operational checklist

- Monitor: `VectorStore.health().document_count`, count of
  `knowledge_documents.status='pending'|'failed'`, API search latency.
- Never expose the FAISS volume to untrusted writers (`SECURITY.md`).
- After volume restore from backup: confirm `index.sha256` verifies
  before serving traffic.

## References

- Implementation: commits on `refresh-contributors` introducing
  Protocol, locked atomic FAISS, mtime TTL, async ingest, agent wiring,
  Knowledge polling, concurrency tests.
- Integrity: `SECURITY.md` (FAISS pickle + digest).
