# LexFlow API — Functional Prototype

**Release:** 0.12.0-prototype · **Updated:** 30 October 2026

Interactive OpenAPI docs: `http://127.0.0.1:8000/docs` after server starts. All endpoints are JSON unless otherwise noted.

OpenAPI/Swagger pages are disabled in the hardened profile. All API responses use `Cache-Control: no-store`. Requests must use an allowed Host name; the hardened profile requires HTTPS.

The default Python/Docker port is 8000; use port 3000 when following the README's explicit Uvicorn command. API authorization always derives the workspace from the authenticated user, not a client-supplied tenant ID.

## Structured case records and file adapters

- `GET /api/case-data/schema` — authenticated JSON Schema for the versioned case model.
- `GET /api/connectors` — file-adapter capabilities, supported formats, scope and verification requirements. ProNotar32 reports `specification_required` and `latest_vendor_supported`, with no verified build or available formats.
- `GET /api/matters/{id}/case-data` — `data`, `revision`, `reviewed_by`, `reviewed_at`, `suggested_designation`. An unsaved case has revision 0. Also included as `case_data` in matter detail.
- `PUT /api/matters/{id}/case-data` — any authenticated workspace member may prepare an open matter using `{ "expected_revision": 0, "data": { "schema_version": 1, "participants": [], "properties": [], "tasks": [] } }`. Replaces the full structured document; omitted fields use model defaults. Saves increment revision and clear case review. Approved/exported matters must be reopened; stale revisions return 409. Unsupported fields and invalid relationships return 422. Source-document references must belong to the matter, and master cases to the workspace.
- `POST /api/matters/{id}/case-data/review` — reviewer/admin; `{ "expected_revision": 1 }`. Requires a source document and a source link or verification note for every participant/property. Review must precede final approval. Field/source changes and reopening invalidate it and increment revision.
- Existing export preview and generation endpoints now accept `connector=case_bundle` with `format=json` (preview query `fmt=json`). The bundle includes the complete structured case and source/review metadata; it does not transmit data or claim vendor compatibility. `pronotar32` returns 409 until an import adapter is verified. `case_bundle` with CSV returns 422.

All writes require CSRF. Existing flat export/transfer formats remain unchanged and omit structured records. See [ProNotar extension guide](PRONOTAR_EXTENSION.md) for the full contract and a synthetic example.

## Workflow learning

- `GET /api/workflows` — tenant-scoped rule list.
- `POST /api/workflows/preview` — reviewer/admin; `{ "matter_type": "property_purchase", "field_key": "buyer_name", "label": "Erwerbende Person", "sample_text": "Erwerbende Person: Anna Beispiel" }`. Examples are transient; response includes suggested candidates and `sample_stored: false`.
- `POST /api/workflows` — admin; save `matter_type`, `field_key`, `label`, optional `enabled`. The API persists no sample text. Rules use escaped literal labels followed by a colon or equals sign, never user-supplied regex. Limit: 100 rules per workspace.
- `PATCH /api/workflows/{id}` — admin; `{ "enabled": false, "expected_version": 1 }`. A stale version returns 409.
- `GET /api/workflows/{id}/versions` — configuration history.

Learned rules apply to future intake for their workspace and matter type. They create unverified candidates, preserving conflict checks and required human confirmation. Existing documents and approvals are not silently reprocessed. Destination mappings remain in `/api/settings/mappings`.

## Integration adapters

- `GET /api/integrations` — latest 100 transfers with attempt counts, latest 30 local receiver records, `notary_configured` and `webhook_configured`, scoped to the workspace.
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

The receiver must verify the HMAC over the exact raw request bytes and timestamp freshness, scope idempotency to `workspace_id` plus key, and return a 2xx JSON response `{ "accepted": true, "receipt_id": "destination-receipt-123" }`. Receipts permit 1–128 word characters, dots or hyphens. HTTP 4xx records state `failed`. Network errors, 5xx, redirects or missing acceptance receipts record state `uncertain`. Redirects and environment proxy settings are disabled; TLS certificates are verified. Endpoint secrets never appear in API responses. The receiver must independently commit before acknowledging and enforce idempotency across a crash between its write and LexFlow's receipt commit.

NotaryDesk Demo also requires this acknowledgment contract; a generic configured target can opt into it with `require_signed_receipt: true`:

```text
X-LexFlow-Receipt-Signature: sha256=HMAC-SHA256(secret, raw_response_body)
```

```json
{
  "accepted": true,
  "receipt_id": "destination-receipt-123",
  "idempotency_key": "original-transfer-key",
  "payload_sha256": "sha256-hex-of-exact-request-body"
}
```

