# Token scopes

<!-- doc_id: api-scopes-01 -->
<!-- category: api -->

Tokens may be scoped to tickets:read, tickets:write, users:read, and webhooks:manage. Least-privilege scopes are recommended for integrations. Missing scopes yield HTTP 403 with an error code scope_denied.
