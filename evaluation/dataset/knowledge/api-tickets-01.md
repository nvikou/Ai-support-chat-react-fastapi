# Tickets API

<!-- doc_id: api-tickets-01 -->
<!-- category: api -->

POST /v1/tickets creates a ticket; GET /v1/tickets/{id} fetches it. Pagination uses cursor query params. Soft-deleted tickets return 410 Gone. Attachments must be uploaded via POST /v1/uploads before referencing their upload_id.
