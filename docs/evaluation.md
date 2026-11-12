# Evaluation

Offline RAG quality for VateCon. Package root:
[evaluation/](../evaluation/).

## Why it exists

Marketing “70–80% tickets automated” was unverifiable. The harness
publishes **reproducible** retrieval / escalation / calibration
metrics on a seeded synthetic set (`nimbusdesk-v1`) without live
OpenAI calls in the default path.

## How to run

```bash
make eval
# or:
python evaluation/run_eval.py
```

CI: `.github/workflows/eval.yml` on PR/push and weekly. Gate fails if
`recall@5` &lt; **0.35**.

## What to read

| Doc | Content |
|-----|---------|
| [evaluation/README.md](../evaluation/README.md) | Methodology, stand-in limits |
| [evaluation/RESULTS.md](../evaluation/RESULTS.md) | Dated headline numbers |

Example headline (see RESULTS for date/model tag): recall@5 **0.625**,
MRR 0.547, escalation F1 0.559, ECE 0.275.

## Non-goals of this harness

- Not a live GPT judge / RAGAS suite by default.
- Not a production deflection % (needs labeled traffic).
- Generation “relevance” on the extractive stand-in is **not**
  end-user answer quality.

When prompts, chunking, or thresholds change, re-run `make eval` and
update RESULTS if metrics move.
