import io
from pathlib import Path
import pytest
from tests.conftest import sign_in


def assert_status(resp, expected=200):
    assert resp.status_code == expected, f"{resp.status_code}: {resp.text}"


def test_login_health_dashboard_and_conflict(api_client):
    assert_status(api_client.get('/api/health'))
    assert_status(api_client.get('/'),200)
    assert_status(api_client.get('/api/dashboard'),401)
    assert_status(api_client.post('/api/auth/login',json={'email':'admin@keller.demo','password':'wrong'}),401)
    sign_in(api_client)
    d=api_client.get('/api/dashboard').json()
    assert d['total_matters']==5
    assert d['documents']==5
    assert d['exports']==1
    assert d['conflicts']==1
    m=api_client.get('/api/matters/matter-demo-conflict').json()
    land=next(f for f in m['fields'] if f['key']=='land_register')
    buyer=next(f for f in m['fields'] if f['key']=='buyer_name')
    assert land['status']=='conflict'
    assert buyer['status']=='needs_review'
    assert sorted({x['value'] for x in land['candidates']}) == ['München Blatt 812','München Blatt 872']
    assert not m['ready_for_approval']
    assert_status(api_client.post('/api/matters/matter-demo-conflict/approve'),422)


def test_workflow_from_text_to_approved_export(admin):
    r=admin.post('/api/matters',json={'title':'Test property purchase','matter_type':'property_purchase'})
    assert_status(r)
    mid=r.json()['id']
    original=Path('samples/03_property_intake.txt').read_text()
    r=admin.post('/api/intake/text',json={'matter_id':mid,'filename':'demo.txt','text':original})
    assert_status(r)
    assert r.json()['suggestions']>=5
    d=admin.get('/api/matters/'+mid).json()
    assert d['matter']['status']=='in_review'
    required=[f for f in d['fields'] if f['required']]
    assert all(f['candidates'] for f in required)
    assert_status(admin.post(f'/api/matters/{mid}/exports',json={'format':'json'}),409)
    for f in required:
        assert_status(admin.post(f'/api/matters/{mid}/fields/{f["key"]}/confirm',
                     json={'candidate_id':f['candidates'][0]['id'],'note':'Verified in demo'}))
    d=admin.get('/api/matters/'+mid).json()
    assert d['ready_for_approval'] is True
    r=admin.post('/api/matters/'+mid+'/approve')
    assert_status(r)
    preview=admin.get('/api/matters/'+mid+'/export/preview').json()['preview']
    assert 'Beteiligter.Kaeufer.Name' in preview
    assert 'Tobias Neumann' in preview
    r=admin.post(f'/api/matters/{mid}/exports',json={'format':'json','connector':'notary_demo'})
    assert_status(r)
    assert r.json()['live_transfer'] is False
    export=admin.get(r.json()['download_url']);assert_status(export)
    assert export.json()['not_a_live_transmission'] is True
    assert export.json()['fields']['Vorgang.KaufpreisEUR']=='425000.00'
    r2=admin.post(f'/api/matters/{mid}/exports',json={'format':'csv','connector':'approved_export'})
    assert_status(r2)
    csvdata=admin.get(r2.json()['download_url']).content.decode('utf-8-sig')
    assert 'destination_field,value' in csvdata
    assert 'Beteiligter.Kaeufer.Name,Tobias Neumann' in csvdata
    assert admin.get('/api/dashboard').json()['exports']==3
    assert_status(admin.post(f'/api/matters/{mid}/reopen'))
    assert admin.get('/api/matters/'+mid).json()['matter']['status']=='in_review'


def test_input_change_invalidates_previous_review(admin):
    mid='matter-demo-intake'
    d=admin.get('/api/matters/'+mid).json()
    field=next(f for f in d['fields'] if f['key']=='buyer_name')
    assert_status(admin.post(f'/api/matters/{mid}/fields/buyer_name/confirm',json={'candidate_id':field['candidates'][0]['id']}))
    assert admin.get('/api/matters/'+mid).json()['fields'][0]['status']=='confirmed'
    r=admin.post('/api/intake/text',json={'matter_id':mid,'text':'Käufer: Another Fictional Buyer\nVerkäufer: Lena Fischer'})
    assert_status(r)
    d=admin.get('/api/matters/'+mid).json()
    field=next(f for f in d['fields'] if f['key']=='buyer_name')
    assert field['status']=='conflict'
    assert d['required_confirmed']==0


