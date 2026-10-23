# Local Deployment Guide

## Prerequisites

- Docker Engine / Docker Desktop with Compose **or** Python 3.12
- At least 1 GB available RAM for the server and 200 MB for local demonstration files (Docker OCR image requires more)
- A modern desktop browser
- Network access for one-time dependency installation (the running local rules engine does not require Internet)

## Docker

From the project directory:

```bash
docker compose up --build
```

Visit `http://localhost:8000`. The compose port is bound to the local loopback interface to discourage accidental network exposure.

The `lexflow_data` named volume preserves the database and uploads across restarts.

```bash
docker compose down                 # stop; keep the volume
docker compose down --volumes       # erase all demo data irreversibly
```

## Python virtual environment

Run `./start.sh` (Linux/macOS), `.\start.ps1` (PowerShell), or follow the manual instructions in `README.md`. The server listens only on `127.0.0.1:8000`.

Launch scripts use `.venv-demo` and select Python 3.12 to avoid changing an existing development environment. `LEXFLOW_PYTHON` can select its executable and `LEXFLOW_VENV_DIR` can select the environment directory. Dependencies are refreshed when `requirements.txt` or `constraints.txt` changes. If port 8000 is occupied, use `LEXFLOW_PORT=8001 ./start.sh` (PowerShell: `$env:LEXFLOW_PORT='8001'; .\start.ps1`).

On a subsequent start the app preserves its local database under `data/` unless `LEXFLOW_DATA_DIR` points elsewhere.

## Reset demo data

Stop the Python server and remove the `data/lexflow.sqlite3`, `data/uploads/` and `data/exports/` folder, then restart. This permanently deletes all demo changes. Docker reset instructions are above.

## Password reset delivery

The local demonstration defaults to `LEXFLOW_RESET_DELIVERY=demo` while `LEXFLOW_SEED_DEMO=1`. It displays a reset link in the browser only for the four seeded accounts; it does not send email. This mode is rejected when demo seeding is disabled. `LEXFLOW_RESET_DELIVERY=disabled` disables new reset requests. Existing issued links remain valid until consumed, expired, superseded, or invalidated by a password change.

For real email delivery, set these environment variables before starting the server:

```bash
export LEXFLOW_RESET_DELIVERY=smtp
export LEXFLOW_PUBLIC_URL=https://lexflow.example.com
export LEXFLOW_SMTP_HOST=smtp.example.com
export LEXFLOW_SMTP_PORT=587
export LEXFLOW_SMTP_SECURITY=starttls
export LEXFLOW_SMTP_FROM='LexFlow <noreply@example.com>'
export LEXFLOW_SMTP_USERNAME=your-smtp-username
export LEXFLOW_SMTP_PASSWORD=your-smtp-password
```

Use `LEXFLOW_SMTP_SECURITY=tls` and port `465` for implicit TLS. Both modes verify TLS certificates; unencrypted delivery is unsupported. `LEXFLOW_PUBLIC_URL` must be an HTTPS origin without a path, query or fragment. Links use that configured origin; the incoming Host header cannot change it. Keep credentials outside source control. `.env.example` documents the variables; the launch scripts also load a local `.env` file; quote JSON and values containing spaces.

SMTP delivery runs in a background task. Known and unknown email addresses receive the same response. A failed send invalidates that link and writes a generic server error without exposing the recipient, token or SMTP credentials. Background delivery is not a durable queue: request a new link if the server stops during delivery. Recovery defaults to disabled when `LEXFLOW_SEED_DEMO=0` and no delivery mode is configured. No actual SMTP service is supplied with the local demo.

Rate limit counters persist in SQLite. Configure trusted proxy addresses correctly if adding a reverse proxy, since client IP limits use the server's reported peer address. Changing/resetting a password invalidates outstanding recovery links; a reset revokes all of the affected account's sessions. Use only synthetic demo accounts in this prototype.

## OCR

Image OCR is local and optional. On Ubuntu/Debian:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng
```

The Python dependencies already include `pytesseract` and `pypdfium2`. Docker includes German and English Tesseract by default. Test with `tesseract --list-langs`.

## External AI enhancement (optional and NOT recommended for real confidential data)

Configure environment variables:

```bash
LEXFLOW_ALLOW_EXTERNAL_AI=1
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Do not put secrets into the source code or a version-controlled `.env`. Only when the operator checks *Use external AI enhancement* on a given intake does the application send the source document text to the configured provider. The external AI operation is disabled by default.

## Hardened dedicated deployment

`deploy/compose.hardened.yml` prepares an HTTPS Caddy proxy and a separate application/data volume for one office. The application has a read-only root filesystem, dropped capabilities, no-new-privileges, a temporary directory, resource limits and no published application port. Only the proxy's fixed network address is trusted for forwarded headers. Repeat the stack with separate keys, volumes and an appropriate network configuration for each customer. Region selection and private-network infrastructure remain operator responsibilities.

Create an untracked `.env.hardened` in the project root, with a DNS name that points to the deployment host:

```dotenv
LEXFLOW_DOMAIN=lexflow.example.com
LEXFLOW_AUDIT_KEY=replace-with-at-least-32-random-characters
LEXFLOW_STORAGE_KEYS='{"office-1":["replace-with-a-Fernet-key"]}'
LEXFLOW_RESET_DELIVERY=disabled
```

