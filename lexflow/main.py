"""LexFlow AI — functional local proof-of-concept API and web application.

Not certified for German notarial practice; live BNotK/notary vendor APIs are not connected.
"""
import hashlib
import json
import mimetypes
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi import Response, Query, Request, BackgroundTasks
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from .auth import COOKIE_NAME, login, logout, change_password, minimum_role, require_user
from .db import db, initialize, record_audit, utcnow
from .settings import PROJECT_ROOT, data_dir, seed_demo_enabled, allow_external_ai, max_upload_bytes, secure_cookies
from .seed import seed_if_empty
from .documents import parse_document, SUPPORTED
from .extraction import FIELD_META, SCHEMAS, comparison_value, rule_extract, external_ai_extract, infer_matter_type
from .exporter import generate_export, validate_mappings
from .validation import validate_field_value
from .password_reset import request_reset, complete_reset
from .security import validate_deployment, allowed_hosts, hardened
from .storage import protect, reveal, keyring
from .workflows import apply_rules
from .case_data import case_state, case_blockers, invalidate_case_review


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_deployment()
    initialize()
    seed_if_empty()
    if hardened():
        from .integrity import verify_integrity
        from .password_reset import DEMO_IDENTITIES
        with db() as conn:
            tenants = conn.execute("SELECT id FROM tenants").fetchall()
            if len(tenants) != 1:
                raise RuntimeError("Provision exactly one dedicated workspace before starting a hardened instance")
            if any(conn.execute("SELECT 1 FROM users WHERE id=?", (identity[0],)).fetchone() for identity in DEMO_IDENTITIES):
                raise RuntimeError("Hardened deployments must not contain seeded demonstration accounts")
            for tenant in tenants:
                if not keyring(tenant["id"]):
                    raise RuntimeError("Every workspace needs a storage key in the hardened profile")
                if not verify_integrity(conn, tenant["id"])["valid"]:
                    raise RuntimeError("Audit integrity failed; check the signing key and restore a verified backup")
    from .demo_notary import start, stop
    destination = start()
    try:
        yield
    finally:
        stop(destination)


app = FastAPI(title="LexFlow AI", version="0.12.0-prototype", lifespan=lifespan,
              description="Synthetic demonstration of notarial document intake, verification and approved export.")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")


@app.middleware("http")
async def auth_privacy_headers(request: Request, call_next):
    from urllib.parse import urlsplit
    try:
        host = urlsplit("//" + request.headers.get("host", "")).hostname
    except ValueError:
        host = None
    if not host or host.lower() not in allowed_hosts():
        response = JSONResponse({"detail": "Unrecognized host"}, status_code=400)
    elif hardened() and request.url.path in ("/docs", "/redoc", "/openapi.json"):
        response = JSONResponse({"detail": "Not found"}, status_code=404)
    elif hardened() and request.url.scheme != "https" and request.url.path != "/api/health":
        response = JSONResponse({"detail": "HTTPS is required"}, status_code=400)
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path not in ("/docs", "/redoc"):
        response.headers["Content-Security-Policy"] = "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    if request.url.path == "/" or request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def auth_validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/auth/"):
        # Pydantic's default errors echo input values, including passwords and tokens.
        return JSONResponse(status_code=422, content={"detail": [
            {key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()
        ]})
    return await request_validation_exception_handler(request, exc)


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=12, max_length=128)


class MatterCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    matter_type: Literal["property_purchase", "inheritance", "company_formation", "general"]


class TextIntake(BaseModel):
    matter_id: str
    filename: str = Field(default="pasted_intake.txt", min_length=1, max_length=128)
    text: str = Field(min_length=5, max_length=200_000)
    use_external_ai: bool = False


class FieldConfirm(BaseModel):
    candidate_id: str | None = None
    value: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=500)


class ExportRequest(BaseModel):
    format: Literal["json", "csv"] = "json"
    connector: Literal["approved_export", "notary_demo", "case_bundle", "pronotar32"] = "approved_export"


