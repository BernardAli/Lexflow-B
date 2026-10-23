# Product Architecture and Boundaries

## High-level view

```text
                Browser UI (HTML/CSS/vanilla JS)
                       │ HTTPS/HTTP
                       ▼
                 FastAPI application
              ┌────────┼─────────────┐
              │        │             │
          Session/  Matter +      Ingestion
          Role/CSRF Review API    / Parsing
              │        │             │
              └────────┼─────────────┤
                       ▼             ▼
                 SQLite DB       Rules extractor
                  │  │           (local by default)
                  │  │                  │
                  │  └────► Optional external AI
                  │           (2-stage opt-in)
                  ▼
         Tenant-scoped files
         originals + approved exports
                  │
                  └──► Mock connector / JSON / CSV
                        LOCAL RECEIVER + OPT-IN SIGNED HTTPS WEBHOOK
```

## Main entities

- **Tenant:** isolated demo office, keyed by `tenant_id`.
- **User:** assigned to exactly one tenant; admin, reviewer or analyst.
- **Session:** short-lived random token stored as SHA-256 hash, plus CSRF token.
- **Matter:** case metadata, matter type, status and explicit approval.
- **Document:** original bytes on disk, extracted text in database, digest and tenant scope.
- **Candidate:** extracted value, confidence heuristic, originating document and evidence text.
- **Field review:** human-confirmed field value, candidate link (or manual override), reviewer and time.
- **Export:** stored mapped JSON/CSV, approved matter and creator.
- **Audit:** HMAC-chained per workspace, with verification and externally retainable checkpoints. The database is not immutable.

## Matter states

```text
new --document intake--> in_review --all required fields confirmed--> approved
                                 ^                                 │
                                 │                                 ▼
                                 └────-- explicit reopen <-- exported (file)
```

Uploading a new document invalidates existing field confirmations and the current approval, so previously verified values must be reviewed in the context of the new evidence. Earlier exports are marked superseded and their download endpoints return HTTP 409. Files downloaded previously cannot be recalled. Mapping changes also reset approval for affected approved matters. Review changes and invalidations preserve previous values, candidate IDs, reviewers and notes in tenant-scoped audit events.

## Matter schemas

- `property_purchase` — buyer, seller, price, property address, land register; optional email/date/parcel.
- `inheritance` — deceased, heir, estate reference.
- `company_formation` — company name, founder, registered address.
- `general` — client name and matter reference.

Local extraction intentionally uses labeled values, not inferred legal opinions. Numeric confidence represents a rule or model hint, not a validated statistical probability. This conservative approach makes failure modes visible but does not fully solve complex legal data extraction.

## Isolation and request flow

Every authenticated API query scopes records by `tenant_id`. Documents and exports also use tenant-specific filesystem subdirectories. The sample tenants can be used to demonstrate blocked cross-workspace access. This is **logical tenant isolation, not equivalent to the dedicated per-tenant databases, KMS keys and storage accounts shown as a target architecture in the original presentation**.

## Approvals and simulated connectors

1. Original document is uploaded or text is pasted.
2. Every file is parsed before external processing or durable changes. Original files, document metadata, candidates, review invalidation and audit events are saved as one batch; storage errors roll back the database and remove the new files. Parsing warnings remain available in the document viewer.
3. The API collates candidates from all documents, normalizes comparison values and flags conflicts.
4. Reviewer confirms each required field using a candidate or verified manual correction.
5. Matter is explicitly approved only when required fields have valid, confirmed values, every optional or required conflict has been resolved, and at least one source document exists.
6. Workspace-specific field mappings convert internal keys to destination field paths.
7. JSON or CSV is generated as a local file, and an audit event is recorded.

`notary_demo` remains a file export. The local receiver stores simulated records and returns receipts. An optional workspace-specific signed HTTPS webhook transmits only approved, previewed data to a configured destination; it is not a vendor-specific notary integration.

## Planned connector interface

Production systems should introduce a connector interface with `validate_access()`, `map_schema()`, `dry_run()`, `write_approved_data()` and `audit_receipt()` methods, each with explicit least-privilege credentials and idempotency keys. Use documented official APIs/imports before attempting browser or UI automation, and validate with the relevant vendor, regulator and notarial customers.

## Versioned workflows, integration receipts and pilot evidence

`workflows.py` stores only schema/field/literal-label configuration, version and enabled state. Preview text is transient. Escaped labels prevent arbitrary regex execution. Rules are tenant scoped and applied before normal candidate review to future intake; they never auto-confirm a field.

`integrations.py` reuses the same approval and mapping validation as exports. A dry-run fingerprint binds the reviewed preview to delivery. Idempotency is tenant scoped; the local receiver writes its payload and receipt in the same transaction. Agent intake receipts commit with documents. HTTPS destinations must verify signatures, enforce workspace/key idempotency and acknowledge receipt. A bounded synchronous call serializes this prototype; a durable outbox is a future production requirement.

`pilot.py` derives field/activity rates from persisted workflow state and audit events, with explicit numerators and denominators. Work observations and operator baselines are recorded separately. A browser timer reports elapsed work; observation keys protect retries from double counting. Synthetic fixture history can lower audit activity coverage; no evidence is invented to conceal those gaps.

`security.py`, `storage.py`, and `integrity.py` add host restrictions, headers, sign-in throttling, session controls, optional per-workspace artifact encryption, and HMAC verification. A hardened deployment requires external keys, secure cookies, no demo seeding and an HTTPS origin. Dedicated database/storage isolation is delivered by running a separate instance and volume per office; the default multi-office demonstration still uses logical scoping in a shared SQLite database. Extracted text and metadata require encrypted infrastructure storage.
