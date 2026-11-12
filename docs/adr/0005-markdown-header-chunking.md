# ADR 0005: MarkdownHeaderTextSplitter with recursive fallback

- **Status:** Accepted
- **Date:** 2026-11-12
- **Deciders:** VateCon engineering
- **Related code:** `backend/app/services/chunking.py`,
  `backend/app/agent.py` (`fallback_splitter`)

## Context

Knowledge ingest accepts Markdown-ish text (FAQ, exported docs) and
PDFs/TXT converted to text. Naive fixed-size splits cut mid-section:
retrieval then returns orphan fragments without the heading that
carries policy context (“Refunds”, “SSO”, …).

Support KB articles are usually hierarchical Markdown. Chunking should
prefer section boundaries, then fall back when structure is absent
(plain TXT, messy PDF extract).

## Decision

1. **Primary path (Markdown):**
   `MarkdownHeaderTextSplitter` on `#` / `##` / `###`
   (`split_markdown_text`), keeping header metadata on chunks.
2. **Fallback path:**
   `RecursiveCharacterTextSplitter(chunk_size=1000, …)` when the
   Markdown splitter yields nothing useful, or for non-Markdown /
   PDF-derived documents already loaded as LangChain `Document`s.

## Options considered

### A. Header-aware Markdown + recursive fallback (chosen)

- **Pros:** Preserves section semantics for typical KB articles;
  recursive splitter still bounds token size; one code path for FAQ
  Markdown and a safe escape hatch for unstructured text.
- **Cons:** PDF extract quality still limits headers; oversized
  sections need the recursive pass; two strategies to reason about.

### B. Fixed-size recursive splitter only — serious alternative

- **Pros:** One strategy; predictable chunk lengths; works on any
  text.
- **Cons:** Splits across headings; retrieval loses “which policy
  section” signal; hurts groundedness and citations on structured
  docs.
- **Rejected as default because:** Most admin-authored KB content is
  Markdown with clear headers. Uniform recursive splitting optimizes
  for the worst input and degrades the common case.

### C. Semantic / embedding-based chunking

- **Pros:** Boundaries follow topic shifts even without headings.
- **Cons:** Extra embedding calls at ingest; non-deterministic
  boundaries; harder to explain in audits; cost on every upload.
- **Rejected for now:** Ops complexity and cost outweigh gains on a
  small, mostly headed corpus. Revisit if PDF-heavy KBs dominate.

## Consequences

- Authors should write KB Markdown with real `#` / `##` structure.
- Ingest logs / failed docs still matter when PDF text has no headers —
  fallback kicks in silently by design.
- Changing `chunk_size` is a recall-affecting change; re-run
  `make eval` after retuning.
