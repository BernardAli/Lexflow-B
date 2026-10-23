# LexFlow API — Functional Prototype

Interactive OpenAPI docs: `http://127.0.0.1:8000/docs` after server starts. All endpoints are JSON unless otherwise noted.

OpenAPI/Swagger pages are disabled in the hardened profile. All API responses use `Cache-Control: no-store`. Requests must use an allowed Host name; the hardened profile requires HTTPS.

## Workflow learning

- `GET /api/workflows` — tenant-scoped rule list.
- `POST /api/workflows/preview` — reviewer/admin; `{ "matter_type": "property_purchase", "field_key": "buyer_name", "label": "Erwerbende Person", "sample_text": "Erwerbende Person: Anna Beispiel" }`. Examples are transient; response includes suggested candidates and `sample_stored: false`.
- `POST /api/workflows` — admin; save `matter_type`, `field_key`, `label`, optional `enabled`. The API persists no sample text. Rules use escaped literal labels followed by a colon or equals sign, never user-supplied regex. Limit: 100 rules per workspace.
- `PATCH /api/workflows/{id}` — admin; `{ "enabled": false, "expected_version": 1 }`. A stale version returns 409.
- `GET /api/workflows/{id}/versions` — configuration history.

Learned rules apply to future intake for their workspace and matter type. They create unverified candidates, preserving conflict checks and required human confirmation. Existing documents and approvals are not silently reprocessed. Destination mappings remain in `/api/settings/mappings`.

## Integration adapters

- `GET /api/integrations` — transfer history, local receiver records and webhook availability, scoped to the workspace.
- `POST /api/integrations/dry-run` — reviewer/admin; `{ "matter_id": "...", "connector": "demo_receiver" }`. Requires approved data; returns `payload` and `preview_hash` without sending.
- `POST /api/integrations/transfers` — reviewer/admin; `{ "matter_id": "...", "connector": "demo_receiver", "preview_hash": "hash-from-dry-run", "idempotency_key": "a-unique-request-key" }`.
- `POST /api/integrations/intake` — authenticated multipart adapter for agents; `matter_id`, one `file`, `Idempotency-Key` header, session cookie and CSRF header. Uses the same document parsers and approval rules as browser intake; external AI is disabled for this adapter.

Transfer destinations are `demo_receiver`, `demo_notary` and `webhook`. `demo_notary` sends to the fictional local NotaryDesk TLS destination and remains marked simulated. Its acceptance receipt is signed and bound to the original transfer key and payload SHA-256. The local receiver stores a real local record and returns a receipt marked `simulated: true`. It sends nothing to a notary vendor. The webhook is available only when an operator configures a workspace-specific HTTPS destination. Approval, payload fingerprint and mapping checks run immediately before delivery. An accepted key replays its receipt; it does not resend. Reusing a key for another payload returns 409. Failed or uncertain deliveries can be retried with the **same key and approved fingerprint**. A changed approval requires a fresh preview/key. Intake receipts and document creation commit together; duplicate agent uploads do not invalidate reviews again.

Webhook requests contain a UTF-8 JSON body and these headers:

```text
Idempotency-Key: original-transfer-key
X-LexFlow-Timestamp: Unix timestamp in seconds
X-LexFlow-Signature: sha256=HMAC-SHA256(secret, timestamp + "." + raw_body)
```

The receiver must verify the HMAC and timestamp freshness, scope idempotency to `workspace_id` plus key, and return a 2xx JSON response `{ "accepted": true, "receipt_id": "destination-receipt-123" }`. Receipts permit 1–128 letters/digits/underscores/dots/hyphens. A 4xx records rejection. Network errors, 5xx, redirects or missing acceptance receipts record an **uncertain** outcome. Redirects and environment proxy settings are disabled; TLS certificates are verified. Endpoint secrets never appear in API responses. The receiver must enforce idempotency across a crash between its write and LexFlow's receipt commit.

A durable integration job records the payload and destination fingerprint before network I/O. A 120-second lease prevents approval-invalidating edits during the bounded 10-second call; unrelated database writes can proceed. Transfer states include pending, sending, accepted, failed, uncertain and cancelled. Accepted keys replay without sending; active leases return an in-progress receipt. A restart can resume pending/expired sends through `python -m lexflow.manage deliver-pending`. Stale approvals, changed destinations or revoked reviewer access cancel recovery. Uncertain outcomes require explicit same-key retry after destination inspection. A scheduled worker and high-volume reconciliation remain deployment work.