class MappingUpdate(BaseModel):
    mappings: dict[str, str]


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def page():
    return (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.12.0-prototype", "environment": "HARDENED PROFILE" if hardened() else "LOCAL PROTOTYPE", "external_ai_enabled": allow_external_ai()}


@app.post("/api/auth/login")
def auth_login(data: Credentials, response: Response, request: Request):
    result = login(data.email, data.password, request.client.host if request.client else "unknown")
    if isinstance(result, dict):
        response.delete_cookie(COOKIE_NAME, path="/")
        return result
    token, csrf, user = result
    response.set_cookie(COOKIE_NAME, token, max_age=12*3600, httponly=True,
                        samesite="strict", secure=secure_cookies(), path="/")
    return {"user": user, "csrf": csrf}


@app.get("/api/auth/options")
def auth_options():
    return {"demo_mode": seed_demo_enabled(), "security_profile": "hardened" if hardened() else "demo"}


@app.get("/api/auth/me")
def auth_me(user=Depends(require_user)):
    return {"user": {k: v for k, v in user.items() if k not in ("csrf", "session_hash")},
            "csrf": user["csrf"], "external_ai_enabled": allow_external_ai(),
            "demo_mode": seed_demo_enabled()}


@app.post("/api/auth/logout")
def auth_logout(response: Response, user=Depends(require_user)):
    logout(user)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.post("/api/auth/change-password")
def auth_change_password(data: PasswordChange, user=Depends(require_user)):
    change_password(user, data.current_password, data.new_password)
    with db() as conn:
        record_audit(conn, user["tenant_id"], None, user["id"], "password_changed", {})
    return {"ok": True}


@app.post("/api/auth/forgot-password")
def auth_forgot_password(data: PasswordResetRequest, request: Request, background_tasks: BackgroundTasks):
    return request_reset(data.email, request.client.host if request.client else "unknown", background_tasks)


@app.post("/api/auth/reset-password")
def auth_reset_password(data: PasswordResetConfirm, request: Request, response: Response):
    complete_reset(data.token, data.new_password, data.confirm_password,
                   request.client.host if request.client else "unknown")
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True, "message": "Your password has been reset. Sign in with your new password."}


@app.get("/api/config")
def app_config(user=Depends(require_user)):
    from .integrations import webhook_target, destination_target
    webhook = bool(webhook_target(user["tenant_id"]))
    return {"schemas": SCHEMAS, "field_meta": {k: {"label": v[0], "type": v[1]} for k, v in FIELD_META.items()},
            "supported_extensions": sorted(SUPPORTED), "max_upload_mb": max_upload_bytes()//1024//1024,
            "external_ai_enabled": allow_external_ai(), "external_ai_default": False,
            "live_connector_enabled": webhook, "vendor_connector_enabled": False,
            "demo_notary_enabled": bool(destination_target(user["tenant_id"], "demo_notary")),
            "demo_mode": seed_demo_enabled(), "workspace": user["workspace"]}


from .matter_service import (get_matter, get_doc, summarize_matter, compose_fields, approval_blockers,
                             review_snapshot, invalidate_exports, export_payload)


@app.get("/api/dashboard")
def dashboard(user=Depends(require_user)):
    with db() as conn:
        ms = conn.execute("SELECT * FROM matters WHERE tenant_id=? ORDER BY updated_at DESC", (user["tenant_id"],)).fetchall()
        summaries = [summarize_matter(conn, m) for m in ms]
        recent = conn.execute("""SELECT a.action,a.details_json,a.created_at,m.reference,u.name AS actor
                                 FROM audit a LEFT JOIN matters m ON a.matter_id=m.id
                                 LEFT JOIN users u ON a.actor_id=u.id
                                 WHERE a.tenant_id=? ORDER BY a.created_at DESC LIMIT 7""", (user["tenant_id"],)).fetchall()
        document_count = conn.execute("SELECT COUNT(*) FROM documents WHERE tenant_id=?", (user["tenant_id"],)).fetchone()[0]
        export_count = conn.execute("SELECT COUNT(*) FROM exports WHERE tenant_id=?", (user["tenant_id"],)).fetchone()[0]
        return {"total_matters":len(ms), "documents":document_count,"exports":export_count,
                "review_queue":sum(1 for m in summaries if m["status"] in ("new","in_review")),
                "conflicts":sum(m["conflict_count"] for m in summaries),
                "status_counts":{k:sum(m["status"]==k for m in summaries) for k in ("new","in_review","approved","exported")},
                "recent_matters":summaries[:6], "recent_activity":[dict(a) for a in recent]}


