# LexFlow AI — Working Product Prototype

**Version:** 0.10.0-prototype · **Prepared for:** Allgift Technologies Ltd  
**Focus:** German notaries and legal practices · **Date:** October 2026

LexFlow is a **runnable, interactive local web application**, based on the supplied "LexFlow AI — Secure AI Workflow Automation" client concept deck. It demonstrates a real end-to-end workflow from document intake to reviewed, approved, downloadable structured data. It is **not just a clickable design**; it includes a database, authenticated API, document parsers, extraction logic, reviewer actions, audit records, and two separate demo workspaces.

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
| Analyst (read-only approval) | `assistant@keller.demo` | `LexFlowDemo2026!` |
| Second independent workspace | `admin@weber.demo` | `LexFlowDemo2026!` |

**The login screen is prefilled with demo credentials.** These are shared development-only credentials and must never be used to secure real client documents.

## Password reset

Click **Forgot password?** on the sign-in screen, enter a demo account email, then use **Create a new password** in the local demonstration panel. No email service is needed for this demo. Choose and confirm a password of 12–128 characters, then sign in with it. Changing a demo password persists across restarts; the sample password shown on the sign-in screen does not change.

Reset links expire after 30 minutes, work once, and are replaced by newer requests. Resetting a password closes all sessions for that account. Only token hashes are stored, and reset requests and completions are recorded in the workspace audit trail. Both recovery endpoints have rate limits.