Generate a signing key with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Generate a file-encryption key with `.venv-demo/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Store these values in a protected secret store and inject them at deployment. Do not commit actual keys. Quoting JSON/spaces in env files is required; the Linux launcher treats its local `.env` as a trusted shell configuration.

Build and provision the empty office before starting the web application:

```bash
docker compose --env-file .env.hardened -f deploy/compose.hardened.yml build
docker compose --env-file .env.hardened -f deploy/compose.hardened.yml run --rm --no-deps lexflow python -m lexflow.manage create-workspace --tenant-id office-1 --name "Example Office" --email admin@example.com
docker compose --env-file .env.hardened -f deploy/compose.hardened.yml up -d
```

Provisioning prompts for a new 12–128 character password and refuses to overwrite an existing workspace. No demo accounts are created. A hardened startup requires exactly one provisioned workspace and rejects retained seeded accounts, demo seeding, insecure cookies, missing explicit hosts, missing HTTPS origin, absent signing/encryption keys, or invalid audit integrity. API documentation endpoints are disabled. HTTP application access is rejected except for the internal health check. The default demonstration login data is hidden when demo seeding is off.

Caddy handles certificate issuance for the configured DNS name; port 80/443 access and working DNS are prerequisites. The configuration follows the official [Caddy reverse-proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) and [request body limit](https://caddyserver.com/docs/caddyfile/directives/request_body) documentation. The supplied image uses [Caddy 2.11.7](https://github.com/caddyserver/caddy/releases/tag/v2.11.7). Docker/ACME execution was not available in this development environment; validate the full stack, image digest, DNS, certificate renewal, network range and restore procedure in your deployment environment before use.

This profile adds controls; it does not implement SSO/MFA, a managed cloud service, regulatory certification, or database-at-rest encryption. Use a separately encrypted data volume and backup destination, least-privilege infrastructure access, and an independently reviewed operating policy.

## File encryption and key rotation

`LEXFLOW_STORAGE_KEYS` is a JSON object mapping each workspace ID to one key or an ordered list of Fernet keys. New original files and exports are encrypted with the **first** key; all listed keys can decrypt existing artifacts. Downloads authenticate the envelope and workspace ID before returning original bytes. The implementation uses the official [Fernet/MultiFernet](https://cryptography.io/en/latest/fernet/) library.

Setting keys does not retroactively encrypt older files. The hardened profile refuses to serve plaintext legacy artifacts; encrypt them with the rotation command before hardened access. To encrypt existing artifacts or rotate to a new key, back up first, keep the old key after the new key in the list, then run:

```bash
.venv-demo/bin/python -m lexflow.manage rotate-artifacts --tenant-id office-1
```

Rotation replaces each file atomically. An interrupted run can leave a mix of old/new key versions, so keep both keys available until rotation and a restore test succeed. SQLite rows, extracted text, candidates, local receiver records and audit details still require encrypted-volume protection. File encryption is not whole-database encryption. External key loss makes encrypted artifacts unrecoverable.

## Audit checkpoints, snapshots and recovery

Audit events are protected with per-workspace HMAC chains. Existing history is sealed once during the additive migration; this cannot establish the integrity of history before migration. The local demo generates a mode-0600 signing key in `data/.audit-key`. A hardened deployment requires a separately protected `LEXFLOW_AUDIT_KEY`. Changing that key invalidates verification of existing chains.

Use the Security page to inspect verification and download a checkpoint, or run:

```bash
.venv-demo/bin/python -m lexflow.manage verify-audit --tenant-id office-1
.venv-demo/bin/python -m lexflow.manage backup /secure-backups/lexflow-snapshot-2026-10-22
```

The snapshot uses SQLite's online backup API while holding an application write lock and copies document/export files consistently. It refuses an existing destination or a destination inside active data. Local fallback signing keys are copied for demo recovery; external encryption and signing keys are **not** included. Put backups and checkpoints in separately protected storage. A chain detects changed/interior missing events; a trusted external checkpoint is required to detect coordinated truncation of both history and its local head.

For a restore drill, stop the target instance, preserve its current volume, copy the snapshot's database and upload/export directories into an empty replacement data directory/volume, restore the correct external keys, and run `verify-audit`. Start an isolated instance against that directory and verify an authenticated document download before switching traffic. Never overwrite a running instance's SQLite database. Snapshot absolute artifact paths must match the restored data path: use the same `/data` container mount or preserve the original `LEXFLOW_DATA_DIR` path. Backup/restore under a different path needs explicit path relocation before serving files.

## Folder intake agent and HTTPS destination

For a controlled local demonstration:

```bash
.venv-demo/bin/python agents/folder_agent.py /path/to/inbox --url http://127.0.0.1:8001 --email admin@keller.demo --matter YOUR_MATTER_ID
```

The agent prompts for a password, authenticates using session/CSRF controls, sends one file per request, and keeps original files. `LEXFLOW_AGENT_PASSWORD` supports supervised automation without putting a password in arguments. Add `--watch` to scan every five seconds. The agent reads the top-level folder, skips symlinks/unsupported files, checks size/mtime around reads and uses stable content keys. Prefer writing to a temporary name and atomically renaming complete files into the inbox; stable metadata alone cannot prove a scanner finished writing. Repeated content with the same file name and matter replays its intake receipt. A changed file becomes new evidence and invalidates prior reviews normally. Only loopback HTTP or verified HTTPS origins are permitted. Session expiry causes reauthentication and retry with the same key.

To enable a supported generic destination, set `LEXFLOW_WEBHOOK_TARGETS` to a JSON workspace map:

```dotenv
LEXFLOW_WEBHOOK_TARGETS='{"office-1":{"url":"https://receiver.example.com/import","secret":"replace-with-32-or-more-random-characters"}}'
```

The operator must authorize that destination for its workspace. See the request signature, acknowledgment and idempotency contract in `docs/API.md`. The local demonstration receiver works without this setting. No vendor-specific integration or Outlook/Word add-in is implied.
