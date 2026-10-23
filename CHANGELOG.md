# Changelog

## 0.10.0-prototype — 2026-10-22

- Added Workflow Studio with transient previews, tenant-scoped literal-label learning, version history and optimistic rule updates.
- Added local receiver records, approval-bound dry runs, signed HTTPS transfers, idempotency and explicit acceptance/uncertain receipts.
- Added a real folder intake agent with authenticated requests, atomic intake receipts and retry deduplication.
- Added Pilot Measurement with observed baselines, work timers, retry-safe observations, defined rates and CSV evidence.
- Added sign-in throttling, idle expiry, session revocation, host/CSP/security headers, per-workspace file encryption and HMAC audit checks.
- Added a dedicated HTTPS container profile, workspace provisioning, consistent snapshots and artifact rotation, plus implementation/security regression checks.

## 0.9.1-prototype — 2026-10-22

- Added polished password recovery screens, expiring single-use reset links, confirmation and session revocation, with a 12–128 character password policy.
- Added seeded-account demo reset delivery, optional TLS SMTP delivery, recovery rate limits, secret-free audit/validation responses and regression tests.
- Redesigned all interface templates with an ink, ivory and brass palette, locally bundled fonts, clearer source labels and consistent components.
- Enforced a 12px minimum font size across desktop and mobile layouts, with improved text contrast and responsive navigation.
- Added Start guided demo for a fresh synthetic conflict-review-export workflow.
- Rejected duplicate destination mappings and invalid reviewed currency, dates, emails and names.
- Blocked approval on optional-field conflicts and revalidated before export.
- Preserved previous/new corrections, full notes, source selections and invalidations in audit history.
- Parsed HTML email, supported attachments, mixed PDF pages and multipage TIFFs with persistent warnings.
- Made upload batches atomic across database changes and newly written files.
- Fixed modal buttons, saved correction editing, source display and connector preview refresh.
- Marked superseded exports and blocked further downloads after input, approval or mapping changes.
- Added Docker exclusions, tested dependency constraints, a separate Python 3.12 demo environment and regression checks.

## 0.9.0-prototype — 2026-10-22

- Runnable FastAPI backend, SQLite persistence, and responsive local web UI.
- Demo multi-tenant offices, Argon2 sessions, CSRF protection, roles.
- Intake for TXT, EML, PDF, DOCX and local OCR-capable scans.
- Transparent rules engine with four notarial matter schemas.
- Optional explicit external AI extraction configuration, disabled by default.
- Field candidate evidence, cross-document conflict detection, human review and approval.
- Connector field mappings, reviewed CSV/JSON exports and notary handoff simulator.
- Audit history, seed fixtures, comprehensive documentation and automated API tests.

**Prototype notice:** No live vendor connector, security certification, legal opinion, document-signing, or production readiness is claimed.
