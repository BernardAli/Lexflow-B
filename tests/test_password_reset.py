"""Account recovery behavior, delivery boundaries, and credential revocation."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlsplit

import pytest

from lexflow import password_reset
from lexflow.auth import hash_password
from lexflow.db import db, utcnow
from lexflow.seed import DEMO_PASSWORD

NEW_PASSWORD = "A-long-new-password-2026!"


def request_link(client, email="admin@keller.demo"):
    response = client.post("/api/auth/forgot-password", json={"email": email})
    assert response.status_code == 200, response.text
    fragment = urlsplit(response.json()["demo_reset_path"]).fragment
    return parse_qs(fragment.split("?", 1)[1])["token"][0]


def complete(client, token, **overrides):
    payload = {"token": token, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD}
    payload.update(overrides)
    return client.post("/api/auth/reset-password", json=payload)


@pytest.mark.parametrize("email", ["admin@keller.demo", "reviewer@keller.demo", "assistant@keller.demo", "admin@weber.demo"])
def test_demo_accounts_can_reset_without_being_signed_in(api_client, email):
    token = request_link(api_client, "  " + email.upper() + "  ")
    with db() as conn:
        row = conn.execute("SELECT * FROM password_resets").fetchone()
        assert row["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
        assert token not in str(dict(row))
        minutes = (datetime.fromisoformat(row["expires_at"]) - datetime.now(timezone.utc)).total_seconds() / 60
        assert 29 < minutes <= 30
    response = complete(api_client, token)
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["referrer-policy"] == "no-referrer"
    assert api_client.get("/api/auth/me").status_code == 401
    assert api_client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD}).status_code == 401
    assert api_client.post("/api/auth/login", json={"email": email, "password": NEW_PASSWORD}).status_code == 200
    assert complete(api_client, token).status_code == 400
    with db() as conn:
        assert not conn.execute("SELECT 1 FROM password_resets").fetchone()
        events = conn.execute("SELECT * FROM audit WHERE action LIKE 'password_reset_%'").fetchall()
        assert [row["action"] for row in events] == ["password_reset_requested", "password_reset_completed"]
        assert all(token not in row["details_json"] and NEW_PASSWORD not in row["details_json"] for row in events)


def test_reset_revokes_all_target_sessions_and_preserves_other_accounts(api_client):
    sessions = []
    for email in ["admin@keller.demo", "admin@keller.demo", "reviewer@keller.demo", "admin@weber.demo"]:
        response = api_client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        sessions.append(api_client.cookies.get("lexflow_session"))
        assert response.status_code == 200
    token = request_link(api_client)
    assert complete(api_client, token).status_code == 200
    for index, session in enumerate(sessions):
        response = api_client.get("/api/auth/me", headers={"Cookie": f"lexflow_session={session}"})
        assert response.status_code == (401 if index < 2 else 200)


def test_expired_link_and_newer_requests_cannot_be_replayed(api_client):
    expired = request_link(api_client)
    with db(write=True) as conn:
        conn.execute("UPDATE password_resets SET expires_at=?", ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),))
    assert complete(api_client, expired).status_code == 400
    previous = request_link(api_client)
    current = request_link(api_client)
    assert previous != current
    assert complete(api_client, previous).status_code == 400
    assert complete(api_client, current).status_code == 200


@pytest.mark.parametrize("overrides", [
    {"new_password": "too-short", "confirm_password": "too-short"},
    {"new_password": "x" * 129, "confirm_password": "x" * 129},
    {"confirm_password": "A-different-password!"},
])
def test_invalid_passwords_do_not_consume_link_or_echo_secrets(api_client, overrides):
    token = request_link(api_client)
    response = complete(api_client, token, **overrides)
    assert response.status_code == 422
    assert token not in response.text
    assert all(value not in response.text for value in overrides.values())
    assert complete(api_client, token).status_code == 200


def test_invalid_tokens_have_the_same_error_and_do_not_change_password(api_client):
    token = request_link(api_client)
    errors = [complete(api_client, bad) for bad in ["unknown", token[:-1] + ".", "wrong-token"]]
    assert all(response.status_code == 400 for response in errors)
    assert errors[0].json() == errors[1].json() == errors[2].json()
    assert complete(api_client, token).status_code == 200


def test_parallel_redemption_only_succeeds_once(api_client):
    token = request_link(api_client)
    def redeem(_):
        try:
            password_reset.complete_reset(token, NEW_PASSWORD, NEW_PASSWORD, "concurrent-test")
            return 200
        except password_reset.HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(redeem, range(2))) == [200, 400]


def test_changing_password_invalidates_outstanding_reset_links(admin):
    token = request_link(admin)
    other = request_link(admin, "admin@weber.demo")
    response = admin.post("/api/auth/change-password", json={"current_password": DEMO_PASSWORD, "new_password": NEW_PASSWORD})
    assert response.status_code == 200
    assert admin.get("/api/auth/me").status_code == 200
    assert complete(admin, token).status_code == 400
    assert complete(admin, other).status_code == 200


def test_demo_delivery_never_exposes_links_for_non_seeded_accounts(api_client):
    with db(write=True) as conn:
        conn.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)", (
            "new-real-user", "tenant-keller-demo", "someone@keller.demo", "Other Person", "admin", hash_password(DEMO_PASSWORD), utcnow()))
    known = api_client.post("/api/auth/forgot-password", json={"email": "someone@keller.demo"})
    unknown = api_client.post("/api/auth/forgot-password", json={"email": "unknown@example.test"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"message": password_reset.RESET_MESSAGE, "delivery": "demo"}
    with db() as conn:
        assert not conn.execute("SELECT 1 FROM password_resets").fetchone()


def test_request_rate_limit_applies_to_known_and_unknown_emails_and_expires(api_client, monkeypatch):
    monkeypatch.setattr(password_reset.time, "time", lambda: 1800000000)
    for _ in range(5):
        assert api_client.post("/api/auth/forgot-password", json={"email": "unknown@example.test"}).status_code == 200
    blocked = api_client.post("/api/auth/forgot-password", json={"email": "unknown@example.test"})
    assert blocked.status_code == 429
    assert 0 < int(blocked.headers["retry-after"]) <= 900
    assert api_client.post("/api/auth/forgot-password", json={"email": "admin@keller.demo"}).status_code == 200
    monkeypatch.setattr(password_reset.time, "time", lambda: 1800000901)
    assert api_client.post("/api/auth/forgot-password", json={"email": "unknown@example.test"}).status_code == 200


def test_ip_request_limit_cannot_be_evaded_with_email_or_forwarded_headers(api_client):
    for index in range(20):
        response = api_client.post("/api/auth/forgot-password", json={"email": f"unknown{index}@example.test"})
        assert response.status_code == 200
    assert api_client.post("/api/auth/forgot-password", json={"email": "other@example.test"},
                           headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 429


def test_failed_redemptions_are_rate_limited(api_client):
    for _ in range(30):
        assert complete(api_client, "invalid").status_code == 400
    assert complete(api_client, "invalid").status_code == 429


@pytest.mark.parametrize("mode,seed", [("disabled", "1"), ("demo", "0"), ("smtp", "0")])
def test_unconfigured_delivery_returns_same_error_for_any_email(api_client, monkeypatch, mode, seed):
    monkeypatch.setenv("LEXFLOW_RESET_DELIVERY", mode)
    monkeypatch.setenv("LEXFLOW_SEED_DEMO", seed)
    monkeypatch.delenv("LEXFLOW_SMTP_HOST", raising=False)
    known = api_client.post("/api/auth/forgot-password", json={"email": "admin@keller.demo"})
    unknown = api_client.post("/api/auth/forgot-password", json={"email": "unknown@example.test"})
    assert known.status_code == unknown.status_code == 503
    assert known.json() == unknown.json()


def smtp_config(monkeypatch):
    monkeypatch.setenv("LEXFLOW_RESET_DELIVERY", "smtp")
    monkeypatch.setenv("LEXFLOW_PUBLIC_URL", "https://lexflow.example.test")
    monkeypatch.setenv("LEXFLOW_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("LEXFLOW_SMTP_FROM", "LexFlow <noreply@example.test>")
    monkeypatch.setenv("LEXFLOW_SMTP_USERNAME", "sender")
    monkeypatch.setenv("LEXFLOW_SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("LEXFLOW_SMTP_SECURITY", "starttls")


@pytest.mark.parametrize("security", ["starttls", "tls"])
def test_smtp_delivery_is_private_uses_configured_origin_and_supports_reset(api_client, monkeypatch, security):
    smtp_config(monkeypatch)
    monkeypatch.setenv("LEXFLOW_ALLOWED_HOSTS", "testserver,untrusted.example.test")
    monkeypatch.setenv("LEXFLOW_SMTP_SECURITY", security)
    transport = MagicMock()
    monkeypatch.setattr(password_reset.smtplib, "SMTP_SSL" if security == "tls" else "SMTP", transport)
    response = api_client.post("/api/auth/forgot-password", json={"email": "admin@keller.demo"}, headers={"Host": "untrusted.example.test"})
    unknown = api_client.post("/api/auth/forgot-password", json={"email": "unknown@example.test"})
    assert response.status_code == unknown.status_code == 200
    assert response.json() == unknown.json() == {"message": password_reset.RESET_MESSAGE, "delivery": "smtp"}
    assert "token" not in response.text and "demo_reset_path" not in response.text
    transport.assert_called_once()
    server = transport.return_value.__enter__.return_value
    server.login.assert_called_once_with("sender", "smtp-password")
    if security == "starttls":
        server.starttls.assert_called_once()
    message = server.send_message.call_args.args[0]
    body = message.get_content()
    assert "untrusted.example.test" not in body
    link = next(word for word in body.split() if word.startswith("https://"))
    assert link.startswith("https://lexflow.example.test/#/reset-password?token=")
    token = parse_qs(urlsplit(link).fragment.split("?", 1)[1])["token"][0]
    assert complete(api_client, token).status_code == 200


def test_delivery_failure_revokes_link_and_does_not_expose_secrets(api_client, monkeypatch, caplog):
    smtp_config(monkeypatch)
    transport = MagicMock(side_effect=OSError("private-smtp-server-details"))
    monkeypatch.setattr(password_reset.smtplib, "SMTP", transport)
    response = api_client.post("/api/auth/forgot-password", json={"email": "admin@keller.demo"})
    assert response.status_code == 200
    with db() as conn:
        assert not conn.execute("SELECT 1 FROM password_resets").fetchone()
    assert "delivery failed" in caplog.text
    assert "private-smtp-server-details" not in caplog.text


def test_no_demo_links_when_demo_seeding_is_disabled(api_client, monkeypatch):
    monkeypatch.setenv("LEXFLOW_SEED_DEMO", "0")
    monkeypatch.delenv("LEXFLOW_RESET_DELIVERY", raising=False)
    assert api_client.post("/api/auth/forgot-password", json={"email": "admin@keller.demo"}).status_code == 503


def test_invalid_request_and_root_use_privacy_headers(api_client):
    response = api_client.post("/api/auth/reset-password", json={"token": "private-token", "new_password": "tiny", "confirm_password": "tiny"})
    assert response.status_code == 422
    assert "tiny" not in response.text and "private-token" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert api_client.get("/").headers["referrer-policy"] == "no-referrer"
