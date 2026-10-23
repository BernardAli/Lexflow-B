import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from fastapi import HTTPException
from lexflow import integrations
from lexflow.db import db, initialize
from lexflow.main import app
from lexflow.manage import backup, provision, rotate_artifacts
from lexflow.seed import DEMO_PASSWORD
from lexflow.storage import MAGIC, protect, reveal
from tests.conftest import sign_in


def rule(**values):
    return {"matter_type": "property_purchase", "field_key": "buyer_name", "label": "Erwerbende Person", **values}


def transfer_data(client, connector="demo_receiver", key="transfer-test-key", matter="matter-demo-finished"):
    response = client.post("/api/integrations/dry-run", json={"matter_id": matter, "connector": connector})
    assert response.status_code == 200, response.text
    return {"matter_id": matter, "connector": connector, "idempotency_key": key, "preview_hash": response.json()["preview_hash"]}


def test_learned_rule_preview_is_transient_and_applies_to_future_documents(admin):
    response = admin.post("/api/workflows/preview", json=rule(sample_text="Erwerbende Person: Synthetic Preview Name"))
    assert response.status_code == 200
    assert response.json()["sample_stored"] is False
    assert response.json()["candidates"][0]["value"] == "Synthetic Preview Name"
    created = admin.post("/api/workflows", json=rule())
    assert created.status_code == 200
    rule_id = created.json()["id"]
    with db() as conn:
        assert "Synthetic Preview Name" not in str([dict(r) for r in conn.execute("SELECT * FROM workflow_rules")])
        assert "Synthetic Preview Name" not in str([dict(r) for r in conn.execute("SELECT * FROM workflow_versions")])
    response = admin.post("/api/intake/text", json={"matter_id": "matter-demo-empty", "text": "Erwerbende Person: Another Person"})
    # The inheritance workflow must not use a property-purchase rule.
    assert response.status_code == 200 and response.json()["suggestions"] == 0
    response = admin.post("/api/intake/text", json={"matter_id": "matter-demo-intake", "text": "Erwerbende Person: Another Person"})
    assert response.status_code == 200
    fields = admin.get("/api/matters/matter-demo-intake").json()["fields"]
    buyer = next(f for f in fields if f["key"] == "buyer_name")
    assert any(c["origin"].startswith("workflow_rule:" + rule_id) and c["value"] == "Another Person" for c in buyer["candidates"])
    assert buyer["status"] != "confirmed"


def test_rule_versions_permissions_and_workspace_boundaries(admin):
    rule_id = admin.post("/api/workflows", json=rule()).json()["id"]
    assert admin.patch(f"/api/workflows/{rule_id}", json={"enabled": False, "expected_version": 1}).json()["version"] == 2
    assert admin.patch(f"/api/workflows/{rule_id}", json={"enabled": True, "expected_version": 1}).status_code == 409
    assert len(admin.get(f"/api/workflows/{rule_id}/versions").json()["versions"]) == 2
    sign_in(admin, "admin@weber.demo")
    assert admin.get("/api/workflows").json()["rules"] == []
    assert admin.get(f"/api/workflows/{rule_id}/versions").status_code == 404
    assert admin.patch(f"/api/workflows/{rule_id}", json={"enabled": True, "expected_version": 2}).status_code == 404
    sign_in(admin, "reviewer@keller.demo")
    assert admin.post("/api/workflows", json=rule()).status_code == 403
    assert admin.post("/api/workflows/preview", json=rule(sample_text="Erwerbende Person: Anna Beispiel")).status_code == 200
    sign_in(admin, "assistant@keller.demo")
    assert admin.post("/api/workflows/preview", json=rule(sample_text="Erwerbende Person: Anna Beispiel")).status_code == 403


def test_literal_labels_and_duplicate_rules_are_validated(admin):
    assert admin.post("/api/workflows", json=rule(label="Label: secret")).status_code == 422
    assert admin.post("/api/workflows", json=rule(field_key="heir_name")).status_code == 422
    assert admin.post("/api/workflows", json=rule()).status_code == 200
    assert admin.post("/api/workflows", json=rule(label="erwerbende person")).status_code == 409
    response = admin.post("/api/workflows/preview", json=rule(label="Buyer (.*)", sample_text="Buyer anything: Anna Example"))
    assert response.json()["candidates"] == []


