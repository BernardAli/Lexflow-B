"""Authenticator-app MFA with encrypted secrets, replay protection and recovery codes.

TOTP follows RFC 6238 (SHA-1, 30-second steps, six digits). Enrollment and
factor changes require password reauthentication. Login challenges never grant
a session until an unused factor is verified.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import time
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .auth import require_user, verify_password, create_session
from .db import db, record_audit, utcnow
from .settings import data_dir, secure_cookies

router = APIRouter(prefix="/api/auth/mfa", tags=["Two-factor authentication"])


def clock():
    return time.time()


def required():
    return os.getenv("LEXFLOW_REQUIRE_MFA", "1" if os.getenv("LEXFLOW_SECURITY_PROFILE") == "hardened" else "0") == "1"


def cipher():
    configured = os.getenv("LEXFLOW_MFA_KEY")
    if configured:
        try:
            return Fernet(configured.encode())
        except (ValueError, TypeError) as exc:
            raise HTTPException(503, "The MFA encryption key is not valid") from exc
    if os.getenv("LEXFLOW_SECURITY_PROFILE") == "hardened":
        raise HTTPException(503, "Configure an external MFA encryption key")
    path = data_dir() / ".mfa-key"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return Fernet(path.read_bytes())
    key = Fernet.generate_key()
    with os.fdopen(fd, "wb") as output:
        output.write(key)
    return Fernet(key)


def encrypt_secret(user_id, secret):
    return cipher().encrypt(json.dumps({"user_id": user_id, "secret": secret}).encode()).decode()


def decrypt_secret(user_id, encrypted):
    try:
        value = json.loads(cipher().decrypt(encrypted.encode()))
        if value["user_id"] != user_id:
            raise InvalidToken
        return value["secret"]
    except (InvalidToken, ValueError, KeyError) as exc:
        raise HTTPException(503, "The authenticator secret cannot be opened with this key") from exc


def totp(secret, step, digits=6, algorithm="sha1"):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), algorithm).digest()
    offset = digest[-1] & 15
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff
    return str(value % (10 ** digits)).zfill(digits)


def code_hash(user_id, code):
    return hashlib.sha256((user_id + "\0" + re.sub(r"[\s-]", "", code).upper()).encode()).hexdigest()


def limit(user_id, ip, operation):
    now = int(clock())
    window = now // 900 * 900
    # Commit failed attempts independently of the protected operation.
    with db(write=True) as conn:
        conn.execute("DELETE FROM auth_limits WHERE window_start<?", (window,))
        for scope, maximum in ((f"mfa:{operation}:user:{user_id}", 10), (f"mfa:{operation}:ip:{ip}", 50)):
            digest = hashlib.sha256(scope.encode()).hexdigest()
            row = conn.execute("SELECT attempts FROM auth_limits WHERE scope_hash=? AND window_start=?", (digest, window)).fetchone()
            if row and row[0] >= maximum:
                raise HTTPException(429, "Too many authenticator attempts. Try again later.", headers={"Retry-After": str(max(1, window + 900 - now))})
            conn.execute("INSERT INTO auth_limits VALUES(?,?,1) ON CONFLICT(scope_hash,window_start) DO UPDATE SET attempts=attempts+1", (digest, window))


def peer(request):
    return request.client.host if request.client else "unknown"


def challenge(conn, user_id):
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM mfa_challenges WHERE user_id=? OR expires_at<=?", (user_id, int(clock())))
    conn.execute("INSERT INTO mfa_challenges VALUES(?,?,?,0)", (hashlib.sha256(token.encode()).hexdigest(), user_id, int(clock()) + 300))
    return {"mfa_required": True, "challenge": token, "expires_in_seconds": 300}


def consume_factor(conn, credential, code, allow_recovery=True):
    normalized = re.sub(r"[\s-]", "", code)
    if re.fullmatch(r"\d{6}", normalized):
        secret = decrypt_secret(credential["user_id"], credential["secret_ciphertext"])
        current = int(clock()) // 30
        for step in (current, current - 1, current + 1):
            if step > credential["last_step"] and hmac.compare_digest(totp(secret, step), normalized):
                conn.execute("UPDATE mfa_credentials SET last_step=? WHERE user_id=?", (step, credential["user_id"]))
                return "authenticator"
    if allow_recovery and re.fullmatch(r"[A-Fa-f0-9]{20}", normalized):
        deleted = conn.execute("DELETE FROM mfa_recovery_codes WHERE user_id=? AND code_hash=?", (credential["user_id"], code_hash(credential["user_id"], normalized)))
        if deleted.rowcount:
            return "recovery_code"
    return None


def new_recovery_codes(conn, user_id):
    codes = [secrets.token_hex(10).upper() for _ in range(10)]
    conn.execute("DELETE FROM mfa_recovery_codes WHERE user_id=?", (user_id,))
    conn.executemany("INSERT INTO mfa_recovery_codes VALUES(?,?)", [(user_id, code_hash(user_id, code)) for code in codes])
    return ["-".join(code[i:i + 5] for i in range(0, 20, 5)) for code in codes]


class PasswordProof(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class CodeProof(BaseModel):
    code: str = Field(min_length=6, max_length=40)


class LoginProof(CodeProof):
    challenge: str = Field(min_length=20, max_length=100)


class FactorChange(PasswordProof, CodeProof):
    pass


def check_password(conn, user_id, password):
    row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
    return bool(row and verify_password(row[0], password))


@router.get("/status")
def status(user=Depends(require_user)):
    with db() as conn:
        row = conn.execute("SELECT enabled,setup_expires FROM mfa_credentials WHERE user_id=?", (user["id"],)).fetchone()
        remaining = conn.execute("SELECT COUNT(*) FROM mfa_recovery_codes WHERE user_id=?", (user["id"],)).fetchone()[0]
    return {"enabled": bool(row and row["enabled"]), "required": required(), "recovery_codes_remaining": remaining,
            "enrollment_pending": bool(row and not row["enabled"] and row["setup_expires"] > int(clock()))}


@router.post("/enroll")
def enroll(data: PasswordProof, request: Request, user=Depends(require_user)):
    limit(user["id"], peer(request), "enroll")
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    with db(write=True) as conn:
        if not check_password(conn, user["id"], data.password):
            raise HTTPException(401, "Password verification failed")
        if conn.execute("SELECT 1 FROM mfa_credentials WHERE user_id=? AND enabled=1", (user["id"],)).fetchone():
            raise HTTPException(409, "Two-factor authentication is already enabled")
        conn.execute("INSERT INTO mfa_credentials VALUES(?,?,0,?,-1,?) ON CONFLICT(user_id) DO UPDATE SET secret_ciphertext=excluded.secret_ciphertext,setup_expires=excluded.setup_expires,last_step=-1", (user["id"], encrypt_secret(user["id"], secret), int(clock()) + 600, utcnow()))
    label = quote("LexFlow:" + user["email"], safe="")
    uri = "otpauth://totp/" + label + "?" + urlencode({"secret": secret, "issuer": "LexFlow", "algorithm": "SHA1", "digits": 6, "period": 30})
    return {"secret": secret, "otpauth_uri": uri, "expires_in_seconds": 600}


@router.post("/confirm")
def confirm(data: CodeProof, request: Request, user=Depends(require_user)):
    limit(user["id"], peer(request), "confirm")
    with db(write=True) as conn:
        credential = conn.execute("SELECT * FROM mfa_credentials WHERE user_id=? AND enabled=0 AND setup_expires>?", (user["id"], int(clock()))).fetchone()
        if not credential or not consume_factor(conn, credential, data.code, allow_recovery=False):
            raise HTTPException(400, "The code is invalid, already used, or setup expired")
        conn.execute("UPDATE mfa_credentials SET enabled=1 WHERE user_id=?", (user["id"],))
        codes = new_recovery_codes(conn, user["id"])
        conn.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], user["session_hash"]))
        conn.execute("INSERT OR REPLACE INTO session_mfa VALUES(?,?)", (user["session_hash"], utcnow()))
        conn.execute("DELETE FROM mfa_challenges WHERE user_id=?", (user["id"],))
        record_audit(conn, user["tenant_id"], None, user["id"], "mfa_enabled", {"factor": "authenticator"})
    return {"enabled": True, "recovery_codes": codes, "message": "Save these recovery codes. They are shown once and each works once."}


@router.post("/verify")
def verify(data: LoginProof, request: Request, response: Response):
    digest = hashlib.sha256(data.challenge.encode()).hexdigest()
    with db() as conn:
        row = conn.execute("SELECT user_id FROM mfa_challenges WHERE token_hash=?", (digest,)).fetchone()
    limit(row[0] if row else "unknown", peer(request), "login")
    result = None
    with db(write=True) as conn:
        row = conn.execute("SELECT * FROM mfa_challenges WHERE token_hash=? AND expires_at>? AND attempts<5", (digest, int(clock()))).fetchone()
        if row:
            conn.execute("UPDATE mfa_challenges SET attempts=attempts+1 WHERE token_hash=?", (digest,))
            credential = conn.execute("SELECT * FROM mfa_credentials WHERE user_id=? AND enabled=1", (row["user_id"],)).fetchone()
            factor = consume_factor(conn, credential, data.code) if credential else None
            if factor:
                user = conn.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
                token, csrf, public = create_session(conn, user, mfa_verified=True)
                conn.execute("DELETE FROM mfa_challenges WHERE user_id=?", (row["user_id"],))
                record_audit(conn, user["tenant_id"], None, user["id"], "mfa_sign_in", {"factor": factor})
                result = (token, csrf, public)
    # Raising outside the transaction preserves the failed-attempt counter.
    if result is None:
        raise HTTPException(401, "The code is invalid, already used, or the sign-in request expired")
    token, csrf, public = result
    from .auth import COOKIE_NAME
    response.set_cookie(COOKIE_NAME, token, max_age=12 * 3600, httponly=True, samesite="strict", secure=secure_cookies(), path="/")
    return {"user": public, "csrf": csrf}


def change_factor(data, request, user, disable):
    limit(user["id"], peer(request), "change")
    if disable and required():
        raise HTTPException(409, "Workspace policy requires two-factor authentication")
    with db(write=True) as conn:
        credential = conn.execute("SELECT * FROM mfa_credentials WHERE user_id=? AND enabled=1", (user["id"],)).fetchone()
        if not check_password(conn, user["id"], data.password) or not credential or not consume_factor(conn, credential, data.code):
            raise HTTPException(401, "Password or authenticator verification failed")
        codes = [] if disable else new_recovery_codes(conn, user["id"])
        if disable:
            conn.execute("DELETE FROM mfa_credentials WHERE user_id=?", (user["id"],))
            conn.execute("DELETE FROM mfa_recovery_codes WHERE user_id=?", (user["id"],))
        conn.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], user["session_hash"]))
        conn.execute("DELETE FROM mfa_challenges WHERE user_id=?", (user["id"],))
        record_audit(conn, user["tenant_id"], None, user["id"], "mfa_disabled" if disable else "mfa_recovery_rotated", {})
    return {"enabled": not disable, "recovery_codes": codes}


@router.post("/recovery-codes")
def rotate_codes(data: FactorChange, request: Request, user=Depends(require_user)):
    return change_factor(data, request, user, False)


@router.post("/disable")
def disable(data: FactorChange, request: Request, user=Depends(require_user)):
    return change_factor(data, request, user, True)
