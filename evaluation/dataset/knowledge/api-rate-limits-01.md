# API rate limits

<!-- doc_id: api-rate-limits-01 -->
<!-- category: api -->

Starter: 60 requests/minute. Growth: 300/minute. Scale: 1,200/minute. Burst headers include X-RateLimit-Remaining. HTTP 429 responses include Retry-After in seconds. Webhook deliveries are not counted against this budget.
