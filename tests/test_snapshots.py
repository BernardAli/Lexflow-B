import hashlib
import hmac
import json
import shutil
import sqlite3
from contextlib import closing

import pytest
from cryptography.fernet import Fernet

from lexflow.db import db
from lexflow.manage import rotate_artifacts
from lexflow.settings import data_dir
from lexflow.snapshots import backup, canonical, restore, verify_snapshot
from tests.test_mfa import enable
from tests.test_delivery import notary
from tests.test_platform_features import transfer_data


def test_portable_restore_authenticates_files_audit_mfa_and_destination(notary, tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv('LEXFLOW_STORAGE_KEYS', json.dumps({'tenant-keller-demo':[key]}))
    rotate_artifacts('tenant-keller-demo')
    assert notary.post('/api/integrations/transfers', json=transfer_data(notary, connector='demo_notary')).json()['status'] == 'accepted'
    secret, codes = enable(notary)
    original = data_dir()
    snapshot = tmp_path / 'snapshot'
    backup(snapshot)
    verified = verify_snapshot(snapshot)
    assert verified['valid'] and verified['artifacts_checked'] > 0
    assert verify_snapshot(snapshot) == verified
    moved = tmp_path / 'moved-snapshot'
    shutil.move(snapshot, moved)
    restored = tmp_path / 'replacement'
    result = restore(moved, restored)
    assert result['sessions_revoked'] and data_dir() == original
    with closing(sqlite3.connect(restored / 'lexflow.sqlite3')) as conn:
        for table in ('sessions', 'mfa_challenges', 'password_resets', 'session_mfa'):
            assert conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] == 0
        for table in ('documents', 'exports'):
            for path, in conn.execute('SELECT file_path FROM '+table):
                assert path.startswith(str(restored))
        assert conn.execute('SELECT COUNT(*) FROM mfa_credentials WHERE enabled=1').fetchone()[0] == 1
    monkeypatch.setenv('LEXFLOW_DATA_DIR', str(restored))
    from fastapi.testclient import TestClient
    from lexflow.main import app
    with TestClient(app) as client:
        token = client.post('/api/auth/login', json={'email':'admin@keller.demo','password':'LexFlowDemo2026!'}).json()['challenge']
        session = client.post('/api/auth/mfa/verify', json={'challenge':token,'code':codes[0]}).json()
        client.headers['X-CSRF-Token'] = session['csrf']
        assert client.get('/api/security/audit-checkpoint').json()['valid']
        cases = client.get('/api/demo-notary/cases').json()['cases']
        assert len(cases) == 1
        documents = client.get('/api/matters/matter-demo-intake').json()['documents']
        assert client.get('/api/documents/'+documents[0]['id']+'/download').status_code == 200
        with db() as conn:
            encrypted = conn.execute('SELECT user_id,secret_ciphertext FROM mfa_credentials WHERE enabled=1').fetchone()
            from lexflow.mfa import decrypt_secret
            assert decrypt_secret(*encrypted) == secret


@pytest.mark.parametrize('change', ['modify', 'missing', 'extra', 'symlink', 'manifest'])
def test_snapshot_refuses_tampering_before_restore(admin, tmp_path, change):
    snapshot, destination = tmp_path/'snapshot', tmp_path/'replacement'
    backup(snapshot)
    if change == 'modify':
        with (snapshot/'lexflow.sqlite3').open('ab') as out:
            out.write(b'tampered')
    elif change == 'missing':
        (snapshot/'lexflow.sqlite3').unlink()
    elif change == 'extra':
        (snapshot/'unexpected.txt').write_text('unexpected')
    elif change == 'symlink':
        (snapshot/'link').symlink_to(snapshot/'lexflow.sqlite3')
    else:
        manifest = json.loads((snapshot/'backup.json').read_text())
        manifest['created_at'] = 'changed'
        (snapshot/'backup.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        restore(snapshot, destination)
    assert not destination.exists()


def test_external_key_required_and_existing_destinations_never_overwritten(api_client, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from lexflow.main import app
    key = 'external-signing-key-for-the-snapshot-test'
    monkeypatch.setenv('LEXFLOW_DATA_DIR', str(tmp_path/'external-data'))
    monkeypatch.setenv('LEXFLOW_AUDIT_KEY', key)
    snapshot = tmp_path/'snapshot'
    with TestClient(app):
        backup(snapshot)
    # Externally injected keys are never copied into the snapshot.
    manifest = json.loads((snapshot/'backup.json').read_text())
    assert manifest['external_keys_included'] is False
    assert not (snapshot/'.audit-key').exists()
    monkeypatch.setenv('LEXFLOW_AUDIT_KEY', 'wrong-key'*8)
    with pytest.raises(ValueError, match='authentication'):
        verify_snapshot(snapshot)
    monkeypatch.setenv('LEXFLOW_AUDIT_KEY', key)
    existing = tmp_path/'existing'
    existing.mkdir()
    sentinel = existing/'keep.txt'
    sentinel.write_text('keep')
    with pytest.raises(ValueError):
        restore(snapshot, existing)
    with pytest.raises(ValueError):
        backup(existing)
    with pytest.raises(ValueError):
        backup(data_dir()/'nested')
    assert sentinel.read_text() == 'keep'


def test_authenticated_manifest_still_rejects_unsafe_database_artifact_paths(admin, tmp_path):
    snapshot = tmp_path/'snapshot'
    backup(snapshot)
    with closing(sqlite3.connect(snapshot/'lexflow.sqlite3')) as conn:
        conn.execute("UPDATE documents SET file_path='/outside/document.txt'")
        conn.commit()
    manifest = json.loads((snapshot/'backup.json').read_text())
    manifest['files']['lexflow.sqlite3'] = hashlib.sha256((snapshot/'lexflow.sqlite3').read_bytes()).hexdigest()
    manifest.pop('signature')
    manifest['signature'] = hmac.new((snapshot/'.audit-key').read_bytes(), canonical(manifest), hashlib.sha256).hexdigest()
    (snapshot/'backup.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='outside'):
        verify_snapshot(snapshot)