def test_upload_errors_and_txt_upload(admin):
    files={'files':('unsupported.exe',b'TEST','application/octet-stream')}
    r=admin.post('/api/intake/upload',data={'matter_id':'matter-demo-intake'},files=files)
    assert_status(r,415)
    files={'files':('synthetic.txt',b'Kaufpreis: 250.000,00 EUR\nGrundbuch: Berlin Blatt 500\n','text/plain')}
    r=admin.post('/api/intake/upload',data={'matter_id':'matter-demo-intake'},files=files)
    assert_status(r)
    did=r.json()['results'][0]['document_id']
    price=next(f for f in admin.get('/api/matters/matter-demo-intake').json()['fields'] if f['key']=='purchase_price')
    assert any(c['document_id']==did and c['value']=='250000.00' for c in price['candidates'])
    assert_status(admin.get('/api/documents/'+did+'/download'))
    assert_status(admin.post('/api/intake/text',json={'matter_id':'matter-demo-intake','text':'Grundbuch: Test Blatt 1','use_external_ai':True}),400)


def test_cross_tenant_isolation(api_client):
    sign_in(api_client)
    assert_status(api_client.get('/api/matters/matter-other-tenant'),404)
    assert_status(api_client.post('/api/intake/text',json={'matter_id':'matter-other-tenant','text':'Käufer: Evil'}),404)
    sign_in(api_client,'admin@weber.demo')
    assert api_client.get('/api/dashboard').json()['total_matters']==1
    assert_status(api_client.get('/api/matters/matter-demo-conflict'),404)
    assert_status(api_client.get('/api/documents/this-does-not-exist'),404)
    assert_status(api_client.get('/api/exports'),200)
    assert api_client.get('/api/exports').json()['exports']==[]


def test_roles_and_csrf(api_client):
    sign_in(api_client,'assistant@keller.demo')
    r=api_client.post('/api/matters/matter-demo-intake/fields/buyer_name/confirm',json={'value':'Jane Doe'})
    assert_status(r,403)
    assert_status(api_client.put('/api/settings/mappings',json={'mappings':{'buyer_name':'person.name'}}),403)
    assert_status(api_client.get('/api/settings/users'),403)
    sign_in(api_client,'reviewer@keller.demo')
    assert_status(api_client.post('/api/matters/matter-demo-intake/fields/buyer_name/confirm',json={'value':'Tobias Neumann'}))
    api_client.headers.pop('X-CSRF-Token',None)
    assert_status(api_client.post('/api/matters/matter-demo-intake/approve'),403)


def test_audit_connector_customization_and_password(admin):
    r=admin.put('/api/settings/mappings',json={'mappings':{'buyer_name':'Eigene.Struktur.Kaeufer'}})
    assert_status(r)
    assert admin.get('/api/settings/mappings').json()['mappings']['buyer_name']=='Eigene.Struktur.Kaeufer'
    assert_status(admin.put('/api/settings/mappings',json={'mappings':{'buyer_name':'../BAD'}}),422)
    events=admin.get('/api/audit').json()['events']
    assert any(e['action']=='connector_mappings_updated' for e in events)
    assert_status(admin.post('/api/auth/change-password',json={'current_password':'bad','new_password':'some-long-new-password'}),403)
    assert_status(admin.post('/api/auth/change-password',json={'current_password':'LexFlowDemo2026!','new_password':'safe-demo-new-password'}))
    assert_status(admin.post('/api/auth/login',json={'email':'admin@keller.demo','password':'safe-demo-new-password'}))


def test_pdf_word_and_email_end_to_end(admin):
    """Real parser fixtures, not just mocked strings."""
    for filename,expected in [
        ('07_synthetic_property_purchase.pdf',('buyer_name','Emilia Roth')),
        ('08_synthetic_property_purchase.docx',('buyer_name','Charlotte Winter')),
        ('06_property_email.eml',('buyer_name','Anna Schmidt')),
    ]:
        matter=admin.post('/api/matters',json={'title':'Fixture '+filename,'matter_type':'property_purchase'}).json()
        content=(Path('samples')/filename).read_bytes()
        upload=admin.post('/api/intake/upload',data={'matter_id':matter['id']},files={
          'files':(filename,content,'application/octet-stream')
        })
        assert_status(upload)
        assert upload.json()['results'][0]['suggestions']>=5
        fields=admin.get('/api/matters/'+matter['id']).json()['fields']
        target=next(f for f in fields if f['key']==expected[0])
        assert target['value']==expected[1]
        assert target['status']=='needs_review'
