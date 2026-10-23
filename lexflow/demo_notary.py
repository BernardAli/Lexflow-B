"""Fictional NotaryDesk destination: separate TLS server, database and receipts.

This local integration lab is disabled outside demo mode. Its browser workspace
uses LexFlow authentication, while every destination operation crosses a signed,
certificate-verified HTTPS connection to the independent receiver.
"""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import ssl
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Literal

from .auth import require_user, minimum_role
from .db import db, record_audit, utcnow
from .settings import data_dir, seed_demo_enabled, PROJECT_ROOT

router = APIRouter(tags=["NotaryDesk Demo"])
_servers = {}
_lock = threading.Lock()


def secret_file(path, value):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_bytes()
    with os.fdopen(fd, "wb") as output:
        output.write(value)
    return value


def certificates(root):
    cert_path, key_path = root / "localhost.crt", root / "localhost.key"
    if cert_path.exists() and key_path.exists():
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        if cert.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=1):
            return cert_path, key_path
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "LexFlow NotaryDesk Demo")])
    now = datetime.now(timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(key, hashes.SHA256()))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    os.chmod(key_path, 0o600)
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


class Destination(ThreadingHTTPServer):
    daemon_threads = True


class Receiver(BaseHTTPRequestHandler):
    server_version = "NotaryDeskDemo"
    sys_version = ""

    def log_message(self, *args):
        pass  # Do not log payloads, signatures, names or identifiers.

    def reply(self, status, payload):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self.server.signing_secret, raw, hashlib.sha256).hexdigest()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-LexFlow-Receipt-Signature", "sha256=" + signature)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024 * 1024:
                self.reply(413, {"detail": "Request size is not supported"})
                return
            raw = self.rfile.read(size)
            stamp = self.headers.get("X-LexFlow-Timestamp", "")
            signature = "sha256=" + hmac.new(self.server.signing_secret, stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
            if (not stamp.isdigit() or abs(int(time.time()) - int(stamp)) > 300
                    or not hmac.compare_digest(signature, self.headers.get("X-LexFlow-Signature", ""))):
                self.reply(401, {"detail": "Destination authentication failed"})
                return
            data = json.loads(raw)
            workspace = data.get("workspace_id", "")
            if not isinstance(workspace, str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,64}", workspace):
                raise ValueError
            with closing(sqlite3.connect(self.server.database, timeout=10)) as conn:
                conn.row_factory = sqlite3.Row
                if self.path == "/imports":
                    self.import_case(conn, data, raw, workspace)
                elif self.path == "/query" and data.get("action") == "read":
                    query = "SELECT * FROM cases WHERE workspace_id=?"
                    args = [workspace]
                    if data.get("case_id"):
                        query += " AND id=?"
                        args.append(data["case_id"])
                    rows = conn.execute(query + " ORDER BY received_at DESC,rowid DESC LIMIT 100", args).fetchall()
                    self.reply(200, {"cases": [self.case(row) for row in rows], "demo": True})
                elif self.path == "/stage" and data.get("action") == "stage":
                    self.change_stage(conn, data, workspace)
                else:
                    self.reply(404, {"detail": "Destination operation not found"})
        except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError):
            self.reply(422, {"detail": "Invalid destination request"})
        except Exception:
            self.reply(503, {"detail": "The demo destination could not complete the request"})

    def import_case(self, conn, payload, raw, workspace):
        key = self.headers.get("Idempotency-Key", "")
        if (not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", key)
                or payload.get("specification") != "lexflow-approved-transfer-v1"
                or payload.get("connector") != "demo_notary" or not payload.get("simulated")
                or not payload.get("matter", {}).get("approved_at") or not payload.get("fields")):
            raise ValueError
        digest = hashlib.sha256(raw).hexdigest()
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute("SELECT * FROM cases WHERE workspace_id=? AND idempotency_key=?", (workspace, key)).fetchone()
        if previous:
            if previous["payload_sha256"] != digest:
                self.reply(409, {"detail": "Transfer key is already bound to different data"})
            else:
                self.reply(200, previous["receipt_json"].encode())
            return
        case_id = "nd-" + uuid.uuid4().hex
        receipt = {"accepted": True, "receipt_id": "NOTARY-DEMO-" + uuid.uuid4().hex[:16].upper(),
                   "idempotency_key": key, "payload_sha256": digest, "case_id": case_id, "demo": True}
        receipt_json = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        encrypted = self.server.cipher.encrypt(json.dumps(payload, ensure_ascii=False).encode())
        conn.execute("INSERT INTO cases VALUES(?,?,?,?,?,?,?,'received',1,?)", (case_id, workspace, key, digest, encrypted, receipt_json, payload.get("source_matter_id", ""), utcnow()))
        conn.execute("INSERT INTO history VALUES(?,?,?,?,?)", (uuid.uuid4().hex, case_id, "received", "LexFlow approved handoff", utcnow()))
        conn.commit()  # Acknowledge only after the independent destination commits.
        self.reply(200, receipt_json.encode())

    def case(self, row):
        payload = json.loads(self.server.cipher.decrypt(row["payload_ciphertext"]))
        if payload.get("workspace_id") != row["workspace_id"]:
            raise ValueError
        receipt = json.loads(row["receipt_json"])
        return {"id": row["id"], "matter": payload["matter"], "fields": payload["fields"],
                "source_matter_id": row["source_matter_id"], "receipt_id": receipt["receipt_id"],
                "payload_sha256": row["payload_sha256"], "stage": row["stage"], "revision": row["revision"], "received_at": row["received_at"], "demo": True}

    def change_stage(self, conn, data, workspace):
        if data.get("stage") not in ("received", "in_preparation", "ready_for_review"):
            raise ValueError
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM cases WHERE workspace_id=? AND id=?", (workspace, data.get("case_id"))).fetchone()
        if not row:
            self.reply(404, {"detail": "Destination case not found"})
            return
        if row["revision"] != data.get("expected_revision"):
            self.reply(409, {"detail": "This destination case changed. Refresh before updating its stage"})
            return
        conn.execute("UPDATE cases SET stage=?,revision=revision+1 WHERE id=?", (data["stage"], row["id"]))
        conn.execute("INSERT INTO history VALUES(?,?,?,?,?)", (uuid.uuid4().hex, row["id"], data["stage"], data.get("actor", "Reviewer"), utcnow()))
        updated = conn.execute("SELECT * FROM cases WHERE id=?", (row["id"],)).fetchone()
        conn.commit()
        self.reply(200, {"case": self.case(updated), "demo": True})


