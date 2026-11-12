# Webhooks

<!-- doc_id: api-webhooks-01 -->
<!-- category: api -->

Webhooks POST JSON to HTTPS endpoints on ticket.created, ticket.updated, and agent.mentioned events. Signatures use HMAC-SHA256 in the X-Nimbus-Signature header. Failed deliveries retry with exponential backoff for 24 hours.