@app.get("/api/matters")
def list_matters(q: str = "", status: str = "", user=Depends(require_user)):
    with db() as conn:
        sql = "SELECT * FROM matters WHERE tenant_id=?"
        args = [user["tenant_id"]]
        if q:
            sql += " AND (title LIKE ? OR reference LIKE ?)"
            args += [f"%{q[:80]}%", f"%{q[:80]}%"]
        if status:
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY updated_at DESC LIMIT 200"
        return {"matters": [summarize_matter(conn,m) for m in conn.execute(sql,args).fetchall()]}


@app.post("/api/matters")
def create_matter(data: MatterCreate, user=Depends(require_user)):
    now = utcnow()
    matter_id = uuid.uuid4().hex
    with db(write=True) as conn:
        tenant = user["tenant_id"]
        prefix = re.sub("[^A-Z]", "", user["workspace"].split(" ")[1].upper())[:3] if " " in user["workspace"] else "LXF"
        # Try until an unused reference is found even after restarts and deletions.
        base = conn.execute("SELECT COUNT(*) FROM matters WHERE tenant_id=?", (tenant,)).fetchone()[0] + 45
        while True:
            reference = f"{now[:4]}-{prefix}-{base:04d}"
            if not conn.execute("SELECT 1 FROM matters WHERE tenant_id=? AND reference=?", (tenant,reference)).fetchone():
                break
            base += 1
        conn.execute("INSERT INTO matters VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (matter_id,tenant,reference,data.title.strip(),data.matter_type,"new",now,now,None,None))
        record_audit(conn, tenant, matter_id, user["id"], "matter_created",
                     {"reference":reference,"matter_type":data.matter_type})
    return {"id":matter_id,"reference":reference}


@app.get("/api/matters/{matter_id}")
def matter_detail(matter_id: str, user=Depends(require_user)):
    with db() as conn:
        m = get_matter(conn,user,matter_id)
        docs = [dict(r) for r in conn.execute("""SELECT id,name,media_type,byte_size,created_at,
                                    LENGTH(raw_text) as text_length FROM documents
                                    WHERE tenant_id=? AND matter_id=? ORDER BY created_at DESC""",
                                    (user["tenant_id"],matter_id)).fetchall()]
        exports = [dict(r) for r in conn.execute("""SELECT e.id,e.filename,e.format,e.connector,e.created_at,
                                         i.invalidated_at,i.reason AS invalidation_reason FROM exports e
                                         LEFT JOIN invalidated_exports i ON i.export_id=e.id
                                         WHERE e.tenant_id=? AND e.matter_id=? ORDER BY e.created_at DESC""",
                                         (user["tenant_id"],matter_id)).fetchall()]
        fields = compose_fields(conn,m)
        required = [f for f in fields if f["required"]]
        blockers = approval_blockers(fields) + case_blockers(conn, m)
        return {"matter": summarize_matter(conn,m),"fields":fields,"documents":docs,"exports":exports,
                "case_data": case_state(conn, m),
                "ready_for_approval":bool(docs) and not blockers,
                "approval_blockers":blockers,
                "required_confirmed":sum(f["status"]=="confirmed" for f in required),
                "required_total":len(required)}


async def prepare_document(matter, filename, raw, text, warnings, use_external_ai):
    suggestions = rule_extract(text,matter["matter_type"])
    if matter.get("tenant_id"):
        with db() as conn:
            apply_rules(conn, matter["tenant_id"], matter["matter_type"], text, suggestions)
    if use_external_ai and text.strip():
        try:
            ai_candidates = await external_ai_extract(text,matter["matter_type"])
            distinct = {(c["field_key"], comparison_value(c["field_key"],c["value"])) for c in suggestions}
            for c in ai_candidates:
                marker = (c["field_key"],comparison_value(c["field_key"],c["value"]))
                if marker not in distinct:
                    suggestions.append(c)
                    distinct.add(marker)
            warnings.append("External AI used with explicit opt-in. Verify all suggestions before approval.")
        except Exception as exc:
            warnings.append(f"External AI failed ({type(exc).__name__}); local extraction was retained.")
    inferred = infer_matter_type(text)
    if inferred != "general" and inferred != matter["matter_type"]:
        warnings.append(f"Document appears to concern {SCHEMAS[inferred]['label']}; verify the selected matter type.")
    if not suggestions:
        warnings.append("No labeled fields detected. You can enter values manually in the Review workbench.")
    return {"document_id":uuid.uuid4().hex, "filename":filename,"raw":raw,"text":text,
            "candidates":suggestions,"warnings":warnings,"inferred_matter_type":inferred,
            "external_ai_requested":use_external_ai}


def store_documents(conn, user, matter_id, prepared, paths):
    get_matter(conn, user, matter_id)
    now = utcnow()
    previous = conn.execute("SELECT * FROM field_reviews WHERE matter_id=?", (matter_id,)).fetchall()
    if previous:
        record_audit(conn, user["tenant_id"], matter_id, user["id"], "reviews_invalidated",
                     {"reason":"new_documents", "previous_reviews":
                      [{"field":r["field_key"], **review_snapshot(r)} for r in previous]})
    invalidate_exports(conn, user, matter_id, "Source documents changed")
    invalidate_case_review(conn, user, matter_id, "Source documents changed")
    target_dir = data_dir() / "uploads" / user["tenant_id"] / matter_id
    target_dir.mkdir(parents=True, exist_ok=True)
    for doc in prepared:
        target = target_dir / (doc["document_id"] + Path(doc["filename"]).suffix.lower())
        with target.open("xb") as output:
            paths.append(target)
            output.write(protect(doc["raw"], user["tenant_id"]))
        conn.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
                     (doc["document_id"],user["tenant_id"],matter_id,Path(doc["filename"]).name[:128],
                      mimetypes.guess_type(doc["filename"])[0] or "application/octet-stream",
                      len(doc["raw"]),hashlib.sha256(doc["raw"]).hexdigest(),doc["text"],str(target),now))
        conn.execute("INSERT INTO document_processing VALUES(?,?)",
                     (doc["document_id"],json.dumps(doc["warnings"],ensure_ascii=False)))
        for candidate in doc["candidates"]:
            conn.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (uuid.uuid4().hex,user["tenant_id"],matter_id,doc["document_id"],candidate["field_key"],
                          candidate["value"],candidate["confidence"],candidate["evidence"],candidate["origin"],now))
        record_audit(conn,user["tenant_id"],matter_id,user["id"],"document_ingested",
                     {"document_id":doc["document_id"],"filename":Path(doc["filename"]).name[:128],
                      "bytes":len(doc["raw"]),"candidates":len(doc["candidates"]),
                      "external_ai_requested":doc["external_ai_requested"],
                      "inferred_matter_type":doc["inferred_matter_type"],"warnings":doc["warnings"]})
    conn.execute("DELETE FROM field_reviews WHERE matter_id=?", (matter_id,))
    conn.execute("UPDATE matters SET status='in_review',approved_at=NULL,approved_by=NULL,updated_at=? WHERE id=?", (now,matter_id))


