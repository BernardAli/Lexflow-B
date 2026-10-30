"""Shared matter queries, review composition and approval/export business rules."""
import time
from fastapi import HTTPException
from .db import record_audit, utcnow
from .extraction import FIELD_META, SCHEMAS, comparison_value
from .exporter import validate_mappings
from .validation import validate_field_value


def assert_transfer_unlocked(conn, user, matter_id):
    active = conn.execute("""SELECT 1 FROM integration_jobs j JOIN integration_transfers t ON t.id=j.transfer_id
                             WHERE t.tenant_id=? AND t.matter_id=? AND t.status='sending' AND j.lease_until>?""",
                          (user["tenant_id"], matter_id, int(time.time()))).fetchone()
    if active:
        raise HTTPException(409, "A delivery is in progress for this approved matter. Check its receipt before changing the data")


def get_matter(conn, user, matter_id):
    row = conn.execute("SELECT * FROM matters WHERE id=? AND tenant_id=?",
                       (matter_id, user["tenant_id"])).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Matter not found")
    return dict(row)


def get_doc(conn, user, doc_id):
    row = conn.execute("SELECT * FROM documents WHERE id=? AND tenant_id=?",
                       (doc_id, user["tenant_id"])).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return dict(row)


def summarize_matter(conn, row):
    m = dict(row)
    m["document_count"] = conn.execute("SELECT COUNT(*) FROM documents WHERE matter_id=?", (m["id"],)).fetchone()[0]
    m["confirmed_count"] = conn.execute("SELECT COUNT(*) FROM field_reviews WHERE matter_id=?", (m["id"],)).fetchone()[0]
    schema = SCHEMAS.get(m["matter_type"], SCHEMAS["general"])
    m["required_count"] = len(schema["required"])
    m["unreviewed_count"] = len([key for key in schema["required"] if not conn.execute(
        "SELECT 1 FROM field_reviews WHERE matter_id=? AND field_key=?", (m["id"],key)).fetchone()])
    m["conflict_count"] = sum(1 for fld in compose_fields(conn,m) if fld["status"] == "conflict")
    return m


def compose_fields(conn, matter):
    schema = SCHEMAS.get(matter["matter_type"], SCHEMAS["general"])
    keys = schema["required"] + schema["optional"]
    candidates = conn.execute("""SELECT c.*,d.name AS document_name FROM candidates c
                                  JOIN documents d ON d.id=c.document_id
                                  WHERE c.matter_id=? ORDER BY c.confidence DESC, c.created_at DESC, c.rowid DESC""", (matter["id"],)).fetchall()
    grouped = {key: [] for key in keys}
    for row in candidates:
        if row["field_key"] in grouped:
            grouped[row["field_key"]].append(dict(row))
    reviews = {r["field_key"]: dict(r) for r in conn.execute(
        "SELECT * FROM field_reviews WHERE matter_id=?", (matter["id"],)).fetchall()}
    result = []
    for key in keys:
        options = grouped[key]
        distinct = set(comparison_value(key, c["value"]) for c in options)
        review = reviews.get(key)
        if review:
            status = "confirmed"
        elif len(distinct) > 1:
            status = "conflict"
        elif len(options) >= 1:
            status = "needs_review"
        else:
            status = "missing" if key in schema["required"] else "optional"
        primary = options[0] if options else None
        value = review["value"] if review else (primary["value"] if primary else "")
        validation_error = None
        if value:
            try:
                validate_field_value(key, value)
            except ValueError as exc:
                validation_error = str(exc)
                if review:
                    status = "invalid"
        result.append({"key": key, "label": FIELD_META[key][0], "type": FIELD_META[key][1],
                       "required": key in schema["required"], "status": status,
                       "value": value, "validation_error": validation_error,
                       "confidence": 1.0 if review else (primary["confidence"] if primary else 0),
                       "reviewed_at": review["reviewed_at"] if review else None,
                       "review_note": review["note"] if review else None,
                       "review_candidate_id": review["candidate_id"] if review else None,
                       "reviewer_id": review["reviewer_id"] if review else None,
                       "candidates": options})
    return result


def approval_blockers(fields):
    return [f["label"] for f in fields if (f["required"] and f["status"] != "confirmed")
            or f["status"] in ("conflict", "invalid")]


def review_snapshot(row):
    if row is None:
        return None
    return {key: row[key] for key in ("value", "candidate_id", "reviewer_id", "note", "reviewed_at")}


def invalidate_exports(conn, user, matter_id, reason):
    assert_transfer_unlocked(conn, user, matter_id)
    rows = conn.execute("""SELECT id FROM exports WHERE matter_id=? AND tenant_id=?
                           AND id NOT IN (SELECT export_id FROM invalidated_exports)""",
                        (matter_id, user["tenant_id"])).fetchall()
    for row in rows:
        conn.execute("INSERT INTO invalidated_exports VALUES(?,?,?)", (row["id"], utcnow(), reason))
    if rows:
        record_audit(conn, user["tenant_id"], matter_id, user["id"], "exports_invalidated",
                     {"export_ids": [r["id"] for r in rows], "reason": reason})


def export_payload(conn, user, matter, connector, fmt):
    from .case_data import case_blockers
    from .connectors import approved_snapshot, serialize_snapshot, ConnectorUnavailable
    if matter["status"] not in ("approved", "exported"):
        raise HTTPException(status_code=409, detail="Approve the matter before export")
    fields = compose_fields(conn, matter)
    blockers = approval_blockers(fields) + case_blockers(conn, matter)
    if blockers:
        raise HTTPException(status_code=409, detail="Reopen and review these fields before export: " + ", ".join(blockers))
    mapping = {r["field_key"]: r["target_key"] for r in conn.execute(
        "SELECT field_key,target_key FROM connector_mappings WHERE tenant_id=?", (user["tenant_id"],))}
    try:
        validate_mappings(mapping)
        return serialize_snapshot(approved_snapshot(conn, user, matter, fields), mapping, connector, fmt)
    except ConnectorUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


