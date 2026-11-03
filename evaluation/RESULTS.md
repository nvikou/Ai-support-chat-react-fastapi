# Evaluation results

Honest, reproducible numbers for the offline RAG harness.
Re-run with `make eval` and refresh this file when the dataset
version or stand-in changes.

| Field | Value |
|-------|-------|
| **Date (UTC)** | 2026-11-03 |
| **Dataset** | `nimbusdesk-v1` (40 docs, 180 labeled questions) |
| **Mode** | `offline-extractive` (token-overlap retrieval, no live LLM) |
| **Cost model tag** | `gpt-4o-mini` (pricing YAML only — no API calls) |
| **CI gate** | fail if `recall@5` &lt; **0.35** |

## Headline metrics

| Family | Metric | Value |
|--------|--------|------:|
| Retrieval | recall@1 | 0.467 |
| Retrieval | recall@3 | 0.569 |
| Retrieval | **recall@5** | **0.625** |
| Retrieval | precision@1 | 0.494 |
| Retrieval | precision@3 | 0.238 |
| Retrieval | precision@5 | 0.181 |
| Retrieval | MRR | 0.547 |
| Generation (proxy) | groundedness | 0.593 |
| Generation (proxy) | relevance (vs gold) | 0.167 |
| Generation (proxy) | hallucination rate | 0.407 |
| Escalation | precision | 0.426 |
| Escalation | recall | 0.816 |
| Escalation | F1 | 0.559 |
| Calibration | **ECE** | **0.275** |
| Performance | latency mean (s) | ~0.0004 |
| Performance | latency p95 (s) | ~0.0005 |
| Performance | est. cost / 1 000 req (USD) | ~0.053 |

Source machine report: regenerate via `python evaluation/run_eval.py`
→ `evaluation/reports/report.json`.

## How to read these numbers

- **recall@5 = 0.625** means that, on average, about 62.5% of the
  gold source documents appear somewhere in the top-5 hits of the
  offline retriever. That is the primary CI-guarded quality signal.
- **ECE = 0.275** means the composite confidence score is only
  moderately calibrated on this stand-in; treat confidence bands as
  directional until a live-LLM eval is added.
- **Escalation F1 = 0.559** reflects pattern + low-confidence rules
  vs labeled `should_escalate`, not a human QA review.
- **Generation relevance is low (0.167)** because the stand-in returns
  extractive chunk text, not a rewritten support answer. That is
  expected offline and must not be sold as end-user answer quality.

## What we are *not* claiming

We **do not** claim “70–80% of support tickets automated.” That figure
had no measurement behind it. On this synthetic set we also **do not**
invent a deflection percentage: deflection needs production traffic
and human labels. Until then, publish retrieval / escalation /
calibration metrics only.

## Limits

1. **Synthetic corpus** — NimbusDesk docs and questions are generated
   with a fixed seed; they are realistic but not a customer KB.
2. **Modest size** — 40 documents / 180 questions; variance will move
   when the set grows.
3. **Offline stand-in** — no OpenAI embeddings, no chat model, no
   judge LLM. Retrieval is token overlap (`InMemoryVectorStore`).
4. **Generation proxies** — groundedness / relevance / hallucination
   use token overlap, not factuality judges.
5. **Latency & cost** — microsecond local retrieval + char/4 token
   estimates; not production p95 against GPT-4o.
6. **Known bias** — hard categories (OOD, injection, unknown) inflate
   abstain/escalate behavior relative to a happy-path FAQ workload.

## Reproduce

```bash
pip install -r backend/requirements.txt
pip install -e "backend/[dev]"
pip install -r evaluation/requirements.txt
make eval
```

Methodology live in `evaluation/README.md`. Dataset contract in
`evaluation/dataset/schema.py`.