def test_local_receiver_is_approval_gated_idempotent_and_has_receipts(admin):
    rejected = admin.post("/api/integrations/dry-run", json={"matter_id": "matter-demo-intake"})
    assert rejected.status_code == 409
    data = transfer_data(admin)
    first = admin.post("/api/integrations/transfers", json=data)
    assert first.status_code == 200
    assert first.json()["status"] == "accepted" and first.json()["simulated"] is True
    second = admin.post("/api/integrations/transfers", json=data)
    assert second.json()["replayed"] is True and second.json()["id"] == first.json()["id"]
    overview = admin.get("/api/integrations").json()
    assert len(overview["transfers"]) == len(overview["receiver_records"]) == 1
    payload = json.loads(overview["receiver_records"][0]["payload_json"])
    assert payload["fields"]["Beteiligter.Kaeufer.Name"]
    assert payload["simulated"] is True
    sign_in(admin, "admin@weber.demo")
    assert admin.get("/api/integrations").json()["transfers"] == []
    assert admin.post("/api/integrations/transfers", json=data).status_code == 404


def test_preview_hash_blocks_changes_and_analysts_cannot_transfer(admin):
    data = transfer_data(admin)
    assert admin.post("/api/integrations/transfers", json=data | {"preview_hash": "0" * 64}).status_code == 409
    assert admin.post("/api/matters/matter-demo-finished/reopen").status_code == 200
    assert admin.post("/api/integrations/transfers", json=data).status_code == 409
    sign_in(admin, "assistant@keller.demo")
    assert admin.post("/api/integrations/transfers", json=data).status_code == 403


def test_signed_webhook_requires_valid_receipt_and_retries_the_same_key(admin, monkeypatch):
    monkeypatch.setenv("LEXFLOW_WEBHOOK_TARGETS", json.dumps({"tenant-keller-demo": {"url": "https://destination.example.test/import", "secret": "s" * 40}}))
    transport = MagicMock()
    client = transport.return_value.__enter__.return_value
    client.post.return_value = httpx.Response(200, json={"accepted": True, "receipt_id": "accepted-42"})
    monkeypatch.setattr(integrations.httpx, "Client", transport)
    data = transfer_data(admin, "webhook")
    result = admin.post("/api/integrations/transfers", json=data)
    assert result.json()["status"] == "accepted" and result.json()["simulated"] is False
    kwargs = client.post.call_args.kwargs
    import hmac
    expected = hmac.new(b"s" * 40, kwargs["headers"]["X-LexFlow-Timestamp"].encode() + b"." + kwargs["content"], hashlib.sha256).hexdigest()
    assert kwargs["headers"]["X-LexFlow-Signature"] == "sha256=" + expected
    assert kwargs["headers"]["Idempotency-Key"] == data["idempotency_key"]
    assert admin.post("/api/integrations/transfers", json=data).json()["replayed"] is True
    assert client.post.call_count == 1
    data2 = transfer_data(admin, "webhook", key="retry-transfer-key")
    client.post.side_effect = httpx.ReadTimeout("secret connection details")
    uncertain = admin.post("/api/integrations/transfers", json=data2)
    assert uncertain.json()["status"] == "uncertain"
    assert "secret connection" not in uncertain.text
    client.post.side_effect = None
    assert admin.post("/api/integrations/transfers", json=data2).json()["status"] == "accepted"


def test_agent_intake_retries_do_not_duplicate_or_invalidate_again(admin):
    key = {"Idempotency-Key": "folder-stable-example-key"}
    def send(raw=b"Kaeufer: Agent Example"):
        return admin.post("/api/integrations/intake", data={"matter_id": "matter-demo-intake"}, files={"file": ("agent.txt", raw)}, headers=key)
    first = send()
    assert first.status_code == 200, first.text
    second = send()
    assert second.json()["replayed"] is True
    assert first.json()["results"][0]["document_id"] == second.json()["results"][0]["document_id"]
    assert send(b"Kaeufer: Different Content").status_code == 409
    with db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM documents WHERE name='agent.txt'").fetchone()[0] == 1
    sign_in(admin, "admin@weber.demo")
    assert send().status_code == 404