def intake_result(doc, matter_id):
    return {"document_id":doc["document_id"],"filename":doc["filename"],"suggestions":len(doc["candidates"]),
            "warnings":doc["warnings"],"matter_id":matter_id,"inferred_matter_type":doc["inferred_matter_type"]}


async def ingest_batch(user, matter_id, files, use_external_ai, *, intake_key=None, intake_digest=None):
    with db() as conn:
        matter = get_matter(conn,user,matter_id)
    if use_external_ai and not allow_external_ai():
        raise HTTPException(status_code=400, detail="External AI not configured. See README and enable it explicitly.")
    # Parse the entire batch before any external processing or durable changes.
    parsed = [(filename,raw,*parse_document(filename,raw)) for filename,raw in files]
    prepared = [await prepare_document(matter,filename,raw,text,warnings,use_external_ai)
                for filename,raw,text,warnings in parsed]
    paths = []
    try:
        with db(write=True) as conn:
            if intake_key:
                receipt = conn.execute("SELECT * FROM intake_receipts WHERE tenant_id=? AND idempotency_key=?", (user["tenant_id"], intake_key)).fetchone()
                if receipt:
                    if receipt["payload_hash"] != intake_digest:
                        raise HTTPException(409, "Key was used for different intake content")
                    return json.loads(receipt["result_json"]) | {"replayed": True}
            store_documents(conn,user,matter_id,prepared,paths)
            if intake_key:
                result = {"results": [intake_result(doc,matter_id) for doc in prepared], "replayed": False}
                conn.execute("INSERT INTO intake_receipts VALUES(?,?,?,?,?)", (user["tenant_id"], intake_key, intake_digest, json.dumps(result), utcnow()))
    except Exception:
        for path in paths:
            path.unlink(missing_ok=True)
        raise
    return result if intake_key else [intake_result(doc,matter_id) for doc in prepared]


