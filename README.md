# LexFlow AI — Working Product Prototype

**Version:** 0.12.0-prototype · **Prepared for:** Allgift Technologies Ltd<br/>
**Focus:** German notaries and legal practices · **Date:** October 2026

LexFlow is a **runnable, interactive local web application**, based on the supplied "LexFlow AI — Secure AI Workflow Automation" client concept deck. It demonstrates a real end-to-end workflow from document intake to reviewed, approved, downloadable structured data. It is **not just a clickable design**; it includes a database, authenticated API, document parsers, extraction logic, reviewer actions, audit records, and two separate demo workspaces.

## Documentation

The [public German product website](https://lexflow-ai.jaunty-ibis-0043.chatgpt.site) has a concise homepage and separate pages for the product, workflow, interactive demo, trust, ProNotar integration, downloads, pilot preparation and FAQs, alongside project/privacy information. Its separate static source, page map and preview instructions are in [public-site/README.md](public-site/README.md). The website is a product presentation; it does not expose the application or its data. Pilot briefs download locally and are not sent to a contact address.

| Document | Use it for |
|---|---|
| [ProNotar32 extension foundation](docs/PRONOTAR_EXTENSION.md) | Structured case records, approval, versioned handoff and the future vendor adapter |
| [EU safety, security and data-protection blueprint (24-page PDF)](docs/LexFlow_EU_Safety_Security_Blueprint.pdf) | Current controls, regulatory applicability, implementation gaps, evidence requirements and release gates; a roadmap, not a compliance certificate |
| [Demonstration guide (14-page PDF)](docs/LexFlow_AI_Demonstration_Guide.pdf) | v0.12 presenter steps, structured case preparation, exports, NotaryDesk Demo and MFA |
| [Presentation video (1080p MP4, v0.11)](docs/LexFlow_AI_Presentation.mp4) | Historical 4:04 narrated overview with English captions and 12 chapters |
| [Video player and transcript](docs/LexFlow_AI_Presentation.html) | Watch with chapter navigation, read the narration and download captions |
| [Deployment and recovery](docs/DEPLOYMENT.md) | Configuration, MFA policy, provisioning, backups, restore and transfer recovery |
| [API reference](docs/API.md) | Authentication, roles, requests, delivery signatures and receipt contracts |
| [Architecture](docs/ARCHITECTURE.md) | Modules, stores, review state and delivery flow |
| [Verification checklist](docs/TEST_PLAN.md) | Release evidence, automated commands and manual scenarios |
| [Security and limitations](docs/SECURITY_AND_LIMITATIONS.md) | Implemented controls and remaining deployment boundaries |
| [Product roadmap](docs/PRODUCT_ROADMAP.md) | Delivered v0.12 features and remaining ProNotar/customer-pilot milestones |
| [Changelog](CHANGELOG.md) | Version history |

The presentation video records the v0.11 workflow and uses synthetic English narration and screenshots. It does not cover v0.12 Case details or structured case bundles; use the current PDF and extension guide for those features. Download the MP4 or open the HTML player beside it for the full transcript. [Video build instructions](docs/TEST_PLAN.md#rebuilding-the-presentation-video) describe how to update the script, slides and captions.

> **IMPORTANT — NOT A PRODUCTION NOTARIAL SYSTEM.** The default accounts use publicly documented test passwords. Upload only synthetic or fully sanitized documents. Actual German notarial deployments need specialist legal/privacy review, security engineering, integration agreements and additional controls (see `docs/SECURITY_AND_LIMITATIONS.md`). No BNotK/XNP or vendor system is preconnected. File exports remain local; an explicitly configured HTTPS webhook can transmit approved data to an authorized destination.

## Start in under 5 minutes

### Option A — Docker (recommended)

Install Docker Desktop or Docker Engine with Compose, unzip the archive, open a terminal inside the `lexflow_ai_prototype` directory and run:

```bash
docker compose up --build
```

Open **http://localhost:8000**.

To stop it, press `Ctrl+C` or run `docker compose down`. Your demo database and files remain in the Docker named volume until you explicitly remove that volume.

### Option B — Linux / macOS (Python 3.12)

```bash
cd lexflow_ai_prototype
chmod +x start.sh
./start.sh
```

This creates a separate `.venv-demo` Python 3.12 environment, installs the tested dependencies on first use, and starts the server at **http://127.0.0.1:8000**.

### Option C — Windows PowerShell (Python 3.12)

```powershell
cd lexflow_ai_prototype
.\start.ps1
```

If PowerShell blocks local scripts, either allow script execution for the current PowerShell process (`Set-ExecutionPolicy -Scope Process Bypass`) or use the manual commands:

```powershell
py -3.12 -m venv .venv-demo
.\.venv-demo\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-demo\Scripts\python.exe -m uvicorn lexflow.main:app --host 127.0.0.1 --port 8000
```

### Option D — Manual Python setup

```bash
python3.12 -m venv .venv-demo
source .venv-demo/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn lexflow.main:app --host 127.0.0.1 --port 8000
```

API reference is available at **http://127.0.0.1:8000/docs**.

To run on port **3000** with the existing Python 3.12 environment:

```bash
.venv-demo/bin/python -m uvicorn lexflow.main:app --host 127.0.0.1 --port 3000
```

Open **http://127.0.0.1:3000**. LexFlow uses FastAPI/Uvicorn; `python manage.py runserver` is not its startup command. After updating the project, stop the old server with `Ctrl+C` and restart it to load the new routes and additive database table. See [upgrading to v0.12](docs/DEPLOYMENT.md#upgrading-to-v012) for backup and rollback guidance.

### Structured case preparation (v0.12)

Open a matter's **Case details** tab to add multiple people/companies, representative links, properties and execution tasks. Case setup includes a category, office naming code, suggested designation, master-case link and template reference. Link records to source documents or verification notes, confirm extracted fields, then have a reviewer **Confirm case details** before approving the matter.

Approved matters with saved case details default to a **Structured case bundle (JSON)** export containing the complete records and review/source metadata. Flat JSON/CSV profiles remain available and omit these additional records. Existing matters require no data conversion; the additional table is created at startup.

The ProNotar32 target tracks the latest vendor-supported release. Its exact build and import format remain unverified, so live connection and vendor XML export stay disabled. The new adapter boundary can implement that contract once supplied. See the [extension guide](docs/PRONOTAR_EXTENSION.md) for capabilities, API endpoints, limitations and validation steps. The current PDF includes this workflow; the existing video remains a v0.11 walkthrough.

These records are entered and reviewed by staff. The six case categories describe the handoff; automatic extraction still uses the four existing matter types. The software does not automatically split a buyer-name field into people, populate Word templates, or submit execution tasks to another system.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Workspace admin | `admin@keller.demo` | `LexFlowDemo2026!` |
| Reviewer | `reviewer@keller.demo` | `LexFlowDemo2026!` |
| Analyst (intake and case preparation) | `assistant@keller.demo` | `LexFlowDemo2026!` |
| Second independent workspace | `admin@weber.demo` | `LexFlowDemo2026!` |

**The login screen is prefilled with demo credentials.** These are shared development-only credentials and must never be used to secure real client documents.

## Password reset

Click **Forgot password?** on the sign-in screen, enter a demo account email, then use **Create a new password** in the local demonstration panel. No email service is needed for this demo. Choose and confirm a password of 12–128 characters, then sign in with it. Changing a demo password persists across restarts; the sample password shown on the sign-in screen does not change.

Reset links expire after 30 minutes, work once, and are replaced by newer requests. Resetting a password closes all sessions for that account. Only token hashes are stored, and reset requests and completions are recorded in the workspace audit trail. Both recovery endpoints have rate limits.

If the account has MFA enabled, password recovery preserves it: the next sign-in still needs an authenticator code or unused recovery code. Set up or manage the factor in **Settings → My account**. The hardened deployment requires enrollment before case access.

On-screen links are limited to the four seeded synthetic accounts. With demo seeding disabled, recovery defaults to disabled until SMTP is configured. Optional TLS-protected email delivery is documented in [the deployment guide](docs/DEPLOYMENT.md#password-reset-delivery).

## Four additional workspaces

- **Workflow studio:** test a literal document label, save a workspace-specific versioned rule and use it on future intake. Reviewers can preview; administrators save and pause rules. Select source text and choose **Teach a field** to start from a document. Example text is never stored in rule configuration.
- **Integrations:** send approved extraction fields to **NotaryDesk Demo**, a fictional case-management workspace with a separate encrypted case store, verified TLS, signed receipts and preparation stages. The local receiver and optional configured HTTPS webhook also use flat-field payloads. Structured participants, properties and tasks are included in the separate **Structured case bundle** file export. A working folder intake agent is included in `agents/folder_agent.py`.
- **Security:** inspect session/cookie/encryption controls, revoke other sessions, verify HMAC audit chains and export checkpoints. A dedicated HTTPS deployment profile, operator provisioning, consistent snapshots and artifact-key rotation are included.
- **Pilot measurement:** record an observed baseline, record work sessions or use a matter timer, inspect extraction/correction/low-confidence/audit rates, and export CSV evidence. Acceptance rates are separate for the local receiver, fictional NotaryDesk over HTTPS and a configured HTTPS destination. No measured time savings are invented.

The default local demo still runs without external accounts or services. See [deployment and operator commands](docs/DEPLOYMENT.md), [API contracts](docs/API.md), and [remaining security boundaries](docs/SECURITY_AND_LIMITATIONS.md). Native Outlook/Word and real notary-vendor integrations remain outside the supplied implementation.

Related sections use tabs in Overview, matters, intake, exports, integrations, pilot measurement, security and settings. Use the arrow keys, Home and End to move between tabs. Switching tabs preserves form drafts, selected files and transfer previews. Selection is remembered during page updates and cleared on sign-out. In Pilot measurement, use **Record measurements** to enter baselines and work sessions; in Settings, use **My account** to change your password or set up an authenticator app.

## Guided demonstration in about 10–15 minutes

1. Sign in as `admin@keller.demo`.
2. Click **Start guided demo** on the dashboard. Each click creates a fresh synthetic matter, so the demonstration is repeatable.
3. See two synthetic source files: a buyer questionnaire and land-register extract.
4. Observe the **land register conflict**: one source says **München Blatt 812**, the other says **München Blatt 872**.
5. Click **Review field** under *Land register*, inspect both source suggestions, select a value, and click **Confirm value**. Do the same for the other *required* fields.
6. When all required fields are confirmed and every conflict is resolved, click **Approve matter**. If you have saved records in **Case details**, use **Confirm case details** there first.
7. Click **Export approved data**, select **Flat reviewed fields**, choose JSON or CSV, inspect the mapped payload, and generate a downloadable file.
8. Open **Integrations → Send approved data**, select that matter and **NotaryDesk Demo (HTTPS)**, run **Dry run**, then **Send approved data**.
9. Click **Open demo notary**, select the received case, open its **Delivery evidence** tab, then use **Case details** to change the stage to **In preparation** and save it.
10. Check **Audit trail** and **Pilot measurement** to inspect recorded actions and measured outcomes.

### Test creation from scratch

1. Click **New matter** and choose *Property purchase*.
2. Navigate to **Document intake**, select your new matter, and upload `samples/07_synthetic_property_purchase.pdf` or `samples/08_synthetic_property_purchase.docx`.
3. Alternatively, open *Paste document text* and click **Insert synthetic example**.
4. Inspect extracted suggestions, confirm each required field and approve the matter.
5. Generate a CSV/JSON export. To test conflicting source documents, upload two source files with different `Grundbuch:` values.

All sample names, financial amounts, addresses and identifiers are **invented** and are intended only for software testing.

### Demonstrate structured case preparation

1. Open an unapproved property-purchase matter with source documents, or reopen an approved matter. Select its **Case details** tab.
2. Add each participant separately. Choose **Person** or **Company**, assign roles and record known attributes. Add representative people before linking them to another participant. Select a source document or enter a verification note for each record.
3. Add each property and its register/cadastral details. Unknown values can stay blank. Record ownership shares as fractions such as `1/2` and area using a decimal point, such as `120.50`.
4. Use **Edit case setup** to choose a case category, office naming code, optional master case and template reference. **Use suggestion** proposes a designation; it does not rename the matter's title/reference. Optionally add pending, initiated or completed execution tasks.
5. Confirm required extracted fields and resolve conflicts under **Review & sources**. A reviewer/admin then returns to **Case details → Confirm case details** and approves the matter. A later record edit, field-review change, new source or reopening requires case review again.
6. Export **Structured case bundle (JSON)** and inspect its participants, properties, tasks, document hashes and review metadata. It is a LexFlow development handoff, not an accepted ProNotar file.

Analysts may prepare records but cannot confirm them, approve or generate exports. A stale save returns a reload message and preserves the browser form for comparison. A saved empty case structure also requires case review. Existing matters with no saved structure keep the original field-review workflow.

The synthetic [structured case example](samples/09_structured_case.json) illustrates the API model; it is not a document-intake upload format. See the [API example](docs/API.md#example--prepare-review-and-export-case-details) for how to submit it.

### Choose the appropriate output

| Output | Included data | Destination behavior |
|---|---|---|
| Flat reviewed fields / `approved_export` | Confirmed extraction fields with configurable destination keys | Local JSON or CSV file |
| Notary software simulator / `notary_demo` | The same flat-field scope | Local JSON or CSV file; no vendor connection |
| Structured case bundle / `case_bundle` | Case metadata, all saved structured records, reviewed fields and source/review metadata | Local JSON file; no original document bytes or verified vendor format |
| Integrations: local receiver, NotaryDesk Demo, configured webhook | Approved flat extraction fields | Delivery and receipts under the existing destination contracts; structured records are omitted |
| ProNotar32 / `pronotar32` | Planned vendor mapping from the structured snapshot | Disabled pending verified version, schema and import tests |

The export dialog defaults to the structured bundle when case details have been saved. Settings' field mappings apply to flat output; they do not define ProNotar XML. See [connector capabilities and extension steps](docs/PRONOTAR_EXTENSION.md).

## Implemented features

| Capability | Working in this release? | How |
|---|---|---|
| Multi-workspace isolation | **Yes** | Every matter, document, candidate, audit event and export is scoped to an authenticated tenant |
| Role-based access | **Yes** | Admin, reviewer and analyst; reviewer/admin required to confirm, approve and export |
| Sessions and authenticator MFA | **Yes** | Argon2 passwords, throttling, CSRF, 12-hour absolute / 30-minute idle expiry; optional demo MFA and mandatory hardened enrollment |
| Dashboard and case management | **Yes** | Case lists, search/filter, statuses, review queue, pipeline counters |
| Structured case records | **Yes** | Multiple people, companies, representatives and properties; source links/verification notes; separate reviewer confirmation |
| Office case setup | **Yes** | Six handoff categories, naming-code suggestions, master-case links and template references; metadata only |
| Execution task records | **Yes, manual** | Pending, initiated and completed status with optional due dates; no reminders or external execution |
| PDF, Word, text and email intake | **Yes** | PDF, DOCX, TXT, EML with HTML bodies and supported attachments; atomic batches of up to 6 files |
| Scan and image intake | **Yes, optional OCR** | PNG/JPG and multipage TIFF; OCR checked per PDF page, with explicit limits and warnings |
| Matter classification | **Limited** | Matter type selected by user; local classification flags a likely mismatch during intake |
| Field extraction | **Yes, baseline** | Transparent local pattern extraction for 4 matter types, optional external LLM enhancement |
| Cross-document conflict detection | **Yes** | Distinct normalized field values are flagged as conflicts |
| Evidence and provenance | **Yes** | Candidate value, confidence heuristic, source document, extraction method, text snippet |
| Human review and correction | **Yes** | Select candidate or enter manual value with an optional review note |
| Approval gate | **Yes** | Requires source documents, valid confirmed mandatory fields, resolution of all conflicts, and reviewed case details when saved |
| Connector mappings | **Yes** | Admin-configurable, unique destination names; changed mappings require renewed approval |
| Approved JSON / CSV export | **Yes** | Generated downloadable files with source matter and destination mapping |
| Complete structured case export | **Yes** | Versioned JSON snapshot with stable record IDs, review/source metadata and content digest; local generation only |
| ProNotar32 adapter foundation | **Yes; import disabled** | Capability registry and file-adapter interface; latest supported release is the target policy, not verified compatibility |
| Notary file-export profile | **Yes** | `notary_demo` generates a local mapped file |
| NotaryDesk Demo destination | **Yes, fictional** | `demo_notary` sends over verified local TLS to a separate encrypted case store, with signed receipts and revision-checked stages |
| Durable transfer intents | **Yes** | Approval-bound previews, destination binding, leases and same-key crash recovery; HTTP I/O releases the SQLite writer lock |
| Backup and portable restore | **Yes** | Authenticated manifest, artifact/audit checks, relocated paths and revoked sessions on restore |
| Evaluation and release checks | **Yes** | Versioned synthetic extraction dataset/report and CI for backend/UI tests, dependency checks and benchmark |
| Audit history | **Yes, demo-grade** | Previous/new corrections, source selections, full notes, review invalidations and mapping changes |
| Third-party notarial integrations | **No** | Requires vendor authorization and a supported real interface |
| Native Outlook/Word add-ins | **No** | The browser-based intake UI works; production add-ins are a roadmap item |
| Enterprise security certification | **No** | Requires a separate design, verification and audit program |

## File structure

```text
lexflow_ai_prototype/
├── lexflow/
│   ├── main.py             # App lifecycle, intake and matter routes
│   ├── matter_service.py   # Shared fields, review gate and export invariants
│   ├── case_models.py      # Versioned participants, properties, tasks and case metadata
│   ├── case_data.py        # Revision-checked preparation, reference checks and review
│   ├── connectors.py       # File adapters, capability registry and structured case bundle
│   ├── db.py               # SQLite schema, transactions and audit
│   ├── auth.py             # Passwords, session auth, CSRF and roles
│   ├── mfa.py              # Authenticator enrollment, challenges and recovery codes
│   ├── password_reset.py   # Reset tokens, demo/SMTP delivery and rate limits
│   ├── extraction.py       # German notarial field schemas / local rules / optional AI
│   ├── documents.py        # PDF, DOCX, EML, TXT, image parsing and OCR
│   ├── exporter.py         # Approved mapping and CSV/JSON generator
│   ├── workflows.py        # Tenant-scoped, versioned label rules
│   ├── integrations.py     # Dry runs, transfers and agent intake adapter
│   ├── delivery.py         # Durable intents, bounded leases and recovery
│   ├── demo_notary.py      # Fictional TLS receiver, case store and proxy
│   ├── pilot.py            # Baselines, observations and defined metrics
│   ├── security.py         # Deployment policy, throttling and security status
│   ├── storage.py          # Workspace artifact encryption and key rings
│   ├── integrity.py        # Audit HMAC chains and checkpoints
│   ├── snapshots.py        # Authenticated snapshots and portable restore
│   ├── manage.py           # Operator commands
│   ├── benchmark.py        # Offline ground-truth evaluation CLI
│   ├── seed.py             # Synthetic multi-tenant demo fixtures
│   └── settings.py         # Environment configuration
├── static/                  # LexFlow UI, case-data.js editor and NotaryDesk entry point
├── agents/                  # Authenticated folder intake client
├── evaluations/             # Synthetic ground truth and recorded benchmark report
├── samples/                 # 8 intake documents + synthetic structured-case JSON example
├── tests/                   # Automated API and workflow tests
├── docs/                    # Guides, PDF, reproducible PDF source and screenshots
├── deploy/                  # Dedicated HTTPS Compose profile and proxy config
├── .github/workflows/       # CI release checks
├── data/                    # Generated DB, files, local demo keys and destination store
├── Dockerfile / docker-compose.yml
├── start.sh / start.ps1
├── .env.example
└── README.md
```

## Configuration

The demo runs with defaults. The hardened profile requires explicit hosts, an HTTPS origin, external audit/storage/MFA keys, disabled demo seeding and secure cookies. See the [deployment configuration reference](docs/DEPLOYMENT.md#configuration-reference).

| Variable | Default | Purpose |
|---|---|---|
| `LEXFLOW_DATA_DIR` | `./data` | Local SQLite database, uploads and exports |
| `LEXFLOW_SEED_DEMO` | `1` | Load sample accounts and matters on first initialization |
| `LEXFLOW_DEMO_NOTARY` | `1` | Start fictional NotaryDesk; also requires demo seeding |
| `LEXFLOW_REQUIRE_MFA` | `0` in demo, `1` in hardened | Require factor enrollment before case access |
| `LEXFLOW_MFA_KEY` | local fallback in demo | Fernet key for authenticator secrets; external key required in hardened |
| `LEXFLOW_SECURITY_PROFILE` | `demo` | Choose demo or hardened deployment policy |
| `LEXFLOW_IDLE_MINUTES` | `30` | Inactivity timeout, from 1 to 720 minutes |
| `LEXFLOW_MAX_UPLOAD_MB` | `12` | Maximum size per uploaded file |
| `LEXFLOW_SECURE_COOKIES` | `0` in demo, `1` in hardened | HTTPS-only session cookies |
| `LEXFLOW_AUDIT_KEY` | local fallback in demo | External audit/manifest signing key required in hardened |
| `LEXFLOW_STORAGE_KEYS` | unset | Workspace Fernet key rings for original files and exports |
| `LEXFLOW_WEBHOOK_TARGETS` | unset | Workspace HTTPS destination URLs and signing secrets |
| `LEXFLOW_RESET_DELIVERY` | `demo` when seeded, otherwise `disabled` | Demo links, TLS SMTP or disabled recovery |
| `LEXFLOW_ALLOW_EXTERNAL_AI` | `0` | Explicitly allow optional third-party AI processing |
| `OPENAI_API_KEY` | unset | Required if external AI processing is enabled |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Configured OpenAI model for optional enrichment |

External AI runs **only** when all three conditions hold: (1) server has `LEXFLOW_ALLOW_EXTERNAL_AI=1`, (2) a valid `OPENAI_API_KEY` exists, and (3) a user opts in for that particular intake. The provider then receives document text; do **not** enable it for confidential client information without a legally reviewed data-processing arrangement and acceptable regional controls. When not configured, all extraction runs locally with deterministic rules, not a large-language model.

`start.sh` and `start.ps1` load a local `.env`. Manual Python/CLI commands use their process environment and do not load that file. Docker Compose forwards only explicitly listed variables; use the documented [demo Compose override](docs/DEPLOYMENT.md#docker) for the newer demo MFA/notary controls, or the supplied hardened stack for mandatory MFA.

## Run quality checks

```bash
python -m pytest -q
python -m compileall -q lexflow agents
python -m pip check

# Optional interface regression checks (Node.js development tools only)
npm ci
npm run test:ui
python -m lexflow.benchmark --output /tmp/extraction-report.json --min-f1 0.95
```

The v0.12 release passed **134 backend tests and 26 UI logic tests**. A Chromium walkthrough completed structured record creation, naming, review, approval and matching preview/download; layouts were checked at 390, 768 and 1440 pixels. Coverage also includes the existing MFA, delivery, isolation and recovery regressions. The earlier 141-view v0.11 browser exercise is historical evidence and was not repeated in full. See the [verification checklist](docs/TEST_PLAN.md) for evidence and limits. OCR tests substitute the OCR engine; recognition quality requires local Tesseract. `constraints.txt` pins the tested Python dependencies; the browser application has no runtime JavaScript dependencies.

Reopening a matter, adding documents, or changing destination mappings marks earlier exports as superseded and blocks new downloads. Copies downloaded earlier remain outside the application’s control. Existing databases are upgraded with additive tables; historical corrections lost before this version cannot be reconstructed.

## Next steps for production

Read the [roadmap](docs/PRODUCT_ROADMAP.md) and [security boundaries](docs/SECURITY_AND_LIMITATIONS.md). The next ProNotar milestone is confirming the latest supported build, licensed modules, accepted import schema/files and create/update/duplicate rules, then validating a mapped import in an authorized test installation. Managed infrastructure, SSO/recovery operations, representative OCR/extraction evaluation and target-environment restore drills also remain pilot work.

**Deliverable status:** Complete, runnable **functional prototype**; not a final legally deployable German notarial SaaS product.

## Release verification and recovery

```bash
.venv-demo/bin/python -m pytest -q
npm ci
npm run test:ui
.venv-demo/bin/python -m lexflow.benchmark --output /tmp/extraction-report.json --min-f1 0.95
.venv-demo/bin/python -m lexflow.manage backup /tmp/lexflow-snapshot
.venv-demo/bin/python -m lexflow.manage verify-backup /tmp/lexflow-snapshot
.venv-demo/bin/python -m lexflow.manage restore /tmp/lexflow-snapshot /tmp/lexflow-restored
```

The versioned synthetic benchmark contains 28 hand-authored text cases covering all four matter types. Recorded precision is **100%**, recall **97.2%**, and F1 **98.6%**; two OCR-damaged labels remain misses. This evaluates text-to-candidate rules, not OCR quality or accuracy on real office documents. The committed dataset and report are in `evaluations/`; `--dataset` accepts independently labelled examples with the same explicit schema. CI runs tests, dependency checks and the benchmark on pushes and pull requests.

Snapshots authenticate their file manifest, database, original-document hashes, encrypted artifacts, audit chains, MFA secrets and demo destination cases. Restore requires a new directory, relocates stored artifact paths and revokes old sessions/reset links. Supply the original external keys when configured; they are excluded from snapshots. See [deployment and recovery](docs/DEPLOYMENT.md).
