# Security, Confidentiality and Regulatory Limitations

**Release:** 0.12.0-prototype · **Updated:** 30 October 2026

Implementation evidence is in the [test plan](TEST_PLAN.md); operational setup is in [deployment and recovery](DEPLOYMENT.md). The default demonstration and hardened deployment have different active controls.

The [EU safety, security and data-protection blueprint](LexFlow_EU_Safety_Security_Blueprint.pdf) provides a 24-page implementation roadmap based on the October 30, 2026 project state and official sources. It distinguishes current mechanisms from deployment-specific GDPR, AI Act, CRA, NIS2 and German notarial requirements, proposed controls and independent assurance. It is not a certification or a legal opinion.

**This application is a demonstrator, not a security-certified product. Do not put actual client or notarial secrets into its preconfigured demo workspace.**

## Controls already implemented

- Authenticator-app MFA with encrypted secrets, expiring challenges, replay prevention, hashed single-use recovery codes and mandatory enrollment in the hardened profile.
- Authenticated snapshots, verified portable restores, revoked restored sessions and a durable approval-bound delivery outbox.
- Argon2 password hashing, equal password-verification work for unknown users, persistent sign-in throttling and 30-minute idle session expiry.
- Explicit allowed hosts, CSP, frame blocking, MIME sniffing protection, private API caching policy and HSTS on HTTPS responses.
- Optional per-workspace Fernet encryption for new original files and exports, with key-ring rotation tools. Database text/metadata still need encrypted volumes.
- Per-workspace HMAC audit chains, verification and externally retainable checkpoints.
- Hardened HTTPS deployment profile with restricted application container and dedicated-office provisioning/backup tools.
- Single-use password reset tokens (stored as SHA-256 hashes), 30-minute expiry, session revocation and persistent recovery rate limits.
- Optional TLS-protected SMTP reset delivery with a configured HTTPS link origin; generic responses for known/unknown accounts. Local demonstration links are restricted to the four publicly documented seed identities and require demo mode.
- Cryptographically random server sessions; only hashed session tokens are stored in SQLite.
- HttpOnly and SameSite Strict session cookies (Secure cookies opt-in for HTTPS deployments).
- CSRF token verification on state-mutating authenticated endpoints.
- Matter, structured-case, document, candidate, export, audit and mapping operations scoped to the authenticated tenant.
- Role checks: analyst vs reviewer vs administrator.
- All SQL uses parameterized values.
- File extension allowlist and configurable file size limits.
- Local-only document processing by default.
- Explicitly configured external AI plus per-document opt-in, with reviewer approval still mandatory.
- Original document SHA-256 hashes and evidence provenance.
- Approval gate before file export, including current structured-case review when records have been saved.
- Optimistic case revisions reject stale saves/reviews. Source changes, field confirmation/clearing and reopening invalidate case review; changes to approved records require reopening.
- Structured source references must belong to the matter; representative links must point to other people in the same case. Master-case links must remain in the workspace and cannot form cycles.
- ProNotar32 file generation stays disabled until an adapter has a verified import contract; the complete LexFlow JSON bundle is explicitly marked as a local, unverified vendor handoff.

## Structured-case boundaries

Analysts may enter case details. Reviewers and administrators may both prepare and confirm them; the application does **not** enforce a separate person for preparation and approval. Each participant/property needs a case source reference or a verification note before case review. These links and notes record provenance but do not prove the facts, verify identity or establish representative authority. Staff must reconcile manually entered records with documents and the separately reviewed extraction fields.

Dates, email syntax, shares, record IDs and relationships receive structural validation. Company register numbers, tax identifiers, nationality, marital status and property rights are not checked against authoritative registries. There is no automatic cross-case participant matching, legal validation or extraction of every photographed questionnaire field.

The `snapshot_sha256` in a structured bundle is a content digest, not a signature, approval credential or vendor receipt. Bundles contain personal/company/property details and review notes; downloading them creates a copy outside the application's recall controls. Original document bytes and local file paths are excluded, but filenames and document hashes remain in the bundle. The case JSON and full previous/new values in audit events require encrypted database/backup storage and an appropriate retention policy, just like the existing extracted text.

Case categories, naming codes and template references are metadata. Execution tasks record status and optional due dates; they do not implement deadline notifications, external filings, billing or Word generation. The latest ProNotar-supported release is a target policy only; no exact version, XML schema or successful import has been verified. See [the extension guide](PRONOTAR_EXTENSION.md).

## Critical work required before production