def start():
    if not seed_demo_enabled() or os.getenv("LEXFLOW_DEMO_NOTARY", "1") != "1":
        return None
    root = data_dir() / "demo_notary"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    signing = secret_file(root / ".signing-key", secrets.token_urlsafe(48).encode())
    storage = secret_file(root / ".storage-key", Fernet.generate_key())
    cert_path, key_path = certificates(root)
    database = root / "cases.sqlite3"
    with closing(sqlite3.connect(database)) as conn:
        conn.executescript("""PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,idempotency_key TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,payload_ciphertext BLOB NOT NULL,receipt_json TEXT NOT NULL,
                source_matter_id TEXT NOT NULL,stage TEXT NOT NULL,revision INTEGER NOT NULL,received_at TEXT NOT NULL,
                UNIQUE(workspace_id,idempotency_key));
            CREATE TABLE IF NOT EXISTS history(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,stage TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL);""")
    os.chmod(database, 0o600)
    server = Destination(("127.0.0.1", 0), Receiver)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.signing_secret, server.cipher, server.database = signing, Fernet(storage), database
    info = {"url": f"https://127.0.0.1:{server.server_port}/imports", "secret": signing.decode(), "ca_file": str(cert_path),
            "require_signed_receipt": True, "identity": "notarydesk-demo:" + hashlib.sha256(cert_path.read_bytes()).hexdigest()}
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="notarydesk-demo")
    thread.start()
    with _lock:
        _servers[str(data_dir())] = info
    return server, thread, str(data_dir())


def stop(handle):
    if handle:
        server, thread, root = handle
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        with _lock:
            _servers.pop(root, None)


def target(tenant):
    with _lock:
        return _servers.get(str(data_dir()))


def destination_request(user, operation, payload):
    configured = target(user["tenant_id"])
    if not configured:
        raise HTTPException(404, "The demo notary workspace is not enabled")
    body = json.dumps(payload | {"workspace_id": user["tenant_id"]}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    stamp = str(int(time.time()))
    signature = "sha256=" + hmac.new(configured["secret"].encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    try:
        context = ssl.create_default_context(cafile=configured["ca_file"])
        with httpx.Client(verify=context, timeout=5, trust_env=False) as client:
            response = client.post(configured["url"].rsplit("/", 1)[0] + operation, content=body, headers={"Content-Type": "application/json", "X-LexFlow-Timestamp": stamp, "X-LexFlow-Signature": signature})
        expected = "sha256=" + hmac.new(configured["secret"].encode(), response.content, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, response.headers.get("X-LexFlow-Receipt-Signature", "")):
            raise ValueError
        if response.status_code >= 400:
            raise HTTPException(response.status_code, response.json().get("detail", "Destination rejected this operation"))
        return response.json()
    except (httpx.HTTPError, ValueError, OSError) as exc:
        raise HTTPException(503, "The demo notary destination is unavailable or its response could not be authenticated") from exc


@router.get("/demo-notary", response_class=HTMLResponse, include_in_schema=False)
def page(user=Depends(require_user)):
    if not target(user["tenant_id"]):
        raise HTTPException(404, "The demo notary workspace is not enabled")
    return (PROJECT_ROOT / "static" / "notary.html").read_text()


@router.get("/api/demo-notary/cases")
def cases(user=Depends(require_user)):
    return destination_request(user, "/query", {"action": "read"})


class Stage(BaseModel):
    stage: Literal["received", "in_preparation", "ready_for_review"]
    expected_revision: int = Field(ge=1)


@router.post("/api/demo-notary/cases/{case_id}/stage")
def stage(case_id: str, data: Stage, user=Depends(minimum_role("reviewer"))):
    result = destination_request(user, "/stage", {"action": "stage", "case_id": case_id, "stage": data.stage, "expected_revision": data.expected_revision, "actor": user["name"]})
    with db(write=True) as conn:
        record_audit(conn, user["tenant_id"], result["case"]["source_matter_id"] or None, user["id"], "demo_notary_stage_updated", {"case_id": case_id, "stage": data.stage, "simulated": True})
    return result
