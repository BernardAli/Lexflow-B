# LexFlow AI — Working Product Prototype

**Version:** 0.11.0-prototype · **Prepared for:** Allgift Technologies Ltd<br/>
**Focus:** German notaries and legal practices · **Date:** October 2026

LexFlow is a **runnable, interactive local web application**, based on the supplied "LexFlow AI — Secure AI Workflow Automation" client concept deck. It demonstrates a real end-to-end workflow from document intake to reviewed, approved, downloadable structured data. It is **not just a clickable design**; it includes a database, authenticated API, document parsers, extraction logic, reviewer actions, audit records, and two separate demo workspaces.

## Documentation

| Document | Use it for |
|---|---|
| [Demonstration guide (12-page PDF)](docs/LexFlow_AI_Demonstration_Guide.pdf) | Presenter steps, sample values, screenshots, NotaryDesk Demo and MFA |
| [Presentation video (1080p MP4)](docs/LexFlow_AI_Presentation.mp4) | 4:04 narrated overview, visible English captions and 12 chapters |
| [Video player and transcript](docs/LexFlow_AI_Presentation.html) | Watch with chapter navigation, read the narration and download captions |
| [Deployment and recovery](docs/DEPLOYMENT.md) | Configuration, MFA policy, provisioning, backups, restore and transfer recovery |
| [API reference](docs/API.md) | Authentication, roles, requests, delivery signatures and receipt contracts |
| [Architecture](docs/ARCHITECTURE.md) | Modules, stores, review state and delivery flow |
| [Verification checklist](docs/TEST_PLAN.md) | Release evidence, automated commands and manual scenarios |
| [Security and limitations](docs/SECURITY_AND_LIMITATIONS.md) | Implemented controls and remaining deployment boundaries |
| [Product roadmap](docs/PRODUCT_ROADMAP.md) | Delivered v0.11 features and remaining customer-pilot milestones |
| [Changelog](CHANGELOG.md) | Version history |

The presentation video is adapted from the current guide, with local synthetic English narration and the guide's synthetic screenshots. Download the MP4 or open the HTML player beside it; the full narration transcript is available in the player. [Video build instructions](docs/TEST_PLAN.md#rebuilding-the-presentation-video) describe how to update the script, slides and captions.

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

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Workspace admin | `admin@keller.demo` | `LexFlowDemo2026!` |
| Reviewer | `reviewer@keller.demo` | `LexFlowDemo2026!` |
| Analyst (intake and read access) | `assistant@keller.demo` | `LexFlowDemo2026!` |
| Second independent workspace | `admin@weber.demo` | `LexFlowDemo2026!` |

**The login screen is prefilled with demo credentials.** These are shared development-only credentials and must never be used to secure real client documents.

## Password reset

Click **Forgot password?** on the sign-in screen, enter a demo account email, then use **Create a new password** in the local demonstration panel. No email service is needed for this demo. Choose and confirm a password of 12–128 characters, then sign in with it. Changing a demo password persists across restarts; the sample password shown on the sign-in screen does not change.

Reset links expire after 30 minutes, work once, and are replaced by newer requests. Resetting a password closes all sessions for that account. Only token hashes are stored, and reset requests and completions are recorded in the workspace audit trail. Both recovery endpoints have rate limits.

If the account has MFA enabled, password recovery preserves it: the next sign-in still needs an authenticator code or unused recovery code. Set up or manage the factor in **Settings → My account**. The hardened deployment requires enrollment before case access.

On-screen links are limited to the four seeded synthetic accounts. With demo seeding disabled, recovery defaults to disabled until SMTP is configured. Optional TLS-protected email delivery is documented in [the deployment guide](docs/DEPLOYMENT.md#password-reset-delivery).

## Four additional workspaces

- **Workflow studio:** test a literal document label, save a workspace-specific versioned rule and use it on future intake. Reviewers can preview; administrators save and pause rules. Select source text and choose **Teach a field** to start from a document. Example text is never stored in rule configuration.
- **Integrations:** send approved data to **NotaryDesk Demo**, a fictional case-management workspace with a separate encrypted case store, verified TLS, signed receipts and preparation stages. The simpler local receiver is also available. An optional signed HTTPS webhook supports an explicitly configured destination. A working folder intake agent is included in `agents/folder_agent.py`.
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
6. When all required fields are confirmed, click **Approve matter**.
7. Click **Export approved data**, choose JSON or CSV, inspect the mapped payload, and generate a downloadable file.
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

## Implemented features

| Capability | Working in this release? | How |
|---|---|---|
| Multi-workspace isolation | **Yes** | Every matter, document, candidate, audit event and export is scoped to an authenticated tenant |
| Role-based access | **Yes** | Admin, reviewer and analyst; reviewer/admin required to confirm, approve and export |
| Sessions and authenticator MFA | **Yes** | Argon2 passwords, throttling, CSRF, 12-hour absolute / 30-minute idle expiry; optional demo MFA and mandatory hardened enrollment |
| Dashboard and case management | **Yes** | Case lists, search/filter, statuses, review queue, pipeline counters |
| PDF, Word, text and email intake | **Yes** | PDF, DOCX, TXT, EML with HTML bodies and supported attachments; atomic batches of up to 6 files |
| Scan and image intake | **Yes, optional OCR** | PNG/JPG and multipage TIFF; OCR checked per PDF page, with explicit limits and warnings |
| Matter classification | **Limited** | Matter type selected by user; local classification flags a likely mismatch during intake |
| Field extraction | **Yes, baseline** | Transparent local pattern extraction for 4 matter types, optional external LLM enhancement |
| Cross-document conflict detection | **Yes** | Distinct normalized field values are flagged as conflicts |
| Evidence and provenance | **Yes** | Candidate value, confidence heuristic, source document, extraction method, text snippet |
| Human review and correction | **Yes** | Select candidate or enter manual value with an optional review note |
| Approval gate | **Yes** | Requires confirmed, valid mandatory fields and resolution of every conflict, including optional fields |
| Connector mappings | **Yes** | Admin-configurable, unique destination names; changed mappings require renewed approval |
| Approved JSON / CSV export | **Yes** | Generated downloadable files with source matter and destination mapping |
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
├── static/                  # LexFlow UI and separate NotaryDesk browser entry point
├── agents/                  # Authenticated folder intake client
├── evaluations/             # Synthetic ground truth and recorded benchmark report
├── samples/                 # 8 synthetic text / email / PDF / Word examples
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

The v0.11 release passed **111 backend tests and 21 UI tests**, plus **141 Chromium page/panel checks** across five widths. Coverage includes MFA, recovery codes, signed local TLS delivery, crash recovery, tenant/role boundaries, portable restore, snapshot tampering and the core intake/review/export flow. See the [verification checklist](docs/TEST_PLAN.md) for evidence and limits. OCR tests substitute the OCR engine; recognition quality requires local Tesseract. `constraints.txt` pins the tested Python dependencies; the browser application has no runtime JavaScript dependencies.

Reopening a matter, adding documents, or changing destination mappings marks earlier exports as superseded and blocks new downloads. Copies downloaded earlier remain outside the application’s control. Existing databases are upgraded with additive tables; historical corrections lost before this version cannot be reconstructed.

## Next steps for production

Read the [roadmap](docs/PRODUCT_ROADMAP.md) and [security boundaries](docs/SECURITY_AND_LIMITATIONS.md). Remaining priorities are the exact customer workflow and supported vendor API, managed keys and tenant infrastructure, SSO and factor-recovery operations, representative OCR/extraction evaluation, target-environment restore drills and independent review.

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