@app.post("/api/intake/text")
async def intake_text(data: TextIntake, user=Depends(require_user)):
    filename = Path(data.filename).name
    if not filename.lower().endswith(".txt"):
        filename += ".txt"
    return (await ingest_batch(user,data.matter_id,[(filename,data.text.encode("utf-8"))],data.use_external_ai))[0]


@app.post("/api/intake/upload")
async def intake_upload(matter_id: str = Form(...), files: list[UploadFile] = File(...),
                        use_external_ai: bool = Form(False), user=Depends(require_user)):
    if len(files) > 6:
        raise HTTPException(status_code=413, detail="Maximum six files per batch")
    with db() as conn:
        get_matter(conn,user,matter_id)
    all_data = []
    # Validate every file before storing anything to avoid accidental partial upload on invalid input.
    for file in files:
        filename = Path(file.filename or "").name
        if not filename or Path(filename).suffix.lower() not in SUPPORTED:
            raise HTTPException(status_code=415, detail=f"Unsupported file type: {filename}")
        raw = await file.read(max_upload_bytes()+1)
        if len(raw) > max_upload_bytes():
            raise HTTPException(status_code=413, detail=f"File too large: {filename}")
        all_data.append((filename,raw))
    return {"results":await ingest_batch(user,matter_id,all_data,use_external_ai)}


@app.post("/api/demo/start")
async def start_demo(user=Depends(require_user)):
    """Create a fresh synthetic example without changing earlier demonstration work."""
    if not seed_demo_enabled():
        raise HTTPException(status_code=404, detail="Demo examples are disabled")
    prepared = []
    for filename in ("01_buyer_questionnaire.txt", "02_land_register_conflict.txt"):
        raw = (PROJECT_ROOT / "samples" / filename).read_bytes()
        text, warnings = parse_document(filename,raw)
        prepared.append(await prepare_document({"matter_type":"property_purchase","tenant_id":user["tenant_id"]},filename,raw,text,warnings,False))
    matter_id, now = uuid.uuid4().hex, utcnow()
    reference = f"{now[:4]}-DEMO-{matter_id[:8].upper()}"
    paths = []
    try:
        with db(write=True) as conn:
            conn.execute("INSERT INTO matters VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (matter_id,user["tenant_id"],reference,"Demo — Sonnenallee property purchase",
                          "property_purchase","new",now,now,None,None))
            record_audit(conn,user["tenant_id"],matter_id,user["id"],"matter_created",
                         {"reference":reference,"matter_type":"property_purchase","synthetic":True})
            store_documents(conn,user,matter_id,prepared,paths)
    except Exception:
        for path in paths:
            path.unlink(missing_ok=True)
        raise
    return {"id":matter_id,"reference":reference,"synthetic":True}


@app.get("/api/documents/{doc_id}")
def document_detail(doc_id: str,user=Depends(require_user)):
    with db() as conn:
        doc = get_doc(conn,user,doc_id)
        processing = conn.execute("SELECT warnings_json FROM document_processing WHERE document_id=?", (doc_id,)).fetchone()
        return {"id":doc["id"],"matter_id":doc["matter_id"],"name":doc["name"],
                "media_type":doc["media_type"],"byte_size":doc["byte_size"],
                "created_at":doc["created_at"],"raw_text":doc["raw_text"], "sha256":doc["sha256"],
                "warnings":json.loads(processing["warnings_json"]) if processing else []}


@app.get("/api/documents/{doc_id}/download")
def download_document(doc_id: str,user=Depends(require_user)):
    with db() as conn:
        doc = get_doc(conn,user,doc_id)
    file_path = Path(doc["file_path"]).resolve()
    if not file_path.is_relative_to(data_dir()) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return artifact_download(file_path, user["tenant_id"], doc["name"])


