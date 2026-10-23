"""Per-workspace HMAC audit chains. Export checkpoints to detect tail truncation."""
import hashlib
import hmac
import json
import os
import secrets
from .db import db
from .settings import data_dir


def audit_key():
    configured = os.getenv("LEXFLOW_AUDIT_KEY")
    if configured:
        return configured.encode()
    path = data_dir() / ".audit-key"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_bytes()
    key = secrets.token_bytes(48)
    with os.fdopen(fd, "wb") as output:
        output.write(key)
    return key


def sign(row, position, previous, key=None):
    data = json.dumps({"event": dict(row), "position": position, "previous": previous},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hmac.new(key if key is not None else audit_key(), data, hashlib.sha256).hexdigest()


def seal_event(conn, event_id):
    row = conn.execute("SELECT * FROM audit WHERE id=?", (event_id,)).fetchone()
    head = conn.execute("SELECT * FROM audit_heads WHERE tenant_id=?", (row["tenant_id"],)).fetchone()
    position, previous = (head["position"] + 1, head["signature"]) if head else (1, "0" * 64)
    signature = sign(row, position, previous)
    conn.execute("INSERT INTO audit_integrity VALUES(?,?,?,?,?)", (event_id, row["tenant_id"], position, previous, signature))
    conn.execute("""INSERT INTO audit_heads VALUES(?,?,?) ON CONFLICT(tenant_id)
                    DO UPDATE SET position=excluded.position,signature=excluded.signature""",
                 (row["tenant_id"], position, signature))


def migrate_integrity():
    with db(write=True) as conn:
        if conn.execute("SELECT 1 FROM schema_migrations WHERE name='audit-chain-v1'").fetchone():
            return
        for row in conn.execute("SELECT id FROM audit ORDER BY rowid").fetchall():
            seal_event(conn, row["id"])
        conn.execute("INSERT INTO schema_migrations VALUES('audit-chain-v1')")


def verify_integrity(conn, tenant, key=None):
    events = conn.execute("SELECT * FROM audit WHERE tenant_id=? ORDER BY rowid", (tenant,)).fetchall()
    position, previous = 0, "0" * 64
    for row in events:
        position += 1
        seal = conn.execute("SELECT * FROM audit_integrity WHERE audit_id=?", (row["id"],)).fetchone()
        expected = sign(row, position, previous, key=key)
        if (not seal or seal["tenant_id"] != tenant or seal["position"] != position
                or seal["previous_hash"] != previous or not hmac.compare_digest(expected, seal["signature"])):
            return {"valid": False, "checked_events": position, "failed_event": row["id"]}
        previous = expected
    head = conn.execute("SELECT * FROM audit_heads WHERE tenant_id=?", (tenant,)).fetchone()
    seals = conn.execute("SELECT COUNT(*) FROM audit_integrity WHERE tenant_id=?", (tenant,)).fetchone()[0]
    valid = seals == position and (not head if not position else bool(head and head["position"] == position and head["signature"] == previous))
    return {"valid": valid, "checked_events": position,
            "checkpoint": {"tenant_id": tenant, "position": position, "signature": previous},
            "limitation": "Keep checkpoints outside this database to detect coordinated tail truncation. The signing key must be protected separately."}
