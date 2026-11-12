# ADR 0004: Composite confidence — reject LLM self-scoring

- **Status:** Accepted
- **Date:** 2026-11-12
- **Deciders:** VateCon engineering
- **Related code:** `backend/app/services/confidence.py`,
  groundedness helpers, escalation thresholds in settings,
  offline ECE in `evaluation/RESULTS.md`

## Context

Early prompts asked the model to emit `CONFIDENCE: [0.0-1.0]` and the
backend parsed that number. Two failures made that unsafe:

1. **Miscalibration** — LLMs are poorly calibrated on their own
   certainty; the number was not a measurable signal.
2. **Fail-open defaults** — missing/malformed markers fell back to
   `0.8`, which *suppressed* escalation on the answers we trust least.
   Prompt text said 0.7 while code escalated at 0.5 — untested magic.

We needed a score derived from retrieval and answer structure that
fails closed and is unit-testable without calling OpenAI.

## Decision

**Compute confidence as a weighted blend of measurable signals** in
`compute_confidence()`:

| Signal | Weight | Meaning |
|--------|-------:|---------|
| Retrieval (best hit + 1st/2nd gap) | 0.40 | Distinctive match in the KB |
| Groundedness | 0.40 | Share of answer tethered to retrieved text |
| Answer length (soft band) | 0.10 | Too short / sprawling → lower trust |
| Has sources | 0.10 | Auditable citations present |

If no hit clears `retrieval_min_similarity` (default 0.35), the score
is **capped at 0.3** (`no_context` penalty). Escalation uses configured
thresholds (default escalate below 0.5), not LLM prose.

Offline on `nimbusdesk-v1` (extractive stand-in, 2026-11-03):
**ECE ≈ 0.275** — moderately calibrated; bands are directional until a
live-LLM eval lands. See [evaluation/RESULTS.md](../../evaluation/RESULTS.md).

## Options considered

### A. Composite signals (chosen)

- **Pros:** Deterministic; unit-tested; fail-closed on weak retrieval;
  inspectable `signals` dict for ops/debug; no extra LLM call.
- **Cons:** Depends on groundedness quality; ECE still imperfect on
  the offline stand-in; weights are heuristics, not fitted on prod.

### B. LLM self-reported confidence — rejected

- **Pros:** Zero engineering; “feels” aligned with the answer text.
- **Cons:** Uncalibrated; prompt/code threshold drift; historical
  fail-open default to 0.8 hid bad answers; not reproducible offline.
- **Rejected because:** Production escalation must not trust a number
  the model invents about itself. Incident class: silent
  non-escalation on garbage answers.

### C. Learned calibrator (Platt / isotonic) on production labels

- **Pros:** Better ECE once labeled traffic exists.
- **Cons:** Needs production deflection labels we do not yet collect;
  overfit risk on tiny sets.
- **Deferred:** Keep composite formula; revisit when feedback 👍/👎 or
  human QA labels exist at meaningful volume.

## Consequences

- Prompts must not be the source of truth for confidence.
- Changing weights/thresholds is a settings + test change, not a
  prompt tweak.
- README claims use measured ECE / escalation F1, not self-scores.