@app.post("/api/matters/{matter_id}/fields/{field_key}/confirm")
def confirm_field(matter_id: str, field_key: str, data: FieldConfirm,
                  user=Depends(minimum_role("reviewer"))):
    with db(write=True) as conn:
        m = get_matter(conn,user,matter_id)
        if field_key not in SCHEMAS[m["matter_type"]]["required"] + SCHEMAS[m["matter_type"]]["optional"]:
            raise HTTPException(status_code=404, detail="Unknown field")
        if m["status"] in ("approved","exported"):
            raise HTTPException(status_code=409, detail="Reopen matter before editing approved data")
        candidate_id = data.candidate_id
        if candidate_id:
            candidate = conn.execute("""SELECT value FROM candidates WHERE id=? AND field_key=? AND matter_id=? AND tenant_id=?""",
                            (candidate_id,field_key,matter_id,user["tenant_id"])).fetchone()
            if not candidate:
                raise HTTPException(status_code=404, detail="Candidate not found")
            value = candidate["value"]
        else:
            value = (data.value or "").strip()
            if not value:
                raise HTTPException(status_code=422, detail="Provide an extracted option or manual value")
        try:
            value = validate_field_value(field_key, value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"{FIELD_META[field_key][0]}: {exc}") from exc
        previous = conn.execute("SELECT * FROM field_reviews WHERE matter_id=? AND field_key=?",
                                (matter_id,field_key)).fetchone()
        now = utcnow()
        invalidate_case_review(conn, user, matter_id, "Reviewed field changed")
        conn.execute("""INSERT INTO field_reviews(id,tenant_id,matter_id,field_key,value,candidate_id,reviewer_id,note,reviewed_at)
                        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(matter_id,field_key) DO UPDATE SET
                        value=excluded.value,candidate_id=excluded.candidate_id,reviewer_id=excluded.reviewer_id,
                        note=excluded.note,reviewed_at=excluded.reviewed_at""",
                      (uuid.uuid4().hex,user["tenant_id"],matter_id,field_key,value,candidate_id,user["id"],data.note,now))
        conn.execute("UPDATE matters SET status='in_review', updated_at=? WHERE id=?",(now,matter_id))
        record_audit(conn,user["tenant_id"],matter_id,user["id"],"field_confirmed",
                     {"field":field_key,"source":"candidate" if candidate_id else "manual",
                      "previous":review_snapshot(previous),
                      "review":{"value":value,"candidate_id":candidate_id,"note":data.note,
                                "reviewer_id":user["id"],"reviewed_at":now}})
    return {"ok":True,"field_key":field_key,"value":value}


@app.post("/api/matters/{matter_id}/fields/{field_key}/clear")
def clear_field(matter_id: str, field_key: str, user=Depends(minimum_role("reviewer"))):
    with db(write=True) as conn:
        m = get_matter(conn,user,matter_id)
        if field_key not in SCHEMAS[m["matter_type"]]["required"] + SCHEMAS[m["matter_type"]]["optional"]:
            raise HTTPException(status_code=404, detail="Unknown field")
        if m["status"] in ("approved","exported"):
            raise HTTPException(status_code=409, detail="Reopen matter first")
        previous = conn.execute("SELECT * FROM field_reviews WHERE matter_id=? AND field_key=?",
                                (matter_id,field_key)).fetchone()
        invalidate_case_review(conn, user, matter_id, "Field review cleared")
        conn.execute("DELETE FROM field_reviews WHERE matter_id=? AND field_key=?",(matter_id,field_key))
        conn.execute("UPDATE matters SET status='in_review',updated_at=? WHERE id=?",(utcnow(),matter_id))
        record_audit(conn,user["tenant_id"],matter_id,user["id"],"field_unconfirmed",
                     {"field":field_key,"previous":review_snapshot(previous)})
    return {"ok":True}


@app.post("/api/matters/{matter_id}/approve")
def approve_matter(matter_id: str,user=Depends(minimum_role("reviewer"))):
    with db(write=True) as conn:
        m = get_matter(conn,user,matter_id)
        if m["status"] in ("approved","exported"):
            raise HTTPException(status_code=409, detail="Matter already approved")
        if not conn.execute("SELECT 1 FROM documents WHERE matter_id=?",(matter_id,)).fetchone():
            raise HTTPException(status_code=422, detail="At least one source document is required")
        fields = compose_fields(conn,m)
        required = [f for f in fields if f["required"]]
        outstanding = approval_blockers(fields) + case_blockers(conn, m)
        if outstanding:
            raise HTTPException(status_code=422, detail="Review required fields and resolve all conflicts or invalid values: " + ", ".join(outstanding))
        now = utcnow()
        conn.execute("UPDATE matters SET status='approved',approved_by=?,approved_at=?,updated_at=? WHERE id=?",
                     (user["id"],now,now,matter_id))
        record_audit(conn,user["tenant_id"],matter_id,user["id"],"matter_approved",
                     {"reviewed_required_fields":len(required)})
    return {"ok":True,"approved_at":now}


