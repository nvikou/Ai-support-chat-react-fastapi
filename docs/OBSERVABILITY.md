# Observability

How VateCon answers production questions: latency, cost, escalation
mix, and where a single answer spent its time. This doc covers what we
measure, why, how to wire exporters, and which alerts to start with.

## Mental model

| Layer | Answers | Implementation |
|-------|---------|----------------|
| Structured logs | What happened on request `X`? | JSON stdout + `X-Request-ID` |
| Prometheus | Is the process healthy *right now*? | `GET /metrics` |
| Cost ledger | Who spent what this month? | `CostEvent` + admin `/admin/costs` |
| OpenTelemetry | Where did this answer spend time? | Spans on the RAG path |

Prometheus counters reset on deploy. The SQL cost ledger does not.
Use metrics for SLOs and burn alerts; use the ledger for billing and
budgets.

---

## 1. Structured logs

**Why.** Aggregators need fields, not regex on free-form text. Support
needs one ID that appears in the browser, the API response, and every
log line for that request.

| Knob | Env | Default |
|------|-----|---------|
| Level | `LOG_LEVEL` | `INFO` |
| JSON formatter | `LOG_JSON` | `true` |

**Correlation.** Middleware accepts a safe `X-Request-ID` (or mints
one), stores it in a `ContextVar`, and echoes it on the response.
Unsafe values are replaced so header injection cannot poison logs.

**Redaction (hard rule).** API keys, bearer tokens, passwords, and
user message bodies must never appear in logs. The redaction filter
masks known secret patterns before emit; unit tests inject a fake key
and assert the output is masked.

Do **not** log: prompt text, chat history, retrieved chunks, or raw
LLM responses. Prefer event names (`llm_invoke_ok`,
`groundedness_fail_closed`) plus typed fields (`error_type`,
`model`, `duration_ms`).

---

## 2. Prometheus metrics (`GET /metrics`)

**Why.** Histograms expose p95; counters expose rate and error mix;
the circuit-breaker gauge shows whether we are still calling the
provider.

| Metric | Type | Labels | Why it exists |
|--------|------|--------|---------------|
| `llm_request_duration_seconds` | histogram | `model`, `status` | Provider latency SLO |
| `llm_tokens_total` | counter | `model`, `type` | Volume / capacity planning |
| `llm_cost_usd_total` | counter | `model` | Process-local spend estimate |
| `rag_retrieval_duration_seconds` | histogram | — | Vector-store latency |
| `rag_confidence_score` | histogram | — | Real confidence distribution |
| `conversations_escalated_total` | counter | `reason` | Escalation mix |
| `llm_errors_total` | counter | `error_type` | Failure taxonomy |
| `circuit_breaker_state` | gauge | — | `1` = open, `0` = closed |

Scrape example:

```yaml
scrape_configs:
  - job_name: vatecon-api
    metrics_path: /metrics
    scrape_interval: 15s
    static_configs:
      - targets: ["api:8000"]
```

### Suggested Grafana panels

1. **LLM p95** —
   `histogram_quantile(0.95, sum by (le, model) (rate(llm_request_duration_seconds_bucket[5m])))`
2. **Token rate** —
   `sum by (model, type) (rate(llm_tokens_total[5m]))`
3. **Escalation rate** —
   `sum(rate(conversations_escalated_total[5m])) / sum(rate(llm_request_duration_seconds_count[5m]))`
4. **Confidence heatmap** — `rag_confidence_score` histogram
5. **Circuit breaker** — `circuit_breaker_state`

---

## 3. Cost tracking and budgets

**Why.** Prometheus cost counters are ephemeral. Operators need durable
spend per user/conversation and a backstop when a single account burns
budget.

| Piece | Location |
|-------|----------|
| Model prices (USD / 1M tokens) | `backend/app/data/pricing.yaml` |
| Per-turn ledger | `CostEvent` via `cost_tracker` |
| Admin rollups | `GET /admin/costs?days=7` (UI on Admin page) |
| Default monthly budget | `DEFAULT_MONTHLY_BUDGET_USD` (default `10`) |
| Degrade / block ratios | `BUDGET_DEGRADE_RATIO` (`0.8`), `BUDGET_BLOCK_RATIO` (`1.0`) |

