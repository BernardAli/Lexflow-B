import json
import sqlite3
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from lexflow import delivery, integrations, main
from lexflow.db import db
from lexflow.settings import database_path
from tests.conftest import sign_in
from tests.test_platform_features import transfer_data


@pytest.fixture
def notary(api_client, monkeypatch):
    monkeypatch.setenv("LEXFLOW_DEMO_NOTARY", "1")
    with TestClient(main.app) as client:
        sign_in(client)
        yield client


def test_demo_notary_signed_tls_handoff_case_stage_and_tenant_isolation(notary):
    assert notary.get('/demo-notary').status_code == 200
    data = transfer_data(notary, connector="demo_notary")
    result = notary.post('/api/integrations/transfers', json=data)
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'accepted' and result.json()['simulated'] is True
    assert notary.post('/api/integrations/transfers', json=data).json()['replayed'] is True
    cases = notary.get('/api/demo-notary/cases').json()['cases']
    assert len(cases) == 1 and cases[0]['stage'] == 'received'
    case = cases[0]
    assert case['fields']['Beteiligter.Kaeufer.Name']
    changed = notary.post('/api/demo-notary/cases/'+case['id']+'/stage', json={'stage':'in_preparation','expected_revision':1})
    assert changed.status_code == 200 and changed.json()['case']['revision'] == 2
    assert notary.post('/api/demo-notary/cases/'+case['id']+'/stage', json={'stage':'ready_for_review','expected_revision':1}).status_code == 409
    sign_in(notary, 'admin@weber.demo')
    assert notary.get('/api/demo-notary/cases').json()['cases'] == []
    assert notary.post('/api/demo-notary/cases/'+case['id']+'/stage', json={'stage':'received','expected_revision':2}).status_code == 404
    sign_in(notary, 'assistant@keller.demo')
    assert len(notary.get('/api/demo-notary/cases').json()['cases']) == 1
    assert notary.post('/api/demo-notary/cases/'+case['id']+'/stage', json={'stage':'received','expected_revision':2}).status_code == 403


def test_unsigned_receiver_requests_and_forged_acceptance_are_rejected(notary, monkeypatch):
    from lexflow.demo_notary import target
    import ssl
    configured = target('tenant-keller-demo')
    with httpx.Client(verify=ssl.create_default_context(cafile=configured['ca_file']), trust_env=False) as client:
        result = client.post(configured['url'], json={'workspace_id':'tenant-keller-demo'})
        assert result.status_code == 401
    transport = MagicMock()
    transport.return_value.__enter__.return_value.post.return_value = httpx.Response(200, json={'accepted':True,'receipt_id':'forged'})
    monkeypatch.setattr(integrations.httpx, 'Client', transport)
    state, receipt = integrations.send_webhook({'url':'https://destination.example.test/import','secret':'s'*40,'require_signed_receipt':True}, {'synthetic':True}, 'stable-demo-key')
    assert state == 'uncertain' and 'authenticated' in receipt['message']


def test_network_delivery_releases_writer_lock_and_locks_only_the_approved_matter(admin, monkeypatch):
    monkeypatch.setenv('LEXFLOW_WEBHOOK_TARGETS', json.dumps({'tenant-keller-demo':{'url':'https://destination.example.test/import','secret':'s'*40}}))
    data = transfer_data(admin, connector='webhook')
    with db() as conn:
        user = dict(conn.execute("SELECT id,tenant_id FROM users WHERE email='admin@keller.demo'").fetchone())
    def send(*args):
        with sqlite3.connect(database_path(), timeout=0.1) as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('SELECT COUNT(*) FROM matters').fetchone()
        with pytest.raises(HTTPException) as error:
            main.reopen_matter(data['matter_id'], user=user)
        assert error.value.status_code == 409 and 'delivery' in error.value.detail
        with pytest.raises(HTTPException) as error:
            main.update_mappings(main.MappingUpdate(mappings={'buyer_name':'Changed.Buyer'}), user=user)
        assert error.value.status_code == 409
        return 'accepted', {'receipt_id':'destination-recorded-1'}
    monkeypatch.setattr(integrations, 'send_webhook', send)
    result = admin.post('/api/integrations/transfers', json=data)
    assert result.status_code == 200 and result.json()['status'] == 'accepted'
    assert admin.post('/api/matters/'+data['matter_id']+'/reopen').status_code == 200


