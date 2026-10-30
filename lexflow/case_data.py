"""Revision-checked preparation and explicit review of structured case data."""
import json

from fastapi import APIRouter, Depends, HTTPException

from .auth import require_user, minimum_role
from .case_models import CaseData, CaseUpdate, CaseReview, default_case, suggested_designation
from .db import db, utcnow, record_audit

router = APIRouter(prefix="/api", tags=["Structured case data"])


def case_state(conn, matter):
    row = conn.execute("SELECT * FROM matter_case_data WHERE matter_id=? AND tenant_id=?",
                       (matter["id"], matter["tenant_id"])).fetchone()
    data = json.loads(row["payload_json"]) if row else default_case(matter["matter_type"])
    return {"data": data, "revision": row["revision"] if row else 0,
            "reviewed_by": row["reviewed_by"] if row else None,
            "reviewed_at": row["reviewed_at"] if row else None,
            "suggested_designation": suggested_designation(data)}


def case_blockers(conn, matter):
    state = case_state(conn, matter)
    return ["Review the structured case details"] if state["revision"] and not state["reviewed_at"] else []


def invalidate_case_review(conn, user, matter_id, reason):
    row = conn.execute("SELECT revision,reviewed_by,reviewed_at FROM matter_case_data WHERE matter_id=? AND tenant_id=?",
                       (matter_id, user["tenant_id"])).fetchone()
    if row:
        conn.execute("UPDATE matter_case_data SET revision=revision+1,reviewed_by=NULL,reviewed_at=NULL WHERE matter_id=?",
                     (matter_id,))
        record_audit(conn, user["tenant_id"], matter_id, user["id"], "case_review_invalidated",
                     {"reason": reason, "previous": dict(row)})


def validate_references(conn, user, matter, data):
    from .matter_service import get_matter
    for item in [*data["participants"], *data["properties"]]:
        for doc_id in item["source_document_ids"]:
            if not conn.execute("SELECT 1 FROM documents WHERE id=? AND matter_id=? AND tenant_id=?",
                                (doc_id, matter["id"], user["tenant_id"])).fetchone():
                raise HTTPException(422, "Source documents must belong to this matter")
    parent = data["master_matter_id"]
    seen = {matter["id"]}
    while parent:
        if parent in seen:
            raise HTTPException(422, "Master-case links cannot form a cycle")
        seen.add(parent)
        master = get_matter(conn, user, parent)
        parent = case_state(conn, master)["data"]["master_matter_id"]


@router.get("/case-data/schema")
def case_schema(user=Depends(require_user)):
    return CaseData.model_json_schema()


@router.get("/matters/{matter_id}/case-data")
def get_case(matter_id: str, user=Depends(require_user)):
    from .matter_service import get_matter
    with db() as conn:
        return case_state(conn, get_matter(conn, user, matter_id))


@router.put("/matters/{matter_id}/case-data")
def save_case(matter_id: str, update: CaseUpdate, user=Depends(require_user)):
    from .matter_service import get_matter, invalidate_exports
    with db(write=True) as conn:
        matter = get_matter(conn, user, matter_id)
        current = case_state(conn, matter)
        if matter["status"] in ("approved", "exported"):
            raise HTTPException(409, "Reopen the matter before editing case details")
        if update.expected_revision != current["revision"]:
            raise HTTPException(409, "Case details changed. Reload the matter before saving")
        data = update.data.model_dump(mode="json")
        validate_references(conn, user, matter, data)
        invalidate_exports(conn, user, matter_id, "Structured case details changed")
        now = utcnow()
        conn.execute("""INSERT INTO matter_case_data(matter_id,tenant_id,revision,payload_json,reviewed_by,reviewed_at)
                        VALUES(?,?,?,?,NULL,NULL) ON CONFLICT(matter_id) DO UPDATE SET
                        revision=excluded.revision,payload_json=excluded.payload_json,reviewed_by=NULL,reviewed_at=NULL""",
                     (matter_id, user["tenant_id"], current["revision"] + 1, json.dumps(data, ensure_ascii=False)))
        conn.execute("UPDATE matters SET status='in_review',updated_at=? WHERE id=?", (now, matter_id))
        record_audit(conn, user["tenant_id"], matter_id, user["id"], "case_details_saved",
                     {"revision": current["revision"] + 1, "previous": current["data"], "data": data})
        return case_state(conn, matter)


@router.post("/matters/{matter_id}/case-data/review")
def review_case(matter_id: str, review: CaseReview, user=Depends(minimum_role("reviewer"))):
    from .matter_service import get_matter, assert_transfer_unlocked
    with db(write=True) as conn:
        matter = get_matter(conn, user, matter_id)
        assert_transfer_unlocked(conn, user, matter_id)
        current = case_state(conn, matter)
        if matter["status"] in ("approved", "exported") or review.expected_revision != current["revision"]:
            raise HTTPException(409, "Reopen or reload the matter before reviewing case details")
        if not conn.execute("SELECT 1 FROM documents WHERE matter_id=?", (matter_id,)).fetchone():
            raise HTTPException(422, "Add a source document before reviewing case details")
        validate_references(conn, user, matter, current["data"])
        for item in [*current["data"]["participants"], *current["data"]["properties"]]:
            if not item["source_document_ids"] and not item["source_note"]:
                raise HTTPException(422, "Each participant and property needs a source document or verification note")
        now = utcnow()
        conn.execute("UPDATE matter_case_data SET reviewed_by=?,reviewed_at=? WHERE matter_id=?",
                     (user["id"], now, matter_id))
        record_audit(conn, user["tenant_id"], matter_id, user["id"], "case_details_reviewed",
                     {"revision": current["revision"]})
        return case_state(conn, matter)