The signing secret is the workspace target's configured secret. NotaryDesk accepts request timestamps within 300 seconds and signs its responses. LexFlow verifies the response signature, original key and transmitted-body digest before accepting a signed receipt. The generic adapter's default contract validates the TLS connection and acceptance fields; a signed response is required only when configured.

`preview_hash` is LexFlow's approval fingerprint: SHA-256 of `json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")`. The transmitted body uses compact JSON with `separators=(",", ":")`; its `payload_sha256` is a separate digest over those actual bytes. Return the dry run's `preview_hash` unchanged rather than substituting a receipt digest. Keys allow 8–100 ASCII letters/digits/underscores/hyphens.

A durable integration job records the payload and destination fingerprint before network I/O. A 120-second lease prevents approval-invalidating edits; unrelated database writes can proceed while the HTTPS client uses 10-second timeouts. These are HTTP timeouts, not a total wall-clock deadline. Transfer states include `pending`, `sending`, `accepted`, `failed`, `uncertain` and `cancelled`. Accepted keys replay without sending; active leases return an in-progress receipt. A restart can resume pending/expired sends through `python -m lexflow.manage deliver-pending`. Stale approvals, changed destinations or revoked reviewer access cancel recovery. Uncertain outcomes require explicit same-key retry after destination inspection. A late acceptance can have `superseded: true` when newer source approval exists; it cannot mark that newer version exported. A scheduled worker and high-volume reconciliation remain deployment work.

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

- `POST /api/auth/login` — `{ "email": "admin@keller.demo", "password": "LexFlowDemo2026!" }`; returns either a session/CSRF response or an MFA challenge, as described below.
- `GET /api/auth/me` — authenticated user, CSRF token, demo flags.
- `POST /api/auth/logout` — invalidate session.
- `POST /api/auth/change-password` — `{ "current_password": "...", "new_password": "..." }`; retains the current session, revokes others, invalidates reset links/challenges and preserves MFA.
- `POST /api/auth/forgot-password` — `{ "email": "admin@keller.demo" }`; public, rate limited. Returns a neutral `message` and `delivery` mode. In demo mode, only seeded sample accounts also receive a `demo_reset_path` and `expires_in_minutes: 30`. SMTP mode never returns a token.
- `POST /api/auth/reset-password` — `{ "token": "...", "new_password": "12–128 characters", "confirm_password": "same password" }`; public, rate limited. Consumes a valid link, changes the password and revokes every session and pending reset link for the account. Returns `{ "ok": true, "message": "..." }`; requires a fresh sign-in.

Authenticated state-changing requests require the `lexflow_session` cookie and `X-CSRF-Token` from login or successful MFA verification. The web interface includes these automatically. Login, MFA challenge verification and password recovery are public proof endpoints; enrollment and factor changes require both a session and CSRF.

| Operation | Analyst | Reviewer | Admin |
|---|---|---|---|
| Read own workspace, create matters and ingest documents | Yes | Yes | Yes |
| Prepare/update case details on an open matter | Yes | Yes | Yes |
| Confirm the current case-details revision | No | Yes | Yes |
| Preview/download current approved output | Yes | Yes | Yes |
| Confirm/clear fields, approve, reopen, generate output or send a transfer | No | Yes | Yes |
| Preview learned rules | No | Yes | Yes |
| Save/pause learned rules, change mappings, list members, set baselines | No | No | Yes |
| Read NotaryDesk cases | Yes | Yes | Yes |
| Change NotaryDesk preparation stage | No | Yes | Yes |
| Manage own password/MFA/sessions and record work observations | Yes | Yes | Yes |

Every permission also requires the account's MFA policy to be satisfied. Analysts can create/intake records; their restrictions apply to review, approval, output and configuration.

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
| `/api/matters/{id}` | GET | Fields, documents, exports, structured case state and combined approval blockers |
| `/api/case-data/schema` | GET | JSON Schema for version-1 structured records |
| `/api/connectors` | GET | File adapter capabilities and version-verification status |
| `/api/matters/{id}/case-data` | GET/PUT | Read/replace complete case details (any authenticated workspace member; PUT requires open matter and matching revision) |
| `/api/matters/{id}/case-data/review` | POST | Confirm current case revision (reviewer/admin) |
| `/api/intake/text` | POST | Ingest pasted text; optionally external AI opt-in |
| `/api/intake/upload` | POST | Multipart ingestion of up to six files |
| `/api/documents/{id}` | GET | Extracted text and metadata |
| `/api/documents/{id}/download` | GET | Download original document |
| `/api/matters/{id}/fields/{key}/confirm` | POST | Human confirm (reviewer/admin) |
| `/api/matters/{id}/fields/{key}/clear` | POST | Clear reviewed value (reviewer/admin) |
| `/api/matters/{id}/approve` | POST | Validate sources, fields and saved case review, then approve (reviewer/admin) |
| `/api/matters/{id}/reopen` | POST | Invalidate approval to edit (reviewer/admin) |
| `/api/matters/{id}/export/preview` | GET | Preview flat JSON/CSV or complete JSON bundle (approved only) |
| `/api/matters/{id}/exports` | POST | Generate local output using a supported file profile (reviewer/admin) |
| `/api/exports` | GET | Export history |
| `/api/exports/{id}/download` | GET | Download approved export |
| `/api/audit` | GET | Tenant-scoped audit events |
| `/api/settings/mappings` | GET/PUT | Read/update connector mappings (PUT: admin only) |
| `/api/settings/users` | GET | List own workspace users (admin only) |

