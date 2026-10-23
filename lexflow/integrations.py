"""Approved local receiver and opt-in, signed HTTPS webhook transfers."""
import hashlib
import hmac
import json
import os
import re
import ssl
import time
import uuid
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field
from typing import Literal
from .auth import require_user, minimum_role
from .db import db, record_audit, utcnow

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


class Transfer(BaseModel):
    matter_id: str
    connector: Literal["demo_receiver", "webhook", "demo_notary"] = "demo_receiver"
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    preview_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class DryRun(BaseModel):
    matter_id: str
    connector: Literal["demo_receiver", "webhook", "demo_notary"] = "demo_receiver"


def webhook_target(tenant):
    target = json.loads(os.getenv("LEXFLOW_WEBHOOK_TARGETS") or "{}").get(tenant)
    if not target:
        return None
    parsed = urlsplit(target.get("url", ""))
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or len(target.get("secret", "")) < 32):
        raise HTTPException(503, "The workspace webhook requires a valid HTTPS URL and a 32+ character signing secret")
    return target


def destination_target(tenant, connector):
    if connector == "demo_notary":
        from .demo_notary import target
        return target(tenant)
    return webhook_target(tenant) if connector == "webhook" else None


def target_hash(target):
    if target is None:
        return "local-receiver-v1"
    identity = {key: target.get(key) for key in ("identity", "secret", "require_signed_receipt")}
    if not target.get("identity"):
        identity["url"] = target["url"]
        identity["ca_file"] = target.get("ca_file")
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def approved_payload(conn, user, data):
    from .matter_service import get_matter, export_payload
    matter = get_matter(conn, user, data.matter_id)
    payload = json.loads(export_payload(conn, user, matter, "approved_export", "json"))
    payload.pop("not_a_live_transmission", None)
    payload.update(specification="lexflow-approved-transfer-v1", connector=data.connector,
                   simulated=data.connector != "webhook", workspace_id=user["tenant_id"], source_matter_id=data.matter_id)
    return payload


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@router.get("")
def overview(user=Depends(require_user)):
    with db() as conn:
        transfers = [dict(r) for r in conn.execute("""SELECT t.*,m.reference,COALESCE(j.attempt_count,0) AS attempt_count FROM integration_transfers t
                     JOIN matters m ON m.id=t.matter_id LEFT JOIN integration_jobs j ON j.transfer_id=t.id
                     WHERE t.tenant_id=? ORDER BY t.rowid DESC LIMIT 100""", (user["tenant_id"],))]
        records = [dict(r) for r in conn.execute("SELECT * FROM receiver_records WHERE tenant_id=? ORDER BY rowid DESC LIMIT 30", (user["tenant_id"],))]
    return {"webhook_configured": bool(webhook_target(user["tenant_id"])), "notary_configured": bool(destination_target(user["tenant_id"], "demo_notary")),
            "transfers": transfers, "receiver_records": records,
            "agents": [{"name": "Folder intake agent", "path": "agents/folder_agent.py", "status": "available"}],
            "vendor_plugins": "Outlook, Word and BNotK/XNP are not connected"}


@router.post("/dry-run")
def dry_run(data: DryRun, user=Depends(minimum_role("reviewer"))):
    if data.connector != "demo_receiver" and not destination_target(user["tenant_id"], data.connector):
        raise HTTPException(503, "The selected destination is not configured for this workspace")
    with db() as conn:
        payload = approved_payload(conn, user, data)
    return {"valid": True, "payload": payload, "preview_hash": payload_hash(payload), "will_send": False,
            "destination": {"demo_receiver": "Local demonstration receiver", "demo_notary": "NotaryDesk Demo (HTTPS)", "webhook": "Configured HTTPS webhook"}[data.connector]}


def send_webhook(target, payload, key):
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(target["secret"].encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    try:
        verification = ssl.create_default_context(cafile=target["ca_file"]) if target.get("ca_file") else True
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False, verify=verification) as client:
            response = client.post(target["url"], content=body, headers={"Content-Type": "application/json",
                "Idempotency-Key": key, "X-LexFlow-Timestamp": stamp, "X-LexFlow-Signature": "sha256=" + signature})
        if 400 <= response.status_code < 500:
            return "failed", {"message": "Destination rejected the transfer", "http_status": response.status_code}
        if response.is_success:
            result = response.json()
            receipt = result.get("receipt_id", "")
            if result.get("accepted") is True and isinstance(receipt, str) and re.fullmatch(r"[\w.-]{1,128}", receipt):
                if target.get("require_signed_receipt"):
                    expected = "sha256=" + hmac.new(target["secret"].encode(), response.content, hashlib.sha256).hexdigest()
                    if (not hmac.compare_digest(expected, response.headers.get("X-LexFlow-Receipt-Signature", ""))
                            or result.get("idempotency_key") != key
                            or result.get("payload_sha256") != hashlib.sha256(body).hexdigest()):
                        return "uncertain", {"message": "Destination receipt could not be authenticated. Check the destination before retrying."}
                return "accepted", {"receipt_id": receipt, "http_status": response.status_code}
        return "uncertain", {"message": "Destination did not provide a valid acceptance receipt. Check it before retrying with the same key."}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, OSError):
        return "uncertain", {"message": "Delivery outcome is uncertain. Check the destination and retry with the same key."}


