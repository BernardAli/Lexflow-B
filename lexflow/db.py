"""SQLite persistence with transaction-per-request helpers and explicit workspace IDs."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .settings import database_path


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def db(*, write=False):
    connection = sqlite3.connect(database_path(), timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 20000")
    try:
        if write:
            connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
    email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, role TEXT NOT NULL,
    password_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
    csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS password_resets (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
    expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS password_reset_limits (
    scope_hash TEXT NOT NULL, window_start INTEGER NOT NULL, attempts INTEGER NOT NULL,
    PRIMARY KEY(scope_hash, window_start)
);
CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);
CREATE TABLE IF NOT EXISTS matters (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
    reference TEXT NOT NULL, title TEXT NOT NULL, matter_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    approved_by TEXT, approved_at TEXT,
    UNIQUE(tenant_id, reference)
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
    matter_id TEXT NOT NULL REFERENCES matters(id), name TEXT NOT NULL,
    media_type TEXT NOT NULL, byte_size INTEGER NOT NULL, sha256 TEXT NOT NULL,
    raw_text TEXT NOT NULL, file_path TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS matter_case_data (
    matter_id TEXT PRIMARY KEY REFERENCES matters(id),
    tenant_id TEXT NOT NULL REFERENCES tenants(id), revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL, reviewed_by TEXT REFERENCES users(id), reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
    matter_id TEXT NOT NULL REFERENCES matters(id),
    document_id TEXT NOT NULL REFERENCES documents(id), field_key TEXT NOT NULL,
    value TEXT NOT NULL, confidence REAL NOT NULL, evidence TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'rules', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS field_reviews (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
    matter_id TEXT NOT NULL REFERENCES matters(id), field_key TEXT NOT NULL,
    value TEXT NOT NULL, candidate_id TEXT, reviewer_id TEXT NOT NULL REFERENCES users(id),
    note TEXT, reviewed_at TEXT NOT NULL,
    UNIQUE(matter_id,field_key)
);
CREATE TABLE IF NOT EXISTS exports (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
    matter_id TEXT NOT NULL REFERENCES matters(id), file_path TEXT NOT NULL,
    filename TEXT NOT NULL, format TEXT NOT NULL, connector TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
    matter_id TEXT, actor_id TEXT, action TEXT NOT NULL,
    details_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connector_mappings (
    tenant_id TEXT NOT NULL REFERENCES tenants(id), field_key TEXT NOT NULL,
    target_key TEXT NOT NULL, PRIMARY KEY(tenant_id,field_key)
);
CREATE TABLE IF NOT EXISTS document_processing (
    document_id TEXT PRIMARY KEY REFERENCES documents(id), warnings_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invalidated_exports (
    export_id TEXT PRIMARY KEY REFERENCES exports(id), invalidated_at TEXT NOT NULL,
    reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_rules (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), matter_type TEXT NOT NULL,
    field_key TEXT NOT NULL, label TEXT NOT NULL, enabled INTEGER NOT NULL, version INTEGER NOT NULL,
    created_by TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(tenant_id,matter_type,field_key,label)
);
CREATE TABLE IF NOT EXISTS workflow_versions (
    id TEXT PRIMARY KEY, rule_id TEXT NOT NULL REFERENCES workflow_rules(id), version INTEGER NOT NULL,
    configuration_json TEXT NOT NULL, actor_id TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS integration_transfers (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), matter_id TEXT NOT NULL REFERENCES matters(id),
    connector TEXT NOT NULL, idempotency_key TEXT NOT NULL, payload_hash TEXT NOT NULL,
    status TEXT NOT NULL, receipt_json TEXT NOT NULL, actor_id TEXT NOT NULL, created_at TEXT NOT NULL,
    UNIQUE(tenant_id,idempotency_key)
);
CREATE TABLE IF NOT EXISTS receiver_records (
    transfer_id TEXT PRIMARY KEY REFERENCES integration_transfers(id), tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL, payload_json TEXT NOT NULL, received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intake_receipts (
    tenant_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, payload_hash TEXT NOT NULL,
    result_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(tenant_id,idempotency_key)
);
CREATE TABLE IF NOT EXISTS pilot_baselines (
    tenant_id TEXT NOT NULL, matter_type TEXT NOT NULL, minutes REAL NOT NULL, sample_size INTEGER NOT NULL,
    updated_at TEXT NOT NULL, PRIMARY KEY(tenant_id,matter_type)
);
CREATE TABLE IF NOT EXISTS pilot_observations (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, matter_id TEXT NOT NULL REFERENCES matters(id),
    seconds INTEGER NOT NULL, source TEXT NOT NULL, actor_id TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pilot_observation_keys (
    tenant_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, payload_hash TEXT NOT NULL,
    PRIMARY KEY(tenant_id,idempotency_key)
);
CREATE TABLE IF NOT EXISTS session_activity (
    token_hash TEXT PRIMARY KEY REFERENCES sessions(token_hash) ON DELETE CASCADE, last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_limits (
    scope_hash TEXT NOT NULL, window_start INTEGER NOT NULL, attempts INTEGER NOT NULL,
    PRIMARY KEY(scope_hash,window_start)
);
CREATE TABLE IF NOT EXISTS mfa_credentials (
    user_id TEXT PRIMARY KEY REFERENCES users(id), secret_ciphertext TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0, setup_expires INTEGER NOT NULL,
    last_step INTEGER NOT NULL DEFAULT -1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
    user_id TEXT NOT NULL REFERENCES users(id), code_hash TEXT NOT NULL,
    PRIMARY KEY(user_id,code_hash)
);
CREATE TABLE IF NOT EXISTS mfa_challenges (
    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
    expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS session_mfa (
    token_hash TEXT PRIMARY KEY REFERENCES sessions(token_hash) ON DELETE CASCADE,
    verified_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS integration_jobs (
    transfer_id TEXT PRIMARY KEY REFERENCES integration_transfers(id), payload_json TEXT NOT NULL,
    target_hash TEXT NOT NULL, attempt_count INTEGER NOT NULL DEFAULT 0,
    lease_until INTEGER NOT NULL DEFAULT 0, lease_token TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_integrity (
    audit_id TEXT PRIMARY KEY REFERENCES audit(id), tenant_id TEXT NOT NULL,
    position INTEGER NOT NULL, previous_hash TEXT NOT NULL, signature TEXT NOT NULL,
    UNIQUE(tenant_id,position)
);
CREATE TABLE IF NOT EXISTS audit_heads (
    tenant_id TEXT PRIMARY KEY, position INTEGER NOT NULL, signature TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY);
CREATE INDEX IF NOT EXISTS idx_transfers_tenant ON integration_transfers(tenant_id,matter_id);
CREATE INDEX IF NOT EXISTS idx_matters_tenant ON matters(tenant_id,status,updated_at);
CREATE INDEX IF NOT EXISTS idx_docs_matter ON documents(tenant_id,matter_id);
CREATE INDEX IF NOT EXISTS idx_candidates_matter ON candidates(tenant_id,matter_id,field_key);
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit(tenant_id,created_at);
CREATE INDEX IF NOT EXISTS idx_exports_tenant ON exports(tenant_id,matter_id);
"""


def initialize():
    with db() as conn:
        conn.executescript(SCHEMA)
    from .integrity import migrate_integrity
    migrate_integrity()


def record_audit(conn, tenant_id: str, matter_id: str | None, actor_id: str | None, action: str, details: dict):
    import json
    import uuid
    audit_id = uuid.uuid4().hex
    conn.execute("INSERT INTO audit VALUES(?,?,?,?,?,?,?)",
                 (audit_id, tenant_id, matter_id, actor_id, action,
                  json.dumps(details, ensure_ascii=False, sort_keys=True), utcnow()))
    from .integrity import seal_event
    seal_event(conn, audit_id)
    return audit_id