@app.post("/api/matters/{matter_id}/reopen")
def reopen_matter(matter_id: str,user=Depends(minimum_role("reviewer"))):
    with db(write=True) as conn:
        m = get_matter(conn,user,matter_id)
        if m["status"] not in ("approved","exported"):
            raise HTTPException(status_code=409, detail="Matter is not approved or exported")
        conn.execute("UPDATE matters SET status='in_review',approved_by=NULL,approved_at=NULL,updated_at=? WHERE id=?",
                    (utcnow(),matter_id))
        invalidate_exports(conn,user,matter_id,"Matter reopened for review")
        invalidate_case_review(conn, user, matter_id, "Matter reopened")
        record_audit(conn,user["tenant_id"],matter_id,user["id"],"matter_reopened",{})
    return {"ok":True}


@app.get("/api/matters/{matter_id}/export/preview")
def export_preview(matter_id: str,fmt: Literal["json","csv"]="json",
                   connector: Literal["approved_export","notary_demo","case_bundle","pronotar32"]="approved_export", user=Depends(require_user)):
    with db() as conn:
        m = get_matter(conn,user,matter_id)
        payload = export_payload(conn,user,m,connector,fmt)
        return {"preview":payload.decode("utf-8-sig"),"format":fmt}


@app.post("/api/matters/{matter_id}/exports")
def create_export(matter_id: str,data:ExportRequest,user=Depends(minimum_role("reviewer"))):
    path = None
    try:
        with db(write=True) as conn:
            m = get_matter(conn,user,matter_id)
            payload = export_payload(conn,user,m,data.connector,data.format)
            export_id = uuid.uuid4().hex
            folder = data_dir()/"exports"/user["tenant_id"]
            folder.mkdir(parents=True,exist_ok=True)
            filename = f"{m['reference']}_{data.connector}_{utcnow()[:10]}.{data.format}"
            path = folder/(export_id+"."+data.format)
            path.write_bytes(protect(payload, user["tenant_id"]))
            now = utcnow()
            conn.execute("INSERT INTO exports VALUES(?,?,?,?,?,?,?,?,?)",
                         (export_id,user["tenant_id"],matter_id,str(path),filename,data.format,data.connector,user["id"],now))
            conn.execute("UPDATE matters SET status='exported',updated_at=? WHERE id=?",(now,matter_id))
            record_audit(conn,user["tenant_id"],matter_id,user["id"],"approved_export_generated",
                         {"export_id":export_id,"connector":data.connector,"format":data.format,"live_transfer":False})
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    return {"id":export_id,"filename":filename,"download_url":f"/api/exports/{export_id}/download", "live_transfer":False}


@app.get("/api/exports")
def list_exports(user=Depends(require_user)):
    with db() as conn:
        rows = conn.execute("""SELECT e.id,e.matter_id,e.filename,e.format,e.connector,e.created_at,m.reference,
                              m.title,u.name AS actor,i.invalidated_at,i.reason AS invalidation_reason FROM exports e
                              JOIN matters m ON e.matter_id=m.id
                              JOIN users u ON e.created_by=u.id
                              LEFT JOIN invalidated_exports i ON i.export_id=e.id
                              WHERE e.tenant_id=? ORDER BY e.created_at DESC LIMIT 200""",
                            (user["tenant_id"],)).fetchall()
        return {"exports":[dict(row) for row in rows]}


@app.get("/api/exports/{export_id}/download")
def download_export(export_id: str,user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT * FROM exports WHERE id=? AND tenant_id=?",(export_id,user["tenant_id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404,detail="Export not found")
        invalidated = conn.execute("SELECT reason FROM invalidated_exports WHERE export_id=?",(export_id,)).fetchone()
        if invalidated:
            raise HTTPException(status_code=409,detail="Export is no longer current: " + invalidated["reason"] + ". Approve and generate a new export.")
        path = Path(row["file_path"]).resolve()
        if not path.is_relative_to(data_dir()) or not path.is_file():
            raise HTTPException(status_code=404,detail="Export file missing")
        return artifact_download(path, user["tenant_id"], row["filename"])


