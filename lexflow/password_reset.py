"""Single-use password recovery, with explicit demo delivery or configured SMTP."""
import hashlib
import logging
import os
import secrets
import smtplib
import ssl
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import urlsplit

from fastapi import HTTPException

from .auth import hash_password, validate_password
from .db import db, record_audit, utcnow
from .settings import seed_demo_enabled

RESET_MINUTES = 30
RESET_MESSAGE = "If the account is eligible, password reset instructions will be available shortly."
# Only these publicly documented, synthetic identities can expose a link in demo mode.
DEMO_IDENTITIES = {
    ("usr-keller-admin", "tenant-keller-demo", "admin@keller.demo"),
    ("usr-keller-reviewer", "tenant-keller-demo", "reviewer@keller.demo"),
    ("usr-keller-analyst", "tenant-keller-demo", "assistant@keller.demo"),
    ("usr-weber-admin", "tenant-weber-demo", "admin@weber.demo"),
}
logger = logging.getLogger(__name__)


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def rate_limit(scopes):
    """Persist bounded fixed-window counters; do not trust forwarded IP headers."""
    window = int(time.time()) // 900 * 900
    with db(write=True) as conn:
        conn.execute("DELETE FROM password_reset_limits WHERE window_start<?", (window,))
        for scope, limit in scopes:
            digest = token_hash(scope)
            count = conn.execute(
                "SELECT attempts FROM password_reset_limits WHERE scope_hash=? AND window_start=?",
                (digest, window),
            ).fetchone()
            if count and count["attempts"] >= limit:
                raise HTTPException(429, "Too many password reset attempts. Try again in 15 minutes.",
                                    headers={"Retry-After": str(window + 900 - int(time.time()))})
            conn.execute("""INSERT INTO password_reset_limits VALUES(?,?,1)
                            ON CONFLICT(scope_hash,window_start) DO UPDATE SET attempts=attempts+1""",
                         (digest, window))


def delivery_settings():
    mode = os.getenv("LEXFLOW_RESET_DELIVERY", "demo" if seed_demo_enabled() else "disabled")
    if mode == "demo" and seed_demo_enabled():
        return {"mode": "demo"}
    if mode == "smtp":
        base = os.getenv("LEXFLOW_PUBLIC_URL", "").rstrip("/")
        try:
            parsed = urlsplit(base)
            valid_origin = bool(parsed.hostname) and parsed.port != 0
        except ValueError:
            parsed = urlsplit("")
            valid_origin = False
        host = os.getenv("LEXFLOW_SMTP_HOST", "")
        sender = os.getenv("LEXFLOW_SMTP_FROM", "")
        security = os.getenv("LEXFLOW_SMTP_SECURITY", "starttls")
        try:
            port = int(os.getenv("LEXFLOW_SMTP_PORT", "465" if security == "tls" else "587"))
        except ValueError:
            port = 0
        if (parsed.scheme == "https" and valid_origin and not parsed.username and not parsed.password
                and parsed.path in ("", "/") and not parsed.query and not parsed.fragment
                and host and "@" in sender and "\n" not in sender and "\r" not in sender
                and security in ("tls", "starttls") and 0 < port < 65536):
            return {"mode": "smtp", "base": base, "host": host, "port": port, "sender": sender,
                    "security": security, "username": os.getenv("LEXFLOW_SMTP_USERNAME", ""),
                    "password": os.getenv("LEXFLOW_SMTP_PASSWORD", "")}
    raise HTTPException(503, "Password reset delivery is not configured. Contact your workspace administrator.")


def send_reset_email(settings, recipient, token):
    """Background delivery; never log the token, recipient or SMTP error contents."""
    message = EmailMessage()
    message["Subject"] = "Reset your LexFlow password"
    message["From"] = settings["sender"]
    message["To"] = recipient
    link = settings["base"] + "/#/reset-password?token=" + token
    message.set_content(
        f"A password reset was requested for your LexFlow account.\n\n"
        f"Create a new password: {link}\n\n"
        f"This link expires in {RESET_MINUTES} minutes and can be used once. "
        "A newer request replaces this link. If you did not request this, ignore this email.\n"
    )
    try:
        transport = smtplib.SMTP_SSL if settings["security"] == "tls" else smtplib.SMTP
        kwargs = {"timeout": 15}
        if settings["security"] == "tls":
            kwargs["context"] = ssl.create_default_context()
        with transport(settings["host"], settings["port"], **kwargs) as server:
            if settings["security"] == "starttls":
                server.starttls(context=ssl.create_default_context())
            if settings["username"]:
                server.login(settings["username"], settings["password"])
            server.send_message(message)
    except Exception:
        with db(write=True) as conn:
            conn.execute("DELETE FROM password_resets WHERE token_hash=?", (token_hash(token),))
        logger.error("Password reset email delivery failed; check SMTP configuration and connectivity.")


def request_reset(email, client_ip, background_tasks):
    email = email.strip().lower()
    rate_limit([(f"request:ip:{client_ip}", 20), (f"request:email:{email}", 5)])
    settings = delivery_settings()
    result = {"message": RESET_MESSAGE, "delivery": settings["mode"]}
    token = secrets.token_urlsafe(40)
    with db(write=True) as conn:
        conn.execute("DELETE FROM password_resets WHERE expires_at<=?", (utcnow(),))
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not user:
            return result
        if settings["mode"] == "demo" and (user["id"], user["tenant_id"], email) not in DEMO_IDENTITIES:
            return result
        conn.execute("DELETE FROM password_resets WHERE user_id=?", (user["id"],))
        expires = (datetime.now(timezone.utc) + timedelta(minutes=RESET_MINUTES)).isoformat(timespec="seconds")
        conn.execute("INSERT INTO password_resets VALUES(?,?,?,?)", (token_hash(token), user["id"], expires, utcnow()))
        record_audit(conn, user["tenant_id"], None, None, "password_reset_requested",
                     {"user_id": user["id"], "delivery": settings["mode"]})
    if settings["mode"] == "demo":
        result.update(demo_reset_path="/#/reset-password?token=" + token, expires_in_minutes=RESET_MINUTES)
    else:
        background_tasks.add_task(send_reset_email, settings, email, token)
    return result


def complete_reset(token, new_password, confirm_password, client_ip):
    rate_limit([(f"complete:ip:{client_ip}", 30)])
    validate_password(new_password)
    if new_password != confirm_password:
        raise HTTPException(422, "Passwords do not match")
    with db(write=True) as conn:
        reset = conn.execute("""SELECT r.user_id,u.tenant_id FROM password_resets r
                                JOIN users u ON u.id=r.user_id
                                WHERE r.token_hash=? AND r.expires_at>?""",
                             (token_hash(token), utcnow())).fetchone()
        if not reset:
            raise HTTPException(400, "This reset link is invalid or has expired. Request a new link.")
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_password), reset["user_id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=?", (reset["user_id"],))
        conn.execute("DELETE FROM mfa_challenges WHERE user_id=?", (reset["user_id"],))
        conn.execute("DELETE FROM password_resets WHERE user_id=?", (reset["user_id"],))
        record_audit(conn, reset["tenant_id"], None, None, "password_reset_completed",
                     {"user_id": reset["user_id"], "all_sessions_revoked": True})
