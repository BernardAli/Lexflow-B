import pytest
from fastapi.testclient import TestClient
from lexflow.main import app
from lexflow.seed import DEMO_PASSWORD


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEXFLOW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LEXFLOW_SEED_DEMO", "1")
    monkeypatch.setenv("LEXFLOW_ALLOW_EXTERNAL_AI", "0")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LEXFLOW_RESET_DELIVERY", raising=False)
    monkeypatch.setenv("LEXFLOW_SECURITY_PROFILE", "demo")
    monkeypatch.setenv("LEXFLOW_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    monkeypatch.setenv("LEXFLOW_IDLE_MINUTES", "30")
    monkeypatch.setenv("LEXFLOW_SECURE_COOKIES", "0")
    monkeypatch.setenv("LEXFLOW_DEMO_NOTARY", "0")
    for name in ("LEXFLOW_STORAGE_KEYS", "LEXFLOW_AUDIT_KEY", "LEXFLOW_WEBHOOK_TARGETS", "LEXFLOW_MFA_KEY", "LEXFLOW_REQUIRE_MFA"):
        monkeypatch.delenv(name, raising=False)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def admin(api_client):
    sign_in(api_client)
    return api_client


def sign_in(client, email="admin@keller.demo"):
    response=client.post("/api/auth/login", json={"email":email,"password":DEMO_PASSWORD})
    assert response.status_code==200, response.text
    client.headers.update({"X-CSRF-Token":response.json()["csrf"]})
    return response.json()
