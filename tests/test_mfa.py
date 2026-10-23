import base64
import hashlib
import json
import time

import pytest
from fastapi import HTTPException

from lexflow import mfa
from lexflow.db import db
from lexflow.seed import DEMO_PASSWORD
from tests.conftest import sign_in


def enable(client):
    setup = client.post("/api/auth/mfa/enroll", json={"password": DEMO_PASSWORD})
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    result = client.post("/api/auth/mfa/confirm", json={"code": mfa.totp(secret, int(mfa.clock()) // 30)})
    assert result.status_code == 200, result.text
    return secret, result.json()["recovery_codes"]


def challenge(client):
    result = client.post("/api/auth/login", json={"email": "admin@keller.demo", "password": DEMO_PASSWORD})
    assert result.status_code == 200 and result.json()["mfa_required"] is True
    assert "csrf" not in result.json() and "user" not in result.json()
    return result.json()["challenge"]


def test_rfc_6238_published_test_vectors():
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    for timestamp, expected in [(59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"), (1234567890, "89005924"), (2000000000, "69279037"), (20000000000, "65353130")]:
        assert mfa.totp(secret, timestamp // 30, digits=8) == expected


def test_enrollment_encrypts_secret_and_requires_confirmation_and_password(admin):
    assert admin.post("/api/auth/mfa/enroll", json={"password": "wrong"}).status_code == 401
    setup = admin.post("/api/auth/mfa/enroll", json={"password": DEMO_PASSWORD}).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/LexFlow")
    assert admin.get("/api/auth/mfa/status").json()["enabled"] is False
    with db() as conn:
        row = conn.execute("SELECT * FROM mfa_credentials").fetchone()
        assert setup["secret"] not in row["secret_ciphertext"]
        with pytest.raises(HTTPException):
            mfa.decrypt_secret("another-user", row["secret_ciphertext"])
    assert admin.post("/api/auth/mfa/confirm", json={"code": "wrong-code"}).status_code == 400
    result = admin.post("/api/auth/mfa/confirm", json={"code": mfa.totp(setup["secret"], int(time.time()) // 30)})
    assert result.status_code == 200 and len(result.json()["recovery_codes"]) == 10
    status = admin.get("/api/auth/mfa/status").json()
    assert status["enabled"] is True and status["recovery_codes_remaining"] == 10
    assert admin.get("/api/dashboard").status_code == 200
    audit = admin.get("/api/audit").text
    assert setup["secret"] not in audit and result.json()["recovery_codes"][0] not in audit


def test_password_alone_never_issues_a_session_and_recovery_is_single_use(admin):
    _, codes = enable(admin)
    token = challenge(admin)
    assert admin.get("/api/dashboard").status_code == 401
    verified = admin.post("/api/auth/mfa/verify", json={"challenge": token, "code": codes[0]})
    assert verified.status_code == 200
    assert verified.json()["user"]["mfa_enabled"] is True
    admin.headers["X-CSRF-Token"] = verified.json()["csrf"]
    assert admin.get("/api/dashboard").status_code == 200
    assert admin.get("/api/auth/mfa/status").json()["recovery_codes_remaining"] == 9
    token2 = challenge(admin)
    assert admin.post("/api/auth/mfa/verify", json={"challenge": token2, "code": codes[0]}).status_code == 401
    with db() as conn:
        assert conn.execute("SELECT attempts FROM mfa_challenges").fetchone()[0] == 1


def test_totp_replay_and_clock_window(admin, monkeypatch):
    stamp = [1800000000]
    monkeypatch.setattr(mfa, "clock", lambda: stamp[0])
    secret, codes = enable(admin)
    token = challenge(admin)
    used = mfa.totp(secret, stamp[0] // 30)
    assert admin.post("/api/auth/mfa/verify", json={"challenge": token, "code": used}).status_code == 401
    stamp[0] += 30
    new = mfa.totp(secret, stamp[0] // 30)
    result = admin.post("/api/auth/mfa/verify", json={"challenge": token, "code": new})
    assert result.status_code == 200
    next_challenge = challenge(admin)
    assert admin.post("/api/auth/mfa/verify", json={"challenge": next_challenge, "code": new}).status_code == 401
    assert admin.post("/api/auth/mfa/verify", json={"challenge": next_challenge, "code": codes[1]}).status_code == 200


def test_expired_setup_challenge_and_attempt_limit(admin):
    secret, _ = enable(admin)
    token = challenge(admin)
    for _ in range(5):
        assert admin.post("/api/auth/mfa/verify", json={"challenge": token, "code": "not-a-code"}).status_code == 401
    with db() as conn:
        assert conn.execute("SELECT attempts FROM mfa_challenges").fetchone()[0] == 5
    assert admin.post("/api/auth/mfa/verify", json={"challenge": token, "code": mfa.totp(secret, int(time.time()) // 30 + 1)}).status_code == 401
    with db(write=True) as conn:
        conn.execute("UPDATE mfa_challenges SET expires_at=0")
    assert admin.post("/api/auth/mfa/verify", json={"challenge": token, "code": "not-a-code"}).status_code == 401


def test_enrollment_revokes_old_sessions_and_password_reset_preserves_mfa(admin):
    old = admin.cookies.get("lexflow_session")
    sign_in(admin)
    _, codes = enable(admin)
    assert admin.get("/api/auth/me", headers={"Cookie": "lexflow_session=" + old}).status_code == 401
    pending = challenge(admin)
    reset = admin.post("/api/auth/forgot-password", json={"email": "admin@keller.demo"}).json()["demo_reset_path"].split("token=")[1]
    response = admin.post("/api/auth/reset-password", json={"token": reset, "new_password": "Replacement-password!", "confirm_password": "Replacement-password!"})
    assert response.status_code == 200
    assert admin.post("/api/auth/mfa/verify", json={"challenge": pending, "code": codes[0]}).status_code == 401
    result = admin.post("/api/auth/login", json={"email": "admin@keller.demo", "password": "Replacement-password!"})
    assert result.json()["mfa_required"] is True


def test_factor_changes_require_both_proofs_and_required_policy_cannot_be_disabled(admin, monkeypatch):
    _, codes = enable(admin)
    assert admin.post("/api/auth/mfa/disable", json={"password": "wrong", "code": codes[0]}).status_code == 401
    rotated = admin.post("/api/auth/mfa/recovery-codes", json={"password": DEMO_PASSWORD, "code": codes[0]})
    assert rotated.status_code == 200
    new_codes = rotated.json()["recovery_codes"]
    assert len(new_codes) == 10 and set(new_codes).isdisjoint(codes)
    monkeypatch.setenv("LEXFLOW_REQUIRE_MFA", "1")
    assert admin.post("/api/auth/mfa/disable", json={"password": DEMO_PASSWORD, "code": new_codes[0]}).status_code == 409
    monkeypatch.setenv("LEXFLOW_REQUIRE_MFA", "0")
    assert admin.post("/api/auth/mfa/disable", json={"password": DEMO_PASSWORD, "code": new_codes[0]}).status_code == 200
    assert admin.get("/api/auth/mfa/status").json()["enabled"] is False


def test_policy_enforces_setup_before_workspace_access(admin, monkeypatch):
    monkeypatch.setenv("LEXFLOW_REQUIRE_MFA", "1")
    assert admin.get("/api/auth/me").status_code == 200
    assert admin.get("/api/auth/mfa/status").status_code == 200
    assert admin.get("/api/dashboard").status_code == 403
    assert admin.get("/api/settings/users").status_code == 403
    enable(admin)
    assert admin.get("/api/dashboard").status_code == 200


def test_challenge_and_codes_are_not_echoed_by_validation(admin):
    _, codes = enable(admin)
    token = challenge(admin)
    result = admin.post("/api/auth/mfa/verify", json={"challenge": token, "code": codes[0] * 10})
    assert result.status_code == 422
    assert token not in result.text and codes[0] not in result.text