def artifact_download(path, tenant, filename):
    from urllib.parse import quote
    return Response(reveal(path.read_bytes(), tenant), media_type="application/octet-stream",
                    headers={"Content-Disposition": "attachment; filename*=UTF-8''" + quote(filename, safe="")})


@app.get("/api/audit")
def list_audit(limit: int=Query(75,ge=1,le=300),matter_id: str|None=None,user=Depends(require_user)):
    with db() as conn:
        args = [user["tenant_id"]]
        sql = """SELECT a.id,a.matter_id,a.action,a.details_json,a.created_at,m.reference,u.name AS actor
                 FROM audit a LEFT JOIN matters m ON a.matter_id=m.id
                 LEFT JOIN users u ON a.actor_id=u.id WHERE a.tenant_id=?"""
        if matter_id:
            get_matter(conn,user,matter_id)
            sql += " AND a.matter_id=?"
            args.append(matter_id)
        sql += " ORDER BY a.created_at DESC, a.rowid DESC LIMIT ?"
        args.append(limit)
        return {"events":[dict(r) for r in conn.execute(sql,args).fetchall()]}


@app.get("/api/settings/mappings")
def list_mappings(user=Depends(require_user)):
    with db() as conn:
        rows = conn.execute("SELECT field_key,target_key FROM connector_mappings WHERE tenant_id=? ORDER BY field_key",
                             (user["tenant_id"],)).fetchall()
    return {"mappings":{r["field_key"]:r["target_key"] for r in rows},
            "connector_profiles":[{"id":"approved_export","label":"Approved JSON/CSV export","live":False},
                                  {"id":"notary_demo","label":"Mock notary connector (file-based)","live":False}]}


@app.put("/api/settings/mappings")
def update_mappings(data:MappingUpdate,user=Depends(minimum_role("admin"))):
    if not data.mappings or len(data.mappings)>len(FIELD_META):
        raise HTTPException(status_code=422,detail="Invalid mapping set")
    with db(write=True) as conn:
        current = {r["field_key"]:r["target_key"] for r in conn.execute(
            "SELECT field_key,target_key FROM connector_mappings WHERE tenant_id=?",(user["tenant_id"],))}
        try:
            validate_mappings(current | data.mappings)
        except ValueError as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc
        changed = {key:{"before":current.get(key),"after":target} for key,target in data.mappings.items()
                   if current.get(key) != target}
        for key,target in data.mappings.items():
            conn.execute("""INSERT INTO connector_mappings VALUES(?,?,?) ON CONFLICT(tenant_id,field_key)
                            DO UPDATE SET target_key=excluded.target_key""",(user["tenant_id"],key,target))
        if changed:
            approved = conn.execute("SELECT id,approved_by,approved_at FROM matters WHERE tenant_id=? AND status IN ('approved','exported')",
                                    (user["tenant_id"],)).fetchall()
            for matter in approved:
                invalidate_exports(conn,user,matter["id"],"Destination mappings changed")
                conn.execute("UPDATE matters SET status='in_review',approved_by=NULL,approved_at=NULL,updated_at=? WHERE id=?",
                             (utcnow(),matter["id"]))
                record_audit(conn,user["tenant_id"],matter["id"],user["id"],"approval_invalidated",
                             {"reason":"destination_mappings_changed","previous_approved_at":matter["approved_at"],
                              "previous_approved_by":matter["approved_by"]})
            record_audit(conn,user["tenant_id"],None,user["id"],"connector_mappings_updated",{"changes":changed})
    return {"ok":True}


@app.get("/api/settings/users")
def list_users(user=Depends(minimum_role("admin"))):
    with db() as conn:
        return {"users":[dict(r) for r in conn.execute(
            "SELECT id,name,email,role FROM users WHERE tenant_id=? ORDER BY name",(user["tenant_id"],)).fetchall()]}


from .workflows import router as workflows_router
from .integrations import router as integrations_router
from .pilot import router as pilot_router
from .security import router as security_router
from .mfa import router as mfa_router
from .demo_notary import router as demo_notary_router
from .case_data import router as case_data_router
from .connectors import router as connectors_router
for feature_router in (workflows_router, integrations_router, pilot_router, security_router, mfa_router, demo_notary_router, case_data_router, connectors_router):
    app.include_router(feature_router)