### Example — ingest text

`POST /api/intake/text`:

```json
{
  "matter_id": "matter-demo-intake",
  "filename": "synthetic_message.txt",
  "text": "Käufer: Anna Schmidt\nKaufpreis: 850.000,00 EUR",
  "use_external_ai": false
}
```

### Example — confirm source value

`POST /api/matters/{matter-id}/fields/land_register/confirm`:

```json
{
  "candidate_id": "the-suggestion-id-from-GET-matter",
  "note": "Verified against updated synthetic source"
}
```

Or use `{ "value": "München Blatt 812", "note": "Manual check" }` to enter a reviewed value.

### Example — export

`POST /api/matters/{matter-id}/exports`:

```json
{
  "format": "json",
  "connector": "notary_demo"
}
```

The payload includes an explicit marker `not_a_live_transmission: true`. This endpoint does **not** connect to BNotK, XNP or notary case-management software.

Approval requires at least one source document, valid confirmed required fields, no unresolved conflicts (including optional fields), and current case review if structured data has been saved. Field confirmation returns HTTP 422 for invalid amounts, dates, email addresses, or empty/invalid names. Monetary values use exact decimal normalization and dates use ISO format.

Export preview accepts `fmt=json|csv`; generation uses the `format` body field. Both apply the same approval gates. Supported connector behavior is:

| Connector | Formats | Scope / result |
|---|---|---|
| `approved_export` (default) | JSON, CSV | Mapped confirmed extraction fields |
| `notary_demo` | JSON, CSV | Mock notary file with the same flat scope |
| `case_bundle` | JSON only | Complete versioned case snapshot, source metadata and review provenance |
| `pronotar32` | None enabled | HTTP 409; import contract/build unverified |

Mapping destinations must be unique across the saved flat mapping set. The bundle uses internal keys and structured records, not those configurable destination keys. CSV with `case_bundle` returns 422. The default API connector remains `approved_export`; callers must explicitly request `case_bundle` for complete records. The browser selects that profile by default for a matter with saved case data. File profiles are separate from `/api/integrations` delivery destinations.

Reopening, document intake, or changed mappings invalidate affected exports. History lists expose `invalidated_at` and `invalidation_reason`; superseded download endpoints return HTTP 409. Changed mappings also require renewed approval.

Document detail includes persistent `warnings`. Field detail includes `review_candidate_id`, `reviewer_id`, and `validation_error`. Audit decision details preserve previous/new review values, complete notes, source candidates, and invalidated reviews.

### Example — prepare, review and export case details

For an open matter that already has a source document and confirmed required fields, first read `GET /api/matters/{id}/case-data`. An unsaved structure has revision 0. Send the complete replacement document with that revision:

```json
{
  "expected_revision": 0,
  "data": {
    "schema_version": 1,
    "category": "property_transaction",
    "naming_code": "KV",
    "designation": "Example Buyer KV",
    "participants": [
      {
        "id": "example-buyer",
        "entity_type": "person",
        "roles": ["buyer"],
        "name": "Example Buyer",
        "source_note": "Synthetic example; checked against this matter's source"
      }
    ],
    "properties": [],
    "tasks": []
  }
}
```

Submit this to `PUT /api/matters/{id}/case-data`. Optional omitted model fields receive defaults; this is a full replacement, not a patch. Preserve record IDs on later edits. Use `source_document_ids` containing actual document IDs from this matter when linking evidence; notes are the alternative when no document is selected.

After the successful save, a reviewer/admin submits the returned revision to `POST /api/matters/{id}/case-data/review`:

```json
{"expected_revision": 1}
```

Then approve with `POST /api/matters/{id}/approve`. Preview with `GET /api/matters/{id}/export/preview?connector=case_bundle&fmt=json` and generate via `POST /api/matters/{id}/exports`:

