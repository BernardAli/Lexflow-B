"""Role-gated session authentication; same-site HttpOnly cookies + CSRF token."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from .db import db, utcnow

hasher = PasswordHasher(time_cost=2, memory_cost=32768, parallelism=2)
COOKIE_NAME = "lexflow_session"
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def login(email: str, password: str, client_ip="unknown"):
    from .security import login_limit
    login_limit(email, client_ip)
    with db(write=True) as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
        valid = verify_password(user["password_hash"] if user else DUMMY_HASH, password)
        if not user or not valid:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if conn.execute("SELECT 1 FROM mfa_credentials WHERE user_id=? AND enabled=1", (user["id"],)).fetchone():
            from .mfa import challenge
            return challenge(conn, user["id"])
        return create_session(conn, user)


def create_session(conn, user, *, mfa_verified=False):
    token = secrets.token_urlsafe(40)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    csrf = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(timespec="seconds")
    conn.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (token_hash, user["id"], csrf, expires_at, utcnow()))
    conn.execute("INSERT INTO session_activity VALUES(?,?)", (token_hash, utcnow()))
    if mfa_verified:
        conn.execute("INSERT INTO session_mfa VALUES(?,?)", (token_hash, utcnow()))
    return token, csrf, public_user(conn, user)


def public_user(conn, user):
    from .mfa import required
    tenant = conn.execute("SELECT name FROM tenants WHERE id=?", (user["tenant_id"],)).fetchone()
    return {"id": user["id"], "tenant_id": user["tenant_id"], "workspace": tenant["name"],
            "name": user["name"], "email": user["email"], "role": user["role"],
            "mfa_required": required(), "mfa_enabled": bool(conn.execute("SELECT 1 FROM mfa_credentials WHERE user_id=? AND enabled=1", (user["id"],)).fetchone())}


def require_user(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db(write=True) as conn:
        row = conn.execute("""SELECT s.csrf_token, s.expires_at,u.* FROM sessions s
                              JOIN users u ON s.user_id=u.id WHERE s.token_hash=?""", (token_hash,)).fetchone()
        if not row or row["expires_at"] <= utcnow():
            raise HTTPException(status_code=401, detail="Session expired")
        import os
        activity = conn.execute("SELECT last_seen FROM session_activity WHERE token_hash=?", (token_hash,)).fetchone()
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=int(os.getenv("LEXFLOW_IDLE_MINUTES", "30")))).isoformat(timespec="seconds")
        if activity and activity["last_seen"] <= cutoff:
            raise HTTPException(status_code=401, detail="Session expired after inactivity")
        user = public_user(conn, row)
        if user["mfa_enabled"] and not conn.execute("SELECT 1 FROM session_mfa WHERE token_hash=?", (token_hash,)).fetchone():
            raise HTTPException(status_code=401, detail="Sign in again with two-factor authentication")
        enrollment_paths = {"/api/auth/me", "/api/auth/logout", "/api/auth/mfa/status", "/api/auth/mfa/enroll", "/api/auth/mfa/confirm", "/api/config"}
        if user["mfa_required"] and not user["mfa_enabled"] and request.url.path not in enrollment_paths:
            raise HTTPException(status_code=403, detail="Set up two-factor authentication before opening the workspace")
        user["csrf"] = row["csrf_token"]
        user["session_hash"] = token_hash
        if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
            if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), row["csrf_token"]):
                raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")
        conn.execute("INSERT INTO session_activity VALUES(?,?) ON CONFLICT(token_hash) DO UPDATE SET last_seen=excluded.last_seen", (token_hash, utcnow()))
        return user


def minimum_role(required: str):
    ranks = {"analyst": 0, "reviewer": 1, "admin": 2}
    def role_guard(user=Depends(require_user)):
        if ranks.get(user["role"], -1) < ranks[required]:
            raise HTTPException(status_code=403, detail=f"{required} access required")
        return user
    return role_guard


def logout(user):
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (user["session_hash"],))


def validate_password(new_password):
    if len(new_password) < 12:
        raise HTTPException(status_code=422, detail="Password must be at least 12 characters")
    if len(new_password) > 128:
        raise HTTPException(status_code=422, detail="Password must be no more than 128 characters")


def change_password(user, current_password, new_password):
    validate_password(new_password)
    with db(write=True) as conn:
        old = conn.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
        if not verify_password(old["password_hash"], current_password):
            raise HTTPException(status_code=403, detail="Current password incorrect")
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), user["id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], user["session_hash"]))
        conn.execute("DELETE FROM password_resets WHERE user_id=?", (user["id"],))
        conn.execute("DELETE FROM mfa_challenges WHERE user_id=?", (user["id"],))