## Pilot evidence

- `GET /api/pilot?matter_type=property_purchase` — extraction coverage, current correction rate, heuristic low-confidence rate, expected audit activity coverage, separate simulated/webhook acceptance rates, and reported time comparison. Each rate includes numerator and denominator; absent evidence produces `null`, not an invented percentage.
- `PUT /api/pilot/baseline` — admin; `{ "matter_type": "property_purchase", "minutes": 20, "sample_size": 5 }`.
- `POST /api/pilot/observations` — `{ "matter_id": "...", "seconds": 300, "source": "manual", "idempotency_key": "a-unique-observation-key" }`. Sources: `manual` or `timer`. Reusing the same key/content does not count time twice. Each case's sessions are summed, then averaged across observed cases.
- `GET /api/pilot/report.csv?matter_type=property_purchase` — aggregate CSV evidence with definitions and sample counts.

Baseline times are operator supplied and pilot times are reported by users/browser timers. They are indicative measurements, not independently verified efficiency or extraction-accuracy claims. Historical seeded records may have gaps in activity audit coverage; the UI exposes them honestly. Every candidate still requires review regardless of its confidence heuristic.

## Security controls

- `GET /api/security/status` — active controls, unexpired account sessions and audit verification.
- `POST /api/security/sessions/revoke-others` — keep the current session; revoke the account's other sessions.
- `GET /api/security/audit-checkpoint` — HMAC chain verification plus checkpoint for external retention.
- `GET /api/auth/options` — public demo/profile flags, used to hide seeded credentials outside demo mode.

Sign-in is limited to 10 requests per normalized email and 50 per client IP per fixed 15-minute window. Inactive sessions expire after 30 minutes by default, alongside the 12-hour absolute expiry. Unknown and incorrect sign-in credentials both incur password verification work. Trusted proxy configuration is required for reliable peer-IP limits.

## Authentication

- `POST /api/auth/login` — `{ "email": "admin@keller.demo", "password": "LexFlowDemo2026!" }`; sets HttpOnly session cookie and returns a CSRF token.
- `GET /api/auth/me` — authenticated user, CSRF token, demo flags.
- `POST /api/auth/logout` — invalidate session.
- `POST /api/auth/change-password` — current/new password.
- `POST /api/auth/forgot-password` — `{ "email": "admin@keller.demo" }`; public, rate limited. Returns a neutral `message` and `delivery` mode. In demo mode, only seeded sample accounts also receive a `demo_reset_path` and `expires_in_minutes: 30`. SMTP mode never returns a token.
- `POST /api/auth/reset-password` — `{ "token": "...", "new_password": "12–128 characters", "confirm_password": "same password" }`; public, rate limited. Consumes a valid link, changes the password and revokes every session and pending reset link for the account. Returns `{ "ok": true, "message": "..." }`; requires a fresh sign-in.

Authenticated state-changing requests require the `X-CSRF-Token` returned by login. Requests made from the web interface include this automatically.

Recovery links use `/#/reset-password?token=...`, keeping tokens in the URL fragment rather than HTTP request URLs. Auth responses and the HTML shell use `Cache-Control: no-store` and `Referrer-Policy: no-referrer`. Invalid or expired links return HTTP 400; invalid/mismatched passwords return 422; rate limits return 429 with `Retry-After`; unavailable delivery configuration returns 503 for every email address. Validation errors omit submitted credentials. Request limits are five per email and twenty per client IP per fixed 15-minute window; completion allows thirty attempts per client IP per window. Recovery endpoints require no session/CSRF token: completion requires the unguessable reset token.

## Main workflows