On-screen links are limited to the four seeded synthetic accounts. With demo seeding disabled, recovery defaults to disabled until SMTP is configured. Optional TLS-protected email delivery is documented in [the deployment guide](docs/DEPLOYMENT.md#password-reset-delivery).

## Four additional workspaces

- **Workflow studio:** test a literal document label, save a workspace-specific versioned rule and use it on future intake. Reviewers can preview; administrators save and pause rules. Select source text and choose **Teach a field** to start from a document. Example text is never stored in rule configuration.
- **Integrations:** run an approval-gated dry run, send to the clearly marked local receiver, inspect its stored record and keep an idempotent receipt. An optional signed HTTPS webhook supports an explicitly configured destination. A working folder intake agent is included in `agents/folder_agent.py`.
- **Security:** inspect session/cookie/encryption controls, revoke other sessions, verify HMAC audit chains and export checkpoints. A dedicated HTTPS deployment profile, operator provisioning, consistent snapshots and artifact-key rotation are included.
- **Pilot measurement:** record an observed baseline, record work sessions or use a matter timer, inspect extraction/correction/low-confidence/audit rates, and export CSV evidence. Each metric explains its denominator; simulated transfer rates remain separate from HTTPS results. No measured time savings are invented.

The default local demo still runs without external accounts or services. See [deployment and operator commands](docs/DEPLOYMENT.md), [API contracts](docs/API.md), and [remaining security boundaries](docs/SECURITY_AND_LIMITATIONS.md). Native Outlook/Word and real notary-vendor integrations remain outside the supplied implementation.

## Guided demonstration in about three minutes

1. Sign in as `admin@keller.demo`.
2. Click **Start guided demo** on the dashboard. Each click creates a fresh synthetic matter, so the demonstration is repeatable.
3. See two synthetic source files: a buyer questionnaire and land-register extract.
4. Observe the **land register conflict**: one source says **München Blatt 812**, the other says **München Blatt 872**.
5. Click **Review field** under *Land register*, inspect both source suggestions, select a value, and click **Confirm value**. Do the same for the other *required* fields.
6. When all required fields are confirmed, click **Approve matter**.
7. Click **Export approved data**, choose JSON or CSV, inspect the mapped payload, and generate a downloadable file.
8. Check **Audit trail** and **Transfers & exports** to see the tracked actions.

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
| Secure demo sessions | **Yes, demo-grade** | Argon2 password hashing, HttpOnly SameSite cookies, CSRF protection, 12-hour sessions |
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
| Notary connector simulator | **Yes, mock only** | Creates export files that mimic a possible mapped handoff — no external write |
| Audit history | **Yes, demo-grade** | Previous/new corrections, source selections, full notes, review invalidations and mapping changes |
| Third-party notarial integrations | **No** | Requires vendor authorization and a supported real interface |
| Native Outlook/Word add-ins | **No** | The browser-based intake UI works; production add-ins are a roadmap item |
| Enterprise security certification | **No** | Requires a separate design, verification and audit program |

## File structure

```text
lexflow_ai_prototype/
├── lexflow/
│   ├── main.py             # API routes, workflows, review gate, exports
│   ├── db.py               # SQLite schema, transactions and audit
│   ├── auth.py             # Passwords, session auth, CSRF and roles
│   ├── extraction.py       # German notarial field schemas / local rules / optional AI
│   ├── documents.py        # PDF, DOCX, EML, TXT, image parsing and OCR
│   ├── exporter.py         # Approved mapping and CSV/JSON generator
│   ├── seed.py             # Synthetic multi-tenant demo fixtures
│   └── settings.py         # Environment configuration
├── static/                  # Fully offline-capable web UI (HTML/CSS/JS)
├── samples/                 # 8 synthetic text / email / PDF / Word examples
├── tests/                   # Automated API and workflow tests
├── docs/                    # Architecture, security, deployment and roadmap
├── data/                    # Local database & uploads (generated on first run)
├── Dockerfile / docker-compose.yml
├── start.sh / start.ps1
├── .env.example
└── README.md
```

## Configuration

All variables are optional unless you enable external AI.

| Variable | Default | Purpose |
|---|---|---|
| `LEXFLOW_DATA_DIR` | `./data` | Local SQLite database, uploads and exports |
| `LEXFLOW_SEED_DEMO` | `1` | Load sample accounts and matters on first initialization |
| `LEXFLOW_MAX_UPLOAD_MB` | `12` | Maximum size per uploaded file |
| `LEXFLOW_SECURE_COOKIES` | `0` | Switch to `1` behind HTTPS only; local HTTP demo uses `0` |
| `LEXFLOW_ALLOW_EXTERNAL_AI` | `0` | Explicitly allow optional third-party AI processing |
| `OPENAI_API_KEY` | unset | Required if external AI processing is enabled |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Configured OpenAI model for optional enrichment |

External AI runs **only** when all three conditions hold: (1) server has `LEXFLOW_ALLOW_EXTERNAL_AI=1`, (2) a valid `OPENAI_API_KEY` exists, and (3) a user opts in for that particular intake. The provider then receives document text; do **not** enable it for confidential client information without a legally reviewed data-processing arrangement and acceptable regional controls. When not configured, all extraction runs locally with deterministic rules, not a large-language model.

If using `.env.example` as a guide, note that the Docker Compose file forwards these variables; `start.sh` and `start.ps1` also load `.env` if present. See `docs/DEPLOYMENT.md`.

## Run quality checks

```bash
python -m pytest -q
python -m compileall -q lexflow

# Optional interface regression checks (Node.js development tools only)
npm ci
npm run test:ui
```

The tests cover login, tenant separation, roles, CSRF, optional conflicts, value validation, complete correction history, batch rollback, email attachments, mixed PDFs, TIFF frames, export invalidation, and the repeatable demo. OCR tests substitute the OCR engine; recognition quality requires local Tesseract. `constraints.txt` pins the tested Python dependencies; the browser application has no runtime JavaScript dependencies.

Reopening a matter, adding documents, or changing destination mappings marks earlier exports as superseded and blocks new downloads. Copies downloaded earlier remain outside the application’s control. Existing databases are upgraded with additive tables; historical corrections lost before this version cannot be reconstructed.

## Next steps for production

Read `docs/PRODUCT_ROADMAP.md` and `docs/SECURITY_AND_LIMITATIONS.md`. Priorities are validating the exact customer workflow and destination software, arranging supported API access, production-grade tenancy and encryption, stronger identity controls, robust OCR/AI accuracy evaluation, compliance review and disaster recovery testing.

**Deliverable status:** Complete, runnable **functional prototype**; not a final legally deployable German notarial SaaS product.
