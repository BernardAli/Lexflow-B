"""Optional per-workspace authenticated encryption for binary artifacts."""
import json
import os
import base64
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from fastapi import HTTPException

MAGIC = b"LEXFLOW-ENC-1\n"


def keyring(tenant):
    keys = json.loads(os.getenv("LEXFLOW_STORAGE_KEYS") or "{}")
    configured = keys.get(tenant, [])
    if isinstance(configured, str):
        configured = [configured]
    return MultiFernet([Fernet(key.encode()) for key in configured]) if configured else None


def protect(raw, tenant):
    cipher = keyring(tenant)
    if not cipher:
        return raw
    envelope = json.dumps({"tenant_id": tenant, "data": base64.b64encode(raw).decode()}).encode()
    return MAGIC + cipher.encrypt(envelope)


def reveal(raw, tenant, *, allow_legacy=False):
    if not raw.startswith(MAGIC):
        if not allow_legacy and os.getenv("LEXFLOW_SECURITY_PROFILE") == "hardened":
            raise HTTPException(503, "Legacy plaintext artifact must be encrypted before hardened access")
        return raw
    cipher = keyring(tenant)
    if not cipher:
        raise HTTPException(503, "The workspace storage key is unavailable")
    try:
        envelope = json.loads(cipher.decrypt(raw[len(MAGIC):]))
        if envelope["tenant_id"] != tenant:
            raise InvalidToken
        return base64.b64decode(envelope["data"], validate=True)
    except (InvalidToken, ValueError, KeyError):
        raise HTTPException(503, "Stored artifact could not be authenticated") from None
