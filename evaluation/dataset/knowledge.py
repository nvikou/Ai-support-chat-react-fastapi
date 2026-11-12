"""Synthetic NimbusDesk knowledge-base documents.

Forty short, self-contained articles covering billing, accounts, API,
and troubleshooting. Bodies are written so labeled questions can cite
stable ``doc_id`` values.
"""

from __future__ import annotations

import random

from evaluation.dataset.constants import PRODUCT_NAME, TARGET_DOCS
from evaluation.dataset.schema import KnowledgeDoc

# Explicit corpus — not LLM-generated — so the gold labels stay stable.
_DOC_SPECS: list[tuple[str, str, str, str]] = [
    (
        "billing-plans-01",
        "billing",
        f"{PRODUCT_NAME} pricing plans",
        "NimbusDesk offers three plans: Starter ($29/mo, 3 agents), "
        "Growth ($79/mo, 15 agents), and Scale ($199/mo, unlimited "
        "agents). Annual billing discounts the monthly price by 20%. "
        "All plans include email ticketing; chat and SLA policies "
        "start on Growth.",
    ),
    (
        "billing-refunds-01",
        "billing",
        "Refund and cancellation policy",
        "Refunds are available within 30 days of the initial purchase "
        "or plan upgrade. Downgrades take effect at the next renewal. "
        "To cancel, an account owner opens Settings → Billing → "
        "Cancel subscription. Partial months are not prorated on "
        "monthly plans; annual plans receive a prorated credit for "
        "unused whole months.",
    ),
    (
        "billing-invoices-01",
        "billing",
        "Invoices and tax receipts",
        "Invoices are emailed to billing contacts within 24 hours of "
        "each charge. PDF copies live under Settings → Billing → "
        "Invoices. VAT/GST IDs can be set on the same page and appear "
        "on the next invoice. Failed payments retry for 7 days before "
        "the workspace is moved to read-only mode.",
    ),
    (
        "billing-seats-01",
        "billing",
        "Agent seat billing",
        "Each named agent seat is billed on the plan's per-seat rate "
        "for Growth and Scale add-ons beyond the included allotment. "
        "Deactivating an agent frees the seat at the next renewal; "
        "mid-cycle removals do not issue an immediate credit. "
        "Viewers and light requesters are free and unlimited.",
    ),
    (
        "billing-payment-methods-01",
        "billing",
        "Accepted payment methods",
        "NimbusDesk accepts Visa, Mastercard, American Express, and "
        "ACH for Scale customers in the US. Cryptocurrency and PayPal "
        "are not supported. Card updates happen in Settings → Billing "
        "→ Payment method. The card on file must not expire within "
        "the next billing cycle or renewal may fail.",
    ),
    (
        "billing-trial-01",
        "billing",
        "Free trial rules",
        "New workspaces receive a 14-day Growth trial with full "
        "features. No credit card is required to start. At day 14 the "
        "workspace converts to Starter unless a paid plan is selected. "
        "Trial data is retained for 30 days after expiry.",
    ),
    (
        "billing-currency-01",
        "billing",
        "Currencies and FX",
        "List prices are in USD. EU customers may pay in EUR at the "
        "rate locked on the invoice date. Currency cannot be changed "
        "mid-subscription; contact billing@nimbusdesk.example to "
        "migrate at renewal.",
    ),
    (
        "billing-overage-01",
        "billing",
        "Automation and API overage",
        "Starter includes 1,000 automation runs/month. Growth includes "
        "10,000; Scale includes 100,000. Overage is $0.01 per run "
        "billed monthly in arrears. API request overage follows the "
        "same meter on Starter after 50,000 calls.",
    ),
    (
        "billing-credits-01",
        "billing",
        "Promotional credits",
        "Promotional credits apply to future invoices before card "
        "charges. Credits never expire while the workspace is active "
        "but are forfeited 90 days after cancellation. Credits cannot "
        "be cash-refunded.",
    ),
    (
        "billing-dunning-01",
        "billing",
        "Failed payment dunning",
        "After a failed charge NimbusDesk emails the billing contact "
        "on day 0, 3, and 6. On day 7 the workspace becomes read-only. "
        "On day 21 the workspace is suspended. Updating a valid card "
        "restores access within 15 minutes.",
    ),
    (
        "accounts-roles-01",
        "accounts",
        "Workspace roles",
        "Roles are Owner, Admin, Agent, and Viewer. Owners manage "
        "billing and transfer ownership. Admins manage agents, "
        "integrations, and SLAs. Agents handle tickets. Viewers have "
        "read-only dashboards. A workspace must always retain at "
        "least one Owner.",
    ),
    (
        "accounts-sso-01",
        "accounts",
        "SSO and SAML",
        "SAML 2.0 SSO is available on Growth and Scale. Configure the "
        "IdP under Settings → Security → SSO. Just-in-time provisioning "
        "creates Agent seats from IdP group maps. SSO enforcement can "
        "block password login for non-Owner users.",
    ),
    (
        "accounts-mfa-01",
        "accounts",
        "Multi-factor authentication",
        "TOTP MFA is available to all users. Admins may require MFA "
        "workspace-wide. Backup codes are shown once at enrollment. "
        "SMS MFA is not offered. Lost-device recovery requires an "
        "Owner to reset the user's MFA from the Agents page.",
    ),
    (
        "accounts-invite-01",
        "accounts",
        "Inviting teammates",
        "Owners and Admins invite users by email from Settings → "
        "Agents → Invite. Invites expire after 7 days. Pending invites "
        "do not consume paid seats until accepted. Resending an invite "
        "resets the expiry clock.",
    ),
    (
        "accounts-deactivate-01",
        "accounts",
        "Deactivating users",
        "Deactivating a user revokes sessions within 60 seconds and "
        "reassigns open tickets to the default queue. Deactivated "
        "users cannot log in. Reactivation restores the previous role "
        "unless an Admin changes it first.",
    ),
    (
        "accounts-password-01",
        "accounts",
        "Password policy",
        "Passwords must be at least 12 characters and are checked "
        "against a breached-password list. Password reset links expire "
        "in 60 minutes. After 5 failed logins the account locks for "
        "15 minutes.",
    ),
    (
        "accounts-audit-01",
        "accounts",
        "Audit log retention",
        "Security audit logs (logins, role changes, exports) are "
        "retained 90 days on Starter, 1 year on Growth, and 2 years "
        "on Scale. Export CSV from Settings → Security → Audit log.",
    ),
    (
        "accounts-data-export-01",
        "accounts",
        "Workspace data export",
        "Owners can request a full workspace export (tickets, users, "
        "macros) from Settings → Data → Export. Exports are prepared "
        "asynchronously and a download link is emailed within 24 "
        "hours. Links expire after 72 hours.",
    ),
    (
        "accounts-gdpr-01",
        "accounts",
        "GDPR deletion requests",
        "To delete a requester's personal data, Admins open the "
        "contact profile → Privacy → Delete personal data. Ticket "
        "bodies are redacted; ticket IDs remain for integrity. "
        "Deletion completes within 30 days and is logged in the "
        "audit trail.",
    ),
    (
        "accounts-domains-01",
        "accounts",
        "Verified email domains",
        "Workspaces may verify company domains via DNS TXT record. "
        "Verified domains enable auto-join for matching email "
        "addresses when an Admin enables Auto-join. Unverified "
        "domains cannot enforce SSO.",
    ),
    (
        "api-auth-01",
        "api",
        "API authentication",
        "The REST API uses Bearer tokens created under Settings → "
        "Developers → API tokens. Tokens inherit the creator's role "
        "capabilities. Rotate tokens at least every 90 days. Never "
        "embed tokens in client-side JavaScript.",
    ),
    (
        "api-rate-limits-01",
        "api",
        "API rate limits",
        "Starter: 60 requests/minute. Growth: 300/minute. Scale: "
        "1,200/minute. Burst headers include X-RateLimit-Remaining. "
        "HTTP 429 responses include Retry-After in seconds. Webhook "
        "deliveries are not counted against this budget.",
    ),
    (
        "api-webhooks-01",
        "api",
        "Webhooks",
        "Webhooks POST JSON to HTTPS endpoints on ticket.created, "
        "ticket.updated, and agent.mentioned events. Signatures use "
        "HMAC-SHA256 in the X-Nimbus-Signature header. Failed "
        "deliveries retry with exponential backoff for 24 hours.",
    ),
    (
        "api-tickets-01",
        "api",
        "Tickets API",
        "POST /v1/tickets creates a ticket; GET /v1/tickets/{id} "
        "fetches it. Pagination uses cursor query params. Soft-deleted "
        "tickets return 410 Gone. Attachments must be uploaded via "
        "POST /v1/uploads before referencing their upload_id.",
    ),
    (
        "api-versioning-01",
        "api",
        "API versioning",
        "The current stable version is v1. Breaking changes ship under "
        "a new version path. Deprecated fields remain for 12 months "
        "with a Sunset header. Sandbox base URL is "
        "https://sandbox.api.nimbusdesk.example.",
    ),
    (
        "api-scopes-01",
        "api",
        "Token scopes",
        "Tokens may be scoped to tickets:read, tickets:write, "
        "users:read, and webhooks:manage. Least-privilege scopes are "
        "recommended for integrations. Missing scopes yield HTTP 403 "
        "with an error code scope_denied.",
    ),
    (
        "api-idempotency-01",
        "api",
        "Idempotency keys",
        "POST endpoints accept Idempotency-Key headers (UUIDs). "
        "Replays within 24 hours return the original response. Keys "
        "are unique per token. Omitting the header allows duplicate "
        "creates.",
    ),
    (
        "api-errors-01",
        "api",
        "API error format",
        'Errors return JSON {"error": {"code": "...", "message": '
        '"..."}}. Validation failures use code validation_error with '
        "a details array. Contact support with the request_id field "
        "from the response body when escalating API issues.",
    ),
    (
        "api-sdks-01",
        "api",
        "Official SDKs",
        "Official SDKs exist for Python and Node.js under the "
        "nimbusdesk organization on PyPI and npm. Community SDKs are "
        "unsupported. SDK major versions track API v1 compatibility.",
    ),
    (
        "api-ip-allowlist-01",
        "api",
        "API IP allowlisting",
        "Scale plans may restrict API tokens to CIDR allowlists under "
        "Settings → Developers → Network. Allowlist changes propagate "
        "within 5 minutes. Webhooks outbound IPs are published in the "
        "status page and should be allowlisted by receivers.",
    ),
    (
        "trouble-login-01",
        "troubleshooting",
        "Cannot log in",
        "If login fails, verify email spelling, try password reset, "
        "and confirm the account is not locked after failed attempts. "
        "SSO users must sign in through the company IdP button. Clear "
        "cookies for app.nimbusdesk.example if sessions loop.",
    ),
    (
        "trouble-email-sync-01",
        "troubleshooting",
        "Inbound email not creating tickets",
        "Confirm the forwarding address is verified, SPF includes "
        "NimbusDesk, and the mailbox is not quarantining messages. "
        "Check Settings → Channels → Email → Delivery log for the "
        "last 24 hours. Shared mailboxes need the connector re-authed "
        "after password rotation.",
    ),
    (
        "trouble-sla-01",
        "troubleshooting",
        "SLA timers not starting",
        "SLA policies apply only to tickets in subscribed queues with "
        "matching priority. Business-hours calendars must include the "
        "ticket's timezone. Paused statuses stop timers; moving back "
        "to Open resumes them.",
    ),
    (
        "trouble-notifications-01",
        "troubleshooting",
        "Missing agent notifications",
        "Agents must enable browser notifications and not mute the "
        "queue. Email digests are separate from real-time pushes. "
        "If mobile push fails, reinstall the app and re-login. "
        "Owners can inspect notification delivery under Admin → "
        "Diagnostics.",
    ),
    (
        "trouble-slow-ui-01",
        "troubleshooting",
        "Slow inbox performance",
        "Inboxes with more than 10,000 open tickets should use saved "
        "filters. Disable browser extensions that inject into the "
        "page. Hard-refresh (Ctrl+Shift+R) after releases. Persistent "
        "slowness with HAR attached should be escalated to support.",
    ),
    (
        "trouble-webhook-fail-01",
        "troubleshooting",
        "Webhooks failing delivery",
        "Check that the receiver returns 2xx within 10 seconds and "
        "presents a valid TLS certificate. Signature mismatches usually "
        "mean the wrong signing secret. Review the webhook delivery "
        "log for response bodies. Disable then re-enable the endpoint "
        "to clear a poison queue.",
    ),
    (
        "trouble-search-01",
        "troubleshooting",
        "Ticket search missing results",
        "Search indexes updates within 2 minutes. Very new tickets may "
        "not appear immediately. Closed tickets older than 2 years on "
        "Starter are archived and require Advanced search. Special "
        "characters in ticket subjects should be quoted.",
    ),
    (
        "trouble-attachments-01",
        "troubleshooting",
        "Attachment upload errors",
        "Max attachment size is 25 MB. Blocked types include .exe and "
        ".bat. If uploads fail with network errors, try a different "
        "browser or disable VPN SSL inspection. Infected files are "
        "rejected with code malware_detected.",
    ),
    (
        "trouble-timezone-01",
        "troubleshooting",
        "Wrong timestamps in tickets",
        "Timestamps render in each user's profile timezone. Workspace "
        "default timezone affects SLA calendars only. If times look "
        "shifted by exactly one hour, check DST rules on the calendar "
        "linked to the SLA policy.",
    ),
    (
        "trouble-mobile-01",
        "troubleshooting",
        "Mobile app offline mode",
        "The iOS/Android apps cache the last 200 viewed tickets for "
        "offline reading. Replies queue until connectivity returns. "
        "Force-sync from the profile menu if a queued reply is stuck "
        "more than 15 minutes after reconnecting.",
    ),
]


def build_knowledge_docs(
    rng: random.Random | None = None,
) -> list[KnowledgeDoc]:
    """Return the synthetic KB (order shuffled with ``rng``)."""
    del rng  # corpus is fixed; rng reserved for future variants
    docs = [
        KnowledgeDoc(
            doc_id=doc_id,
            category=category,
            title=title,
            body=body,
        )
        for doc_id, category, title, body in _DOC_SPECS
    ]
    if not (30 <= len(docs) <= 50):
        raise RuntimeError(f"knowledge corpus size {len(docs)} outside 30–50")
    if len(docs) != TARGET_DOCS:
        raise RuntimeError(f"expected TARGET_DOCS={TARGET_DOCS}, got {len(docs)}")
    return docs