| Endpoint | Method | Purpose / role |
|---|---|---|
| `/api/health` | GET | Public health check |
| `/api/config` | GET | Supported schemas and extraction types |
| `/api/dashboard` | GET | Aggregated scoped dashboard |
| `/api/matters` | GET | Filter / list matters |
| `/api/matters` | POST | Create matter (any authenticated user) |
| `/api/demo/start` | POST | Create a fresh synthetic property-purchase example; demo mode only |
| `/api/matters/{id}` | GET | Fields, evidence, documents, exports, review state |
| `/api/intake/text` | POST | Ingest pasted text; optionally external AI opt-in |
| `/api/intake/upload` | POST | Multipart ingestion of up to six files |
| `/api/documents/{id}` | GET | Extracted text and metadata |
| `/api/documents/{id}/download` | GET | Download original document |
| `/api/matters/{id}/fields/{key}/confirm` | POST | Human confirm (reviewer/admin) |
| `/api/matters/{id}/fields/{key}/clear` | POST | Clear reviewed value (reviewer/admin) |
| `/api/matters/{id}/approve` | POST | Validate required values and approve (reviewer/admin) |
| `/api/matters/{id}/reopen` | POST | Invalidate approval to edit (reviewer/admin) |
| `/api/matters/{id}/export/preview` | GET | Preview JSON/CSV (approved only) |
| `/api/matters/{id}/exports` | POST | Generate local JSON/CSV (reviewer/admin) |
| `/api/exports` | GET | Export history |
| `/api/exports/{id}/download` | GET | Download approved export |
| `/api/audit` | GET | Tenant-scoped audit events |
| `/api/settings/mappings` | GET/PUT | Read/update connector mappings (PUT: admin only) |
| `/api/settings/users` | GET | List own workspace users (admin only) |

### Example — ingest text

```json
POST /api/intake/text
{
  "matter_id": "matter-demo-intake",
  "filename": "synthetic_message.txt",
  "text": "Käufer: Anna Schmidt\nKaufpreis: 850.000,00 EUR",
  "use_external_ai": false
}
```

### Example — confirm source value

```json
POST /api/matters/{matter-id}/fields/land_register/confirm
{
  "candidate_id": "the-suggestion-id-from-GET-matter",
  "note": "Verified against updated synthetic source"
}
```

Or use `{ "value": "München Blatt 812", "note": "Manual check" }` to enter a reviewed value.

### Example — export

```json
POST /api/matters/{matter-id}/exports
{
  "format": "json",
  "connector": "notary_demo"
}
```

The payload includes an explicit marker `not_a_live_transmission: true`. This endpoint does **not** connect to BNotK, XNP or notary case-management software.

Approval requires valid confirmed required fields and no unresolved conflicts, including optional fields. Confirmation returns HTTP 422 for invalid amounts, dates, email addresses, or empty/invalid names. Monetary values use exact decimal normalization and dates use ISO format.

Export preview accepts `fmt=json|csv` and `connector=approved_export|notary_demo`. Preview and generation apply the same validation. Mapping destinations must be unique across the complete saved mapping set.

Reopening, document intake, or changed mappings invalidate affected exports. History lists expose `invalidated_at` and `invalidation_reason`; superseded download endpoints return HTTP 409. Changed mappings also require renewed approval.

Document detail includes persistent `warnings`. Field detail includes `review_candidate_id`, `reviewer_id`, and `validation_error`. Audit decision details preserve previous/new review values, complete notes, source candidates, and invalidated reviews.

## Authenticator and demo destination APIs

`POST /api/auth/login` returns either the existing `{user, csrf}` session response or `{mfa_required: true, challenge, expires_in_seconds}` without a session. Submit `{challenge, code}` to `POST /api/auth/mfa/verify` to obtain the session. A code can be a current authenticator code or unused recovery code. Validation never echoes secret inputs. Failed proof returns 401 and retains a bounded attempt counter.

Authenticated endpoints (mutations require CSRF):

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/auth/mfa/status` | GET | Enabled/required status and unused recovery count |
| `/api/auth/mfa/enroll` | POST | `{password}`; return setup key and otpauth URI |
| `/api/auth/mfa/confirm` | POST | `{code}`; enable factor, return recovery codes once |
| `/api/auth/mfa/recovery-codes` | POST | `{password, code}`; replace recovery codes |
| `/api/auth/mfa/disable` | POST | `{password, code}`; allowed only for optional policy |
| `/demo-notary` | GET | Fictional case-management browser workspace |
| `/api/demo-notary/cases` | GET | Read workspace cases through signed TLS proxy |
| `/api/demo-notary/cases/{id}/stage` | POST | Reviewer/admin `{stage, expected_revision}` |

Mandatory MFA restricts an unenrolled session to identity/configuration, enrollment and logout; case APIs return 403. Factor activation and changes revoke other sessions. TOTP replay, expired challenges and consumed recovery codes are rejected. Destination stages are `received`, `in_preparation`, `ready_for_review`; stale revisions return 409, other workspace case IDs return 404.