```json
{"connector": "case_bundle", "format": "json"}
```

Use the returned `download_url` with the authenticated session. The envelope contains `specification: lexflow-case-bundle-v1`, `not_a_live_transmission: true`, `vendor_import_verified: false`, `snapshot_sha256` and a `lexflow-case-v1` snapshot. A SHA-256 digest is not an import receipt. The [extension guide](PRONOTAR_EXTENSION.md#bundle-contract) defines its contents and encoding. The [larger synthetic example](../samples/09_structured_case.json) is the `data` object, not a full PUT request or a document-intake file.

Stale revisions, edits to approved/exported matters and unverified ProNotar output return 409. Missing review prerequisites or invalid record/source relationships return 422. A master case outside the workspace is unavailable (404). Analysts cannot review or generate files (403). There is no case-data DELETE endpoint: saving an empty structure still retains a revision and its review requirement. Review/approval do not auto-populate structured participants from flat extraction fields.

## Authenticator APIs

`POST /api/auth/login` returns either the existing `{user, csrf}` session response or `{mfa_required: true, challenge, expires_in_seconds}` without a session. Submit `{challenge, code}` to `POST /api/auth/mfa/verify` to obtain the session. A code can be a current authenticator code or unused recovery code. Validation never echoes secret inputs. Failed proof returns 401 and retains a bounded attempt counter.

Authenticated endpoints (mutations require CSRF):

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/auth/mfa/status` | GET | Enabled/required status and unused recovery count |
| `/api/auth/mfa/enroll` | POST | `{password}`; return setup key and otpauth URI |
| `/api/auth/mfa/confirm` | POST | `{code}`; enable factor, return recovery codes once |
| `/api/auth/mfa/recovery-codes` | POST | `{password, code}`; replace recovery codes |
| `/api/auth/mfa/disable` | POST | `{password, code}`; allowed only for optional policy |

Setup expires after ten minutes; confirmation returns ten single-use recovery codes once. Challenges expire after five minutes and allow at most five proof attempts. An authenticator code uses six digits and 30-second steps; the current/adjacent step is allowed only if newer than the previously consumed step. Recovery codes can be entered with their displayed hyphens. Password reset preserves the factor and unused codes.

Mandatory MFA restricts an unenrolled session to `/api/auth/me`, `/api/config`, logout, MFA status/enrollment/confirmation; case APIs return 403. Factor activation and changes revoke other sessions. TOTP replay, expired challenges and consumed recovery codes are rejected. A password-only enrollment session is not authorization to open case records.

## NotaryDesk Demo APIs

The fictional destination is available only with demo seeding and `LEXFLOW_DEMO_NOTARY=1` (the demo default). Its UI uses the LexFlow session. The proxy supplies the workspace from that user and talks to a separate loopback TLS receiver; no third-party account or vendor URL is required.

| Endpoint | Method | Purpose |
|---|---|---|
| `/demo-notary` | GET | Fictional case-management browser workspace |
| `/api/demo-notary/cases` | GET | Read latest 100 workspace cases through signed TLS proxy |
| `/api/demo-notary/cases/{id}/stage` | POST | Reviewer/admin `{stage, expected_revision}` |

Case responses include `id`, source `matter`, mapped `fields`, `source_matter_id`, `receipt_id`, `payload_sha256`, `stage`, `revision`, `received_at` and `demo: true`. Approved received values are read-only. Destination stages are `received`, `in_preparation`, `ready_for_review`; stale revisions return 409 and other workspace case IDs return 404. A disabled demo destination returns 404 on its UI/proxy routes and 503 when chosen for a dry run/transfer.

## Error handling

| Status | Meaning |
|---|---|
| 400 | Invalid/expired reset link, invalid authenticator confirmation or disabled external AI request |
| 401 | Missing/expired session or invalid sign-in/factor proof; a failed proof can be retried within challenge limits |
| 403 | CSRF failure, insufficient role or required MFA enrollment |
| 404 | Resource unavailable in the authenticated workspace, or demo notary disabled |
| 409 | Stale preview/revision, reused key with changed payload, changed destination, superseded export or approval-invalidating edit during an active delivery |
| 413 / 415 | Oversized/empty upload or unsupported type |
| 422 | Invalid request fields, mapping/value validation or unsatisfied approval gate |
| 429 | Rate limit; inspect `Retry-After` |
| 503 | Missing deployment/destination keys, unavailable service or failed response/artifact authentication |

For uncertain delivery, inspect the destination before retrying the original transfer key. Reusing that key after changing the approved payload returns 409. A fresh preview/key is for a deliberately new handoff, after resolving the prior outcome.