def test_crash_after_destination_commit_reuses_durable_key_without_duplicate(notary, monkeypatch):
    data = transfer_data(notary, connector='demo_notary')
    real_deliver = delivery.deliver
    monkeypatch.setattr(delivery, 'deliver', lambda tenant, identifier: {'id':identifier,'status':'pending'})
    queued = notary.post('/api/integrations/transfers', json=data).json()
    monkeypatch.setattr(delivery, 'deliver', real_deliver)
    real_send = integrations.send_webhook
    def crash_after_acceptance(*args):
        state, _ = real_send(*args)
        assert state == 'accepted'
        raise KeyboardInterrupt('Simulated process termination after remote commit')
    monkeypatch.setattr(integrations, 'send_webhook', crash_after_acceptance)
    with pytest.raises(KeyboardInterrupt):
        real_deliver('tenant-keller-demo', queued['id'])
    with db(write=True) as conn:
        row = conn.execute('SELECT status FROM integration_transfers WHERE id=?', (queued['id'],)).fetchone()
        assert row[0] == 'sending'
        conn.execute('UPDATE integration_jobs SET lease_until=0 WHERE transfer_id=?', (queued['id'],))
    monkeypatch.setattr(integrations, 'send_webhook', real_send)
    resumed = delivery.resume_pending()
    assert resumed[0]['status'] == 'accepted' and resumed[0]['attempt_count'] == 2
    assert len(notary.get('/api/demo-notary/cases').json()['cases']) == 1


def test_unsent_intent_is_cancelled_when_approval_changes(admin, monkeypatch):
    data = transfer_data(admin)
    real = delivery.deliver
    monkeypatch.setattr(delivery, 'deliver', lambda tenant, identifier:{'id':identifier,'status':'pending'})
    admin.post('/api/integrations/transfers', json=data)
    monkeypatch.setattr(delivery, 'deliver', real)
    assert admin.post('/api/matters/'+data['matter_id']+'/reopen').status_code == 200
    result = delivery.resume_pending()
    assert result[0]['status'] == 'cancelled'
    with db() as conn:
        assert conn.execute('SELECT COUNT(*) FROM receiver_records').fetchone()[0] == 0


def test_retries_cannot_silently_switch_destination(admin, monkeypatch):
    monkeypatch.setenv('LEXFLOW_WEBHOOK_TARGETS', json.dumps({'tenant-keller-demo':{'url':'https://first.example.test/import','secret':'s'*40}}))
    monkeypatch.setattr(integrations, 'send_webhook', lambda *args:('uncertain', {'message':'Check destination'}))
    data = transfer_data(admin, connector='webhook')
    assert admin.post('/api/integrations/transfers', json=data).json()['status'] == 'uncertain'
    monkeypatch.setenv('LEXFLOW_WEBHOOK_TARGETS', json.dumps({'tenant-keller-demo':{'url':'https://other.example.test/import','secret':'s'*40}}))
    assert admin.post('/api/integrations/transfers', json=data).status_code == 409


def test_late_receipt_preserves_a_newer_approval_and_marks_original_payload_superseded(admin, monkeypatch):
    monkeypatch.setenv('LEXFLOW_WEBHOOK_TARGETS', json.dumps({'tenant-keller-demo':{'url':'https://destination.example.test/import','secret':'s'*40}}))
    data = transfer_data(admin, connector='webhook')
    def send(*args):
        # Simulate a process pause beyond its lease, followed by renewed review.
        with db(write=True) as conn:
            conn.execute('UPDATE integration_jobs SET lease_until=0')
        assert admin.post('/api/matters/'+data['matter_id']+'/reopen').status_code == 200
        assert admin.post('/api/matters/'+data['matter_id']+'/fields/buyer_name/confirm', json={'value':'Updated Synthetic Buyer','note':'Newer review'}).status_code == 200
        assert admin.post('/api/matters/'+data['matter_id']+'/approve').status_code == 200
        return 'accepted', {'receipt_id':'late-original-acceptance'}
    monkeypatch.setattr(integrations, 'send_webhook', send)
    result = admin.post('/api/integrations/transfers', json=data).json()
    assert result['status'] == 'accepted' and result['superseded'] is True
    detail = admin.get('/api/matters/'+data['matter_id']).json()
    assert detail['matter']['status'] == 'approved'
    assert next(field for field in detail['fields'] if field['key']=='buyer_name')['value'] == 'Updated Synthetic Buyer'
