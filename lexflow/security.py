"""Deployment checks, login throttling and authenticated security controls."""
import hashlib
import json
import os
import time
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from .auth import require_user
from .db import db, record_audit, utcnow
from .integrity import verify_integrity
from .settings import seed_demo_enabled, secure_cookies
from .storage import keyring

router = APIRouter(prefix="/api/security", tags=["Security"])


def hardened():
    return os.getenv("LEXFLOW_SECURITY_PROFILE", "demo") == "hardened"


def allowed_hosts():
    return [host.strip().lower() for host in os.getenv("LEXFLOW_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if host.strip()]


def validate_deployment():
    if os.getenv("LEXFLOW_SECURITY_PROFILE", "demo") not in ("demo", "hardened"):
        raise RuntimeError("Choose a demo or hardened security profile")
    if not 1 <= int(os.getenv("LEXFLOW_IDLE_MINUTES", "30")) <= 720:
        raise RuntimeError("Session idle timeout must be 1–720 minutes")
    if hardened():
        if os.getenv("LEXFLOW_DEMO_NOTARY") == "1":
            raise RuntimeError("Disable the fictional notary destination in hardened deployments")
        from cryptography.fernet import Fernet
        from .mfa import required
        if not required():
            raise RuntimeError("Hardened profile requires two-factor authentication")
        public = urlsplit(os.getenv("LEXFLOW_PUBLIC_URL", ""))
        if (seed_demo_enabled() or not secure_cookies() or len(os.getenv("LEXFLOW_AUDIT_KEY", "")) < 32
                or not os.getenv("LEXFLOW_STORAGE_KEYS") or not os.getenv("LEXFLOW_ALLOWED_HOSTS")
                or "*" in allowed_hosts() or public.scheme != "https" or not public.hostname
                or public.hostname.lower() not in allowed_hosts()):
            raise RuntimeError("Hardened profile requires demo seeding off, secure cookies, explicit hosts, an HTTPS public URL, a 32+ character external audit key, and workspace storage keys")
        try:
            Fernet(os.getenv("LEXFLOW_MFA_KEY", "").encode())
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Hardened profile requires an external Fernet MFA encryption key") from exc


def login_limit(email, ip):
    window = int(time.time()) // 900 * 900
    with db(write=True) as conn:
        conn.execute("DELETE FROM auth_limits WHERE window_start<?", (window,))
        for text, limit in (("ip:" + ip, 50), ("email:" + email.strip().lower(), 10)):
            scope = hashlib.sha256(text.encode()).hexdigest()
            row = conn.execute("SELECT attempts FROM auth_limits WHERE scope_hash=? AND window_start=?", (scope, window)).fetchone()
            if row and row[0] >= limit:
                raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.",
                                    headers={"Retry-After": str(max(1, window + 900 - int(time.time())))})
            conn.execute("""INSERT INTO auth_limits VALUES(?,?,1) ON CONFLICT(scope_hash,window_start)
                            DO UPDATE SET attempts=attempts+1""", (scope, window))


@router.get("/status")
def status(user=Depends(require_user)):
    from .mfa import required
    with db() as conn:
        sessions = conn.execute("SELECT COUNT(*) FROM sessions WHERE user_id=? AND expires_at>?", (user["id"], utcnow())).fetchone()[0]
        integrity = verify_integrity(conn, user["tenant_id"])
    return {"profile": "hardened" if hardened() else "demo", "secure_cookies": secure_cookies(),
            "storage_encryption": bool(keyring(user["tenant_id"])), "database_encryption": False,
            "login_rate_limiting": True, "idle_timeout_minutes": int(os.getenv("LEXFLOW_IDLE_MINUTES", "30")),
            "active_sessions": sessions, "audit_integrity": integrity,
            "mfa_enabled": user["mfa_enabled"], "mfa_required": required(),
            "isolation": "single-workspace dedicated instance" if hardened() else "logical tenant scoping; deploy a separate instance and volume per workspace for dedicated isolation",
            "limitations": ["SSO is not implemented; authenticator-app MFA is available", "Database metadata and extracted text require an encrypted volume", "Independent security review remains required"]}


@router.post("/sessions/revoke-others")
def revoke_other_sessions(user=Depends(require_user)):
    with db(write=True) as conn:
        count = conn.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], user["session_hash"])).rowcount
        record_audit(conn, user["tenant_id"], None, user["id"], "other_sessions_revoked", {"count": count})
    return {"ok": True, "revoked": count}


@router.get("/audit-checkpoint")
def audit_checkpoint(user=Depends(require_user)):
    with db() as conn:
        return verify_integrity(conn, user["tenant_id"])