**Budget behaviour (tested).**

| Spend / budget | Action |
|----------------|--------|
| `< degrade_ratio` | Allow primary model |
| `≥ degrade_ratio` and `< block_ratio` | Force fallback model |
| `≥ block_ratio` | Refuse the turn (no LLM call) |

Per-user override: `User.monthly_budget_usd`.

---

## 4. OpenTelemetry tracing

**Why.** Metrics say *how slow*; traces say *which step* (retrieval vs
LLM vs groundedness) dominated a slow answer.

| Knob | Env | Default |
|------|-----|---------|
| Enable | `OTEL_ENABLED` | `false` |
| Exporter | `OTEL_EXPORTER` | `console` (`console` \| `otlp`) |
| OTLP URL | `OTEL_ENDPOINT` | `http://localhost:4318/v1/traces` |

**Span tree (answer path).**

```
HTTP (FastAPI instrumentation)
└── rag.answer
    ├── rag.retrieval
    ├── llm.invoke
    ├── rag.groundedness
    └── rag.confidence
```

`request.id` is attached when a request ID is present so logs and
traces join on the same correlation key.

**Local.**

```bash
OTEL_ENABLED=true OTEL_EXPORTER=console uvicorn app.main:app --reload
```

**Production.** Point `OTEL_ENDPOINT` at a collector (Tempo, Jaeger,
Grafana Cloud, etc.) over OTLP/HTTP. Keep sampling decisions in the
collector until traffic forces in-process sampling.

---

## 5. Alerting (start here)

Thresholds below assume a single API replica serving interactive chat.
Tune after a week of real traffic; keep the *justification*, change the
number.

| Alert | Expr (sketch) | For | Severity | Why these numbers |
|-------|---------------|-----|----------|-------------------|
| LLM p95 high | `histogram_quantile(0.95, sum by (le) (rate(llm_request_duration_seconds_bucket[5m]))) > 8` | 10m | warning | Interactive chat feels broken past ~8s; 10m avoids blips |
| LLM error rate | `sum(rate(llm_errors_total[5m])) / sum(rate(llm_request_duration_seconds_count[5m])) > 0.05` | 10m | critical | >5% typed failures means users mostly escalate or see errors |
| Circuit open | `circuit_breaker_state == 1` | 2m | critical | Open = we skip the provider; every turn degrades/escalates |
| Escalation spike | `sum(rate(conversations_escalated_total[10m])) > 3 * sum(rate(conversations_escalated_total[10m] offset 1d))` | 15m | warning | 3× day-over-day usually means KB/retrieval/model regression |
| Low confidence mass | `sum(rate(rag_confidence_score_bucket{le="0.5"}[15m])) / sum(rate(rag_confidence_score_count[15m])) > 0.4` | 30m | warning | >40% of scores ≤0.5 means retrieval/KB quality drifted |
| Cost burn (process) | `increase(llm_cost_usd_total[1h]) > 5` | — | warning | Catch runaway loops before the monthly budget alone notices |
| Budget blocks | Log/event rate of budget `block` actions > 10/hour | 30m | warning | Many blocks = budgets too tight or abuse |

Page on **circuit open** and **LLM error rate**. Keep the rest as
Slack/email until on-call proves they are actionable.

---

## Quick verification checklist

- [ ] Response includes `X-Request-ID`; same value in JSON logs
- [ ] Injecting `sk-test…` into a log message yields a redacted line
- [ ] `curl localhost:8000/metrics` shows the LLM/RAG collectors
- [ ] Admin → costs shows total, avg/conversation, top users, 7-day trend
- [ ] With `OTEL_ENABLED=true` and console exporter, an answer prints
      `rag.answer` / `rag.retrieval` / `llm.invoke` spans
