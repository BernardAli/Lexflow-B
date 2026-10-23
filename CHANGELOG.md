# Changelog

## Presentation video — 2026-10-23

- Added a 4:04 narrated 1080p presentation adapted from the current guide, with 12 chapters, visible English captions and synthetic screenshots.
- Added an offline browser player, full narration transcript, WebVTT captions, source provenance and reproducible local video build tooling.
- Linked the video from the README and presenter PDF and documented media build/playback checks.

## Documentation refresh — 2026-10-23

- Aligned the README, architecture, roadmap, API, deployment, security and verification guides with v0.11; separated delivered features from customer-pilot milestones.
- Documented MFA/session permissions, the three delivery destinations, signed acknowledgment hashes, transfer recovery, environment loading and portable/container restore constraints.
- Updated the 12-page presenter PDF and added its source, optional build dependency and six synthetic screenshots to the repository.

## 0.11.0-prototype — 2026-10-23

- Added the fictional NotaryDesk Demo: separate encrypted SQLite case store, local TLS receiver, signed acceptance receipts, case register, preparation stages and delivery-evidence tabs.
- Added authenticator-app MFA with encrypted identity-bound secrets, expiring challenges, replay prevention, single-use recovery codes and mandatory enrollment in the hardened profile.
- Persisted delivery intents and bounded leases before network I/O; released the SQLite writer lock during delivery, protected approvals during active sends and added crash recovery with the original transfer key.
- Added authenticated snapshot manifests, artifact/audit/MFA/destination verification and portable restores that rebase file paths and revoke sessions.
- Added a versioned 28-case synthetic extraction benchmark and CI release checks. Fixed empty field labels consuming subsequent lines.
- Extracted shared matter/approval services and updated deployment, recovery and demonstration documentation.

## Interface update — 2026-10-23

- Grouped related sections into shared tabs across Overview, matters, intake, exports, integrations, pilot measurement, security and settings.
- Added keyboard navigation, labelled panels, mobile scrolling, section counts and selection retention during page updates.
- Preserved form drafts, selected upload files and transfer previews when switching tabs; cleared tab preferences on sign-out.
- Opened the matter's Exports tab after file generation and limited the workspace-members tab to administrators.

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