def test_agent_failure_does_not_leave_a_receipt(admin):
    response = admin.post("/api/integrations/intake", data={"matter_id": "matter-demo-intake"},
                          files={"file": ("broken.pdf", b"not a pdf")}, headers={"Idempotency-Key": "broken-agent-example"})
    assert response.status_code == 422
    with db() as conn:
        assert not conn.execute("SELECT 1 FROM intake_receipts").fetchone()


def test_pilot_has_empty_time_baselines_and_explained_denominators(admin):
    data = admin.get("/api/pilot").json()
    assert data["baseline"] is None and data["pilot_minutes"] is None and data["time_saved_percent"] is None
    assert data["coverage"]["denominator"] == 15
    assert data["coverage"]["numerator"] == 15
    assert data["transfers"][0]["percent"] is None
    assert data["audit_coverage"]["percent"] < 100  # historical seed fixtures do not invent full events
    assert admin.put("/api/pilot/baseline", json={"matter_type": "property_purchase", "minutes": 20, "sample_size": 5}).status_code == 200
    for seconds in (120, 180):
        assert admin.post("/api/pilot/observations", json={"matter_id": "matter-demo-intake", "seconds": seconds}).status_code == 200
    result = admin.get("/api/pilot").json()
    assert result["pilot_minutes"] == 5 and result["timed_matters"] == 1
    assert result["time_saved_percent"] == 75
    assert admin.post("/api/pilot/observations", json={"matter_id": "matter-other-tenant", "seconds": 100}).status_code == 404
    csv = admin.get("/api/pilot/report.csv")
    assert csv.status_code == 200 and "baseline_minutes,20.0" in csv.content.decode("utf-8-sig")
    sign_in(admin, "admin@weber.demo")
    assert admin.get("/api/pilot").json()["baseline"] is None


def test_pilot_separates_simulated_transfers_and_tracks_manual_correction(admin):
    data = transfer_data(admin)
    admin.post("/api/integrations/transfers", json=data)
    assert admin.post("/api/matters/matter-demo-intake/fields/buyer_name/confirm", json={"value": "Corrected Synthetic Buyer"}).status_code == 200
    result = admin.get("/api/pilot").json()
    assert result["corrections"]["numerator"] >= 1
    assert result["transfers"][0]["percent"] == 100
    assert result["transfers"][1]["percent"] is None


def test_security_headers_sign_in_limits_and_idle_sessions(api_client):
    root = api_client.get("/")
    assert root.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in root.headers["content-security-policy"]
    assert api_client.get("/", headers={"Host": "attacker.invalid"}).status_code == 400
    for _ in range(10):
        assert api_client.post("/api/auth/login", json={"email": "unknown@example.test", "password": "invalid"}).status_code == 401
    limited = api_client.post("/api/auth/login", json={"email": "unknown@example.test", "password": "invalid"})
    assert limited.status_code == 429 and "retry-after" in limited.headers
    sign_in(api_client)
    with db(write=True) as conn:
        conn.execute("UPDATE session_activity SET last_seen='2000-01-01T00:00:00+00:00'")
    assert api_client.get("/api/auth/me").status_code == 401


def test_revoke_other_sessions_and_detect_tampered_audit(admin):
    first = admin.cookies.get("lexflow_session")
    sign_in(admin)
    assert admin.post("/api/security/sessions/revoke-others").json()["revoked"] == 1
    assert admin.get("/api/auth/me", headers={"Cookie": "lexflow_session=" + first}).status_code == 401
    assert admin.get("/api/security/status").json()["audit_integrity"]["valid"] is True
    with db(write=True) as conn:
        conn.execute("UPDATE audit SET action='tampered' WHERE id=(SELECT id FROM audit LIMIT 1)")
    assert admin.get("/api/security/audit-checkpoint").json()["valid"] is False


