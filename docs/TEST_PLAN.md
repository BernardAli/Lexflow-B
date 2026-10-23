# Demonstration and Verification Checklist

| ID | Scenario | Expected outcome |
|---|---|---|
| A01 | Visit `/api/health` | HTTP 200 and prototype status |
| A02 | Open app without login | Login screen; protected API returns HTTP 401 |
| A03 | Login as admin@keller.demo | Dashboard for Notariat Keller only |
| A04 | Open 2026-KEL-0041 | Land register 812/872 conflict with two sources |
| A05 | Try approving before review | HTTP 422; approval blocked |
| A06 | Confirm all required fields | Approval button unlocks |
| A07 | Approve matter | State changes to approved; audit event written |
| A08 | Export as JSON | Downloadable mapped file, no live transmission |
| A09 | Export as CSV | BOM-prefixed UTF-8 CSV, mapped key-value rows |
| A10 | Reopen approved matter | Matter becomes in_review; approval reset |
| A11 | Upload another document | Existing confirmations cleared for re-review |
| A12 | Login as analyst | Can view but cannot confirm, approve or export |
| A13 | Login as reviewer | Can confirm; cannot alter admin mappings |
| A14 | Login as Weber admin | Keller matter cannot be read or modified |
| A15 | Remove CSRF header | State mutation returns HTTP 403 |
| A16 | Upload an unsupported extension | HTTP 415 |
| A17 | Opt into external AI without config | HTTP 400, no external transmission |
| A18 | Process sample PDF | Extract buyer, seller, price, address and land register |
| A19 | Process sample DOCX | Recognize labeled values in two-column table |
| A20 | Process sample EML | Extract plain-text email body |
| A21 | Start guided demo twice | Two independent synthetic matters with the 812/872 conflict |
| A22 | Confirm required fields with an optional conflict outstanding | Approval remains blocked |
| A23 | Save duplicate destinations, including a partial update | HTTP 422 and mappings unchanged |
| A24 | Confirm invalid currency/date/email | HTTP 422; candidate selection also validates |
| A25 | Correct twice, clear, then add documents | Earlier values, complete notes and source decisions remain in audit |
| A26 | Upload good TXT then malformed PDF | No batch documents, reviews, files or audit changes persist |
| A27 | Simulate storage failure on the second file | Database rolls back; newly written files are removed |
| A28 | Process HTML email with a PDF attachment | Both bodies and attachment data appear; unsupported attachments warn |
| A29 | Process mixed PDF or multipage TIFF | OCR runs per needed page/frame; failures identify the affected page/frame |
| A30 | Reopen, change input, or change mappings after exporting | Previous output is superseded and download returns HTTP 409 |
| A31 | Use Close, Cancel, Clear review and edit corrections | Buttons work; saved correction/note/source remain selected |
| A32 | Change export connector profile | Preview refreshes to match generated payload |
| A33 | Use Forgot password for a seeded account | Clearly labeled local reset link appears; no email is sent |
| A34 | Set and confirm a new password | New password works; old password and previous sessions fail |
| A35 | Reuse/expire a link or request a newer one | Invalid link rejected; no password change |
| A36 | Submit mismatched, short or oversized passwords | Error shown; valid reset token remains usable |
| A37 | Request unknown/non-seeded account in demo mode | Neutral response; no reset link exposed |
| A38 | Repeated requests or failed redemptions | HTTP 429 with Retry-After; counters expire |
| A39 | Configure SMTP with test transport | TLS delivery uses configured origin; API response contains no token |
| A40 | Open reset link directly on desktop/mobile | Public reset form loads, errors are accessible, all text is at least 12px |

Additional platform verification:

| ID | Scenario | Expected outcome |
|---|---|---|
| B01 | Test a new label rule and save it | Preview values stay transient; only label/schema configuration persists |
| B02 | Upload a matching future document | Tenant/matter-specific learned candidate appears and still needs review |
| B03 | Pause a rule or submit a stale rule version | New version recorded; stale updates return 409 |
| B04 | Attempt another tenant's rule or receipt | No disclosure; missing resources return 404 |
| B05 | Dry run an unapproved matter | Transfer blocked |
| B06 | Send an approved preview twice with one key | One destination record, one receipt; second request replays |
| B07 | Change approved content after preview | Fingerprint check rejects stale preview |
| B08 | Mock HTTPS rejection/timeout/acceptance | Rejected/uncertain/accepted outcomes remain distinct; secrets are not returned |
| B09 | Run folder agent twice on the same file | One document and atomic intake receipt; second run reports already received |
| B10 | Inspect pilot with no baseline/time/transfers | Missing evidence stays empty; no fabricated savings or success rate |
| B11 | Add baseline and work sessions, retry an observation | Correct per-case totals and rates; observation key prevents double counting |
| B12 | Alter an audit event directly | Chain verification reports invalid |
| B13 | Configure workspace file keys and rotate | Stored bytes are encrypted; authenticated download reproduces original bytes |
| B14 | Back up a workspace | Consistent database/files and audit fallback key are copied to a new destination |
| B15 | Start incomplete hardened configuration | Startup fails closed |
| B16 | Provision one dedicated workspace and start with HTTPS | Secure cookies, no seeded credentials, hidden API docs and valid audit verification |
| B17 | Use forged Host or exhausted sign-in attempts | Host rejected or 429 with Retry-After |
| B18 | Leave a session idle or revoke other sessions | Expired/revoked sessions fail; retained current session continues |

Run automated checks from the project root:

```bash
.venv-demo/bin/python -m pytest -q
npm ci
npm run test:ui
```

Tests create isolated temporary data directories, leaving your running demo environment intact.

Python 3.12 is the tested demo runtime. Interface checks use jsdom and Node.js; they do not replace a graphical browser walkthrough. OCR tests mock recognition so they run without installing Tesseract. SMTP tests mock both TLS transports and never send email. Password reset tests cover all demo roles, concurrent redemption, expiration, replay, session revocation, account boundaries, password-change invalidation, private errors and rate limits. Docker execution and Windows PowerShell launch require their respective platforms.

The new workspaces were also exercised end-to-end in Chromium at widths 320, 390, 768 and 1440 pixels, checking visible text at least 12px, text contrast and horizontal overflow. The real folder agent was run against a temporary HTTP server twice to verify receipt replay. Docker execution, Caddy/ACME and live third-party SMTP/webhook destinations were not available; transports are mocked in automated checks.