1. **Identity:** remove demo accounts, add SSO/OIDC, managed MFA recovery, breached-password screening, suspicious sign-in monitoring and stronger session lifecycle policy; harden reset delivery with durable queues, monitoring and account recovery policy.
2. **Network/application:** validate the supplied HTTPS profile in the target environment, add upload scanning and DDoS protections, review proxy trust and independently test all controls.
3. **Storage/keys:** deploy encrypted database/backup volumes, managed key custody and isolated infrastructure. File encryption and rotation are implemented, but extracted text/metadata are not application-encrypted.
4. **Tenant isolation:** decide on dedicated database/object store/keys per client or equivalent architecture; arrange independent red-team isolation tests.
5. **LLM processing:** conduct DPIA and legal review, select contractually acceptable processors and residency, enforce DPA, no-training/no-retention settings where needed; redact data when feasible; test prompt injection and hallucinations.
6. **OCR/extraction:** build quality benchmarks for German notarial document families, human acceptance thresholds, versioned field definitions, source-page anchoring and adversarial evaluation. A 28-case versioned synthetic regression benchmark is supplied, but is not a representative office sample. Current confidence numbers are not calibrated.
7. **Notarial integrations:** adapt the implemented approval checks, dry-run, signing, durable intent and idempotency controls to an authorized vendor interface; validate its permissions, acknowledgment, reconciliation and rollback/import behavior. NotaryDesk is a fictional local test destination.
8. **Audit:** move verified events/checkpoints to external write-once storage, establish immutable retention and clock synchronization; local HMAC chains alone do not prevent coordinated truncation by an administrator.
9. **Operations:** repeat the implemented backup/restore drill in the actual deployment, agree recovery objectives and implement retention, observability, incident response, vulnerability management and regional hosting controls.
10. **Compliance:** qualified German notarial/legal review, including confidentiality and service-provider arrangements under applicable BNotO/NotAktVV provisions, GDPR processing agreements, and client deployment terms.

## Known technical limitations

- SQLite is suitable for a limited demo but not for concurrent enterprise multi-node workloads.
- Authenticator-app 2FA is implemented; SSO and self-service user provisioning remain unavailable. Operator provisioning creates a dedicated workspace/admin; sign-in and password recovery have separate rate limits.
- MFA is optional for default seeded accounts. Mandatory enrollment is enforced in the hardened profile. No self-service lost-factor reset or managed recovery desk is supplied; password reset deliberately preserves the existing factor. Retain unused recovery codes separately.
- SMTP recovery requires operator configuration; background email delivery is not durable. Demo mode intentionally displays links only for seeded, publicly documented identities and must not be used for confidential data.
- No automated DLP, antivirus scanning, malware quarantine or content disarm.
- Original files/exports can be encrypted per workspace. SQLite text, structured case records, candidates, receiver payloads and audit details require encrypted infrastructure volumes; no managed key service is supplied.
- A folder intake agent and signed generic HTTPS destination adapter are included. Native Outlook/Word/DMS and vendor-specific notary/BNotK/XNP integrations are not implemented.
- NotaryDesk runs a separate TLS receiver/database inside the same application process and data volume, and shares LexFlow browser authentication. Its received payloads are encrypted; receipt/stage/history metadata is not whole-database encrypted. It is a demonstration boundary, not an independently hosted vendor.
- The `notary_demo` file-export connector generates a file. The `demo_notary` delivery connector transmits to fictional NotaryDesk Demo over local verified TLS; this is not a real vendor integration.
- `case_bundle` is the only current output containing the new structured records. Flat JSON/CSV profiles and existing delivery payloads omit participants, properties and tasks. A ProNotar export request is rejected while its adapter is disabled.
- No certified electronic signatures, notarization, legality verification, land-register lookup, AML/KYC, jurisdiction checks or legal advice.
- Scanned PDFs are OCR'd locally only where Tesseract and PDFium are available, with up to 12 OCR pages per document. Mixed PDFs are checked per page; image files process up to 12 frames. Failed or skipped pages/frames produce warnings.
- External AI output is an unverified suggestion; source quote may be unavailable, model output can be incorrect, and real legal processing requires stricter provider arrangements.
- Content parsing for complex nested/graphic PDFs and unusual Word files remains limited.
- Approval is a workflow control, not formal legal authorization or electronic signature.
- HMAC checks detect edited/interior missing audit events when the signing key is protected. External trusted checkpoints are necessary to detect coordinated tail truncation; the local database is not immutable.
- A snapshot using local fallback keys includes those keys. Store the whole snapshot privately; external audit/storage/MFA keys are excluded and must be preserved separately when configured. Recovery verifies bytes and bindings but does not provide a scheduled backup service or managed key custody.
- Delivery recovery is an operator command, not an installed background worker. Uncertain receipts require destination inspection and explicit same-key retry. A receiver must enforce idempotency independently; the generic HTTPS contract does not provide cross-system distributed transactions.
- Superseded exports remain on disk as historical artifacts, but new downloads are blocked after reopening, source changes or mapping changes. Already downloaded copies cannot be recalled.

## Threats / mitigation targets

| Threat | Demo mitigation | Required production addition |
|---|---|---|
| Cross-tenant reading | Tenant-scoped SQL + paths + tests | Dedicated isolation and external penetration testing |
| Unauthorized edits | Roles + CSRF + authenticator MFA | Granular policies, approval separation of duties |
| Poisoned legal data | Conflict detection + human review | Page-level provenance, calibrated extraction, verification protocols |
| Data loss / theft | Authenticated snapshots, portable restore, optional artifact encryption | Encrypted volumes, managed keys, scheduled restore drills |
| Tampering with audit | HMAC chain + verification/checkpoint export | External immutable retention and trusted checkpoints |
| Malicious uploaded file | Extension/size checks | Malware scanning, sandbox parsing and CDR |
| Credential stuffing | Argon2 + persistent limits + authenticator MFA | Threat telemetry and distributed abuse protection |

This document is technical product guidance, not legal advice.