def test_encrypted_artifacts_download_and_workspace_key_binding(admin, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("LEXFLOW_STORAGE_KEYS", json.dumps({"tenant-keller-demo": [key], "tenant-weber-demo": [key]}))
    content = b"Kaeufer: Encrypted Synthetic Buyer"
    response = admin.post("/api/intake/upload", data={"matter_id": "matter-demo-intake"}, files={"files": ("encrypted.txt", content)})
    assert response.status_code == 200
    doc_id = response.json()["results"][0]["document_id"]
    with db() as conn:
        row = conn.execute("SELECT file_path FROM documents WHERE id=?", (doc_id,)).fetchone()
    raw = Path(row["file_path"]).read_bytes()
    assert raw.startswith(MAGIC) and content not in raw
    assert admin.get(f"/api/documents/{doc_id}/download").content == content
    with pytest.raises(HTTPException) as error:
        reveal(raw, "tenant-weber-demo")
    assert error.value.status_code == 503
    assert rotate_artifacts("tenant-keller-demo") >= 1
    assert admin.get(f"/api/documents/{doc_id}/download").content == content


def test_time_observation_retries_do_not_double_count(admin):
    observation = {"matter_id": "matter-demo-intake", "seconds": 120, "source": "timer", "idempotency_key": "time-same-work-session"}
    assert admin.post("/api/pilot/observations", json=observation).status_code == 200
    assert admin.post("/api/pilot/observations", json=observation).json()["replayed"] is True
    assert admin.get("/api/pilot").json()["pilot_minutes"] == 2
    assert admin.post("/api/pilot/observations", json=observation | {"seconds": 240}).status_code == 409


def test_storage_rotation_keeps_old_keys_readable_and_authenticates_ciphertext(admin, monkeypatch):
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    monkeypatch.setenv("LEXFLOW_STORAGE_KEYS", json.dumps({"tenant-keller-demo": [old]}))
    raw = protect(b"synthetic secret bytes", "tenant-keller-demo")
    monkeypatch.setenv("LEXFLOW_STORAGE_KEYS", json.dumps({"tenant-keller-demo": [new, old]}))
    assert reveal(raw, "tenant-keller-demo") == b"synthetic secret bytes"
    modified = raw[:-8] + b"tampered!"
    with pytest.raises(HTTPException):
        reveal(modified, "tenant-keller-demo")
    with pytest.raises(HTTPException):
        monkeypatch.setenv("LEXFLOW_STORAGE_KEYS", json.dumps({"tenant-keller-demo": [new]}))
        reveal(raw, "tenant-keller-demo")


def test_backup_is_consistent_and_audit_key_can_be_restored(admin, tmp_path, monkeypatch):
    destination = tmp_path / "snapshot"
    backup(destination)
    assert (destination / "lexflow.sqlite3").exists()
    assert (destination / "backup.json").exists()
    monkeypatch.setenv("LEXFLOW_DATA_DIR", str(destination))
    assert admin.get("/api/security/audit-checkpoint").json()["valid"] is True


def test_hardened_profile_rejects_incomplete_configuration(api_client, monkeypatch):
    monkeypatch.setenv("LEXFLOW_SECURITY_PROFILE", "hardened")
    with pytest.raises(RuntimeError, match="Hardened profile"):
        with TestClient(app):
            pass


def test_dedicated_workspace_hardened_startup_and_https(api_client, monkeypatch, tmp_path):
    monkeypatch.setenv("LEXFLOW_DATA_DIR", str(tmp_path / "dedicated"))
    monkeypatch.setenv("LEXFLOW_SEED_DEMO", "0")
    monkeypatch.setenv("LEXFLOW_SECURITY_PROFILE", "hardened")
    monkeypatch.setenv("LEXFLOW_SECURE_COOKIES", "1")
    monkeypatch.setenv("LEXFLOW_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("LEXFLOW_PUBLIC_URL", "https://testserver")
    monkeypatch.setenv("LEXFLOW_AUDIT_KEY", "a" * 48)
    monkeypatch.setenv("LEXFLOW_STORAGE_KEYS", json.dumps({"office-test": [Fernet.generate_key().decode()]}))
    initialize()
    provision("office-test", "Test Office", "admin@office.test", "New-Dedicated-Password!")
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post("/api/auth/login", json={"email": "admin@office.test", "password": "New-Dedicated-Password!"})
        assert response.status_code == 200 and "Secure" in response.headers["set-cookie"]
        assert client.get("/api/auth/options").json()["demo_mode"] is False
        assert client.get("/docs").status_code == 404
        assert "strict-transport-security" in response.headers
        assert client.get("/api/security/status").json()["profile"] == "hardened"
        assert client.get("http://testserver/").status_code == 400