@router.post("/transfers")
def transfer(data: Transfer, user=Depends(minimum_role("reviewer"))):
    target = destination_target(user["tenant_id"], data.connector)
    if data.connector != "demo_receiver" and not target:
        raise HTTPException(503, "The selected destination is not configured for this workspace")
    with db(write=True) as conn:
        existing = conn.execute("SELECT * FROM integration_transfers WHERE tenant_id=? AND idempotency_key=?", (user["tenant_id"], data.idempotency_key)).fetchone()
        if existing and (existing["matter_id"] != data.matter_id or existing["connector"] != data.connector or existing["payload_hash"] != data.preview_hash):
            raise HTTPException(409, "This idempotency key belongs to another transfer or approved payload")
        if existing and existing["status"] == "accepted":
            return json.loads(existing["receipt_json"]) | {"replayed": True}
        payload = approved_payload(conn, user, data)
        digest = payload_hash(payload)
        if digest != data.preview_hash:
            raise HTTPException(409, "The approved data changed after preview. Run a new dry run")
        transfer_id = existing["id"] if existing else uuid.uuid4().hex
        job = conn.execute("SELECT target_hash FROM integration_jobs WHERE transfer_id=?", (transfer_id,)).fetchone()
        if job and job["target_hash"] != target_hash(target):
            raise HTTPException(409, "The destination changed. Check the earlier outcome before preparing another transfer")
        if not existing:
            result = {"id": transfer_id, "status": "pending", "connector": data.connector,
                      "simulated": data.connector != "webhook", "idempotency_key": data.idempotency_key,
                      "created_at": utcnow(), "replayed": False}
            conn.execute("INSERT INTO integration_transfers VALUES(?,?,?,?,?,?,?,?,?,?)", (transfer_id, user["tenant_id"], data.matter_id, data.connector, data.idempotency_key, digest, "pending", json.dumps(result), user["id"], utcnow()))
            record_audit(conn, user["tenant_id"], data.matter_id, user["id"], "connector_transfer_queued", {"transfer_id": transfer_id, "payload_hash": digest, "connector": data.connector})
        if not job:
            conn.execute("INSERT INTO integration_jobs(transfer_id,payload_json,target_hash,updated_at) VALUES(?,?,?,?)", (transfer_id, json.dumps(payload), target_hash(target), utcnow()))
    from .delivery import deliver
    return deliver(user["tenant_id"], transfer_id)


@router.post("/intake")
async def agent_intake(request: Request, idempotency_key: str = Header(..., alias="Idempotency-Key"), user=Depends(require_user)):
    """Multipart adapter used by folder agents; same parser and approval gates as the UI."""
    from .main import ingest_batch, get_matter
    from .settings import max_upload_bytes
    from .documents import SUPPORTED
    from pathlib import Path
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", idempotency_key):
        raise HTTPException(422, "Invalid idempotency key")
    async with request.form(max_files=1, max_fields=2, max_part_size=max_upload_bytes()) as form:
        matter_id, upload = form.get("matter_id"), form.get("file")
        if not isinstance(matter_id, str) or not hasattr(upload, "read"):
            raise HTTPException(422, "Provide matter_id and one file")
        name = Path(upload.filename or "").name
        if Path(name).suffix.lower() not in SUPPORTED:
            raise HTTPException(415, "Unsupported file type")
        raw = await upload.read(max_upload_bytes() + 1)
    if not raw or len(raw) > max_upload_bytes():
        raise HTTPException(413, "File is empty or too large")
    digest = hashlib.sha256(matter_id.encode() + b"\0" + name.encode() + b"\0" + raw).hexdigest()
    with db() as conn:
        get_matter(conn, user, matter_id)
        existing = conn.execute("SELECT * FROM intake_receipts WHERE tenant_id=? AND idempotency_key=?", (user["tenant_id"], idempotency_key)).fetchone()
        if existing:
            if existing["payload_hash"] != digest:
                raise HTTPException(409, "Key was used for different intake content")
            return json.loads(existing["result_json"]) | {"replayed": True}
    return await ingest_batch(user, matter_id, [(name, raw)], False, intake_key=idempotency_key, intake_digest=digest)
