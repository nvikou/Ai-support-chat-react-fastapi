# Idempotency keys

<!-- doc_id: api-idempotency-01 -->
<!-- category: api -->

POST endpoints accept Idempotency-Key headers (UUIDs). Replays within 24 hours return the original response. Keys are unique per token. Omitting the header allows duplicate creates.
