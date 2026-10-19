# API error format

<!-- doc_id: api-errors-01 -->
<!-- category: api -->

Errors return JSON {"error": {"code": "...", "message": "..."}}. Validation failures use code validation_error with a details array. Contact support with the request_id field from the response body when escalating API issues.
