"""Regression coverage for the presentation review and repeatable demonstration."""
import io
import json
from email.message import EmailMessage
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfWriter

from lexflow.db import db
from lexflow.documents import parse_document
from lexflow.exporter import generate_export
from lexflow.settings import data_dir
from tests.conftest import sign_in


def demo(client):
    response = client.post('/api/demo/start')
    assert response.status_code == 200, response.text
    return response.json()['id']


def fields(client, mid):
    return client.get('/api/matters/'+mid).json()['fields']


def confirm_required(client, mid):
    for field in fields(client, mid):
        if field['required']:
            response = client.post(f'/api/matters/{mid}/fields/{field["key"]}/confirm',
                                   json={'candidate_id':field['candidates'][0]['id'],'note':'Checked synthetic source'})
            assert response.status_code == 200, response.text


def test_repeatable_demo_starts_fresh_and_exports(admin):
    first, second = demo(admin), demo(admin)
    assert first != second
    detail = admin.get('/api/matters/'+first).json()
    assert len(detail['documents']) == 2
    assert detail['matter']['conflict_count'] == 1
    confirm_required(admin, first)
    assert admin.post(f'/api/matters/{first}/approve').status_code == 200
    result = admin.post(f'/api/matters/{first}/exports',json={'format':'json','connector':'notary_demo'})
    assert result.status_code == 200
    payload = admin.get(result.json()['download_url']).json()
    assert payload['fields']['Vorgang.KaufpreisEUR'] == '850000.00'
    assert payload['not_a_live_transmission'] is True
    assert len(payload['fields']) == 5
    assert admin.get('/api/matters/'+second).json()['required_confirmed'] == 0


def test_optional_conflict_blocks_approval_until_explicit_resolution(admin):
    mid = demo(admin)
    assert admin.post('/api/intake/text',json={'matter_id':mid,'text':'Buyer email: other@example.test'}).status_code == 200
    confirm_required(admin,mid)
    detail = admin.get('/api/matters/'+mid).json()
    assert detail['required_confirmed'] == detail['required_total']
    assert not detail['ready_for_approval']
    assert admin.post(f'/api/matters/{mid}/approve').status_code == 422
    assert admin.post(f'/api/matters/{mid}/exports',json={'format':'json'}).status_code == 409
    email = next(f for f in detail['fields'] if f['key']=='buyer_email')
    assert admin.post(f'/api/matters/{mid}/fields/buyer_email/confirm',json={'candidate_id':email['candidates'][0]['id']}).status_code == 200
    assert admin.post(f'/api/matters/{mid}/approve').status_code == 200


def test_mapping_collisions_rejected_in_full_and_partial_updates(admin):
    original = admin.get('/api/settings/mappings').json()['mappings']
    for update in ({'buyer_name':'Party.Name','seller_name':'Party.Name'}, {'buyer_name':original['seller_name']}):
        response = admin.put('/api/settings/mappings',json={'mappings':update})
        assert response.status_code == 422
        assert admin.get('/api/settings/mappings').json()['mappings'] == original
    with pytest.raises(ValueError,match='used by both'):
        generate_export({}, {'buyer_name':'Anna Schmidt','seller_name':'Peter Müller'},
                        {'buyer_name':'Party.Name','seller_name':'Party.Name'},'approved_export','json')


@pytest.mark.parametrize('key,value',[
    ('purchase_price','not money'), ('purchase_price','-100'), ('purchase_price','0'),
    ('purchase_price','1.234.56'), ('purchase_price','USD 100'),
    ('appointment_date','31.02.2026'), ('appointment_date','tomorrow'),
    ('buyer_email','bad@@example.test'), ('buyer_email','buyer@bad..test'),
    ('buyer_name','12345'),
])
def test_invalid_reviewed_values_rejected(admin,key,value):
    response = admin.post(f'/api/matters/matter-demo-intake/fields/{key}/confirm',json={'value':value})
    assert response.status_code == 422, response.text


@pytest.mark.parametrize('key,value,expected',[
    ('purchase_price','850.000,00 €','850000.00'),
    ('purchase_price','EUR 850,000.00','850000.00'),
    ('purchase_price','123456789012345.67','123456789012345.67'),
    ('appointment_date','17.11.2026','2026-11-17'),
    ('buyer_email','ANNA@EXAMPLE.TEST','anna@example.test'),
])
def test_review_values_are_normalized_without_float_rounding(admin,key,value,expected):
    response = admin.post(f'/api/matters/matter-demo-intake/fields/{key}/confirm',json={'value':value})
    assert response.status_code == 200, response.text
    assert response.json()['value'] == expected


def test_invalid_candidate_and_legacy_confirmed_value_cannot_bypass_validation(admin):
    mid = demo(admin)
    result = admin.post('/api/intake/text',json={'matter_id':mid,'text':'Buyer email: invalid-address'})
    assert result.status_code == 200
    candidate = next(c for f in fields(admin,mid) if f['key']=='buyer_email'
                     for c in f['candidates'] if c['value']=='invalid-address')
    assert admin.post(f'/api/matters/{mid}/fields/buyer_email/confirm',json={'candidate_id':candidate['id']}).status_code == 422
    confirm_required(admin,mid)
    with db(write=True) as conn:
        conn.execute("UPDATE field_reviews SET value='not money' WHERE matter_id=? AND field_key='purchase_price'",(mid,))
    assert not admin.get('/api/matters/'+mid).json()['ready_for_approval']
    assert admin.post(f'/api/matters/{mid}/approve').status_code == 422


def test_complete_correction_history_survives_clear_and_new_intake(admin):
    mid='matter-demo-intake'
    url=f'/api/matters/{mid}/fields/buyer_name'
    for value,note in [('First Manual Name','First note'),('Second Manual Name','Second note')]:
        assert admin.post(url+'/confirm',json={'value':value,'note':note}).status_code == 200
    assert admin.post(url+'/clear').status_code == 200
    original = next(f for f in fields(admin,mid) if f['key']=='buyer_name')['candidates'][0]
    assert admin.post(url+'/confirm',json={'candidate_id':original['id'],'note':'Original source checked'}).status_code == 200
    reviewed = next(f for f in fields(admin,mid) if f['key']=='buyer_name')
    assert reviewed['review_candidate_id'] == original['id']
    assert reviewed['reviewer_id'] == 'usr-keller-admin'
    assert admin.post('/api/intake/text',json={'matter_id':mid,'text':'Buyer: Updated Name'}).status_code == 200
    events = admin.get('/api/audit',params={'matter_id':mid}).json()['events']
    confirmations = [json.loads(e['details_json']) for e in events if e['action']=='field_confirmed']
    second = next(e for e in confirmations if e['review']['value']=='Second Manual Name')
    assert second['previous']['value'] == 'First Manual Name'
    assert second['previous']['note'] == 'First note'
    assert second['review']['note'] == 'Second note'
    cleared = next(json.loads(e['details_json']) for e in events if e['action']=='field_unconfirmed')
    assert cleared['previous']['value'] == 'Second Manual Name'
    invalidation = next(json.loads(e['details_json']) for e in events if e['action']=='reviews_invalidated')
    assert invalidation['previous_reviews'][0]['candidate_id'] == original['id']


@pytest.mark.parametrize('change',['reopen','intake','mapping'])
def test_old_exports_are_marked_and_download_blocked_after_changes(admin,change):
    mid=demo(admin);confirm_required(admin,mid)
    assert admin.post(f'/api/matters/{mid}/approve').status_code == 200
    exported=admin.post(f'/api/matters/{mid}/exports',json={'format':'json'}).json()
    assert admin.get(exported['download_url']).status_code == 200
    if change=='reopen':
        response=admin.post(f'/api/matters/{mid}/reopen')
    elif change=='intake':
        response=admin.post('/api/intake/text',json={'matter_id':mid,'text':'Buyer: New Name'})
    else:
        response=admin.put('/api/settings/mappings',json={'mappings':{'buyer_name':'Custom.Buyer.Name'}})
    assert response.status_code == 200
    assert admin.get(exported['download_url']).status_code == 409
    assert admin.get('/api/matters/'+mid).json()['matter']['status']=='in_review'
    row=next(e for e in admin.get('/api/exports').json()['exports'] if e['id']==exported['id'])
    assert row['invalidated_at'] and row['invalidation_reason']


def test_export_preview_matches_selected_connector(admin):
    mid=demo(admin);confirm_required(admin,mid)
    assert admin.post(f'/api/matters/{mid}/approve').status_code == 200
    preview=admin.get(f'/api/matters/{mid}/export/preview?connector=notary_demo').json()['preview']
    output=admin.post(f'/api/matters/{mid}/exports',json={'format':'json','connector':'notary_demo'}).json()
    assert json.loads(preview)==admin.get(output['download_url']).json()


def test_malformed_second_file_keeps_documents_reviews_files_and_audit_unchanged(admin):
    mid='matter-demo-intake';confirm_required(admin,mid)
    before=admin.get('/api/matters/'+mid).json()
    audit=admin.get('/api/audit').json()
    files=set(data_dir().rglob('*'))
    response=admin.post('/api/intake/upload',data={'matter_id':mid},files=[
        ('files',('good.txt',b'Buyer: New Name','text/plain')),
        ('files',('broken.pdf',b'not a pdf','application/pdf'))])
    assert response.status_code==422
    assert admin.get('/api/matters/'+mid).json()==before
    assert admin.get('/api/audit').json()==audit
    assert set(data_dir().rglob('*'))==files


def test_storage_failure_rolls_back_entire_batch(admin,monkeypatch):
    mid='matter-demo-intake';confirm_required(admin,mid)
    before=admin.get('/api/matters/'+mid).json()
    original=Path.open
    count=0
    def fail_second(path,*args,**kwargs):
        nonlocal count
        if args and args[0]=='xb':
            count+=1
            if count==2: raise OSError('Simulated storage failure')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',fail_second)
    before_files=set(p for p in data_dir().rglob('*') if p.is_file())
    with pytest.raises(OSError,match='Simulated'):
        admin.post('/api/intake/upload',data={'matter_id':mid},files=[
            ('files',('first.txt',b'Buyer: One Name','text/plain')),
            ('files',('second.txt',b'Buyer: Two Names','text/plain'))])
    assert admin.get('/api/matters/'+mid).json()==before
    assert set(p for p in data_dir().rglob('*') if p.is_file())==before_files


def test_email_html_and_supported_attachments_are_extracted(admin):
    message=EmailMessage();message['Subject']='Synthetic intake'
    message.set_content('<html><head><style>hidden</style></head><body><p>Buyer: HTML Buyer</p><script>Buyer: Hidden</script></body></html>',subtype='html')
    message.add_attachment(Path('samples/07_synthetic_property_purchase.pdf').read_bytes(),maintype='application',subtype='pdf',filename='buyer.pdf')
    message.add_attachment(b'not processed',maintype='application',subtype='zip',filename='archive.zip')
    result=admin.post('/api/intake/upload',data={'matter_id':'matter-demo-intake'},files={
        'files':('synthetic.eml',message.as_bytes(),'message/rfc822')})
    assert result.status_code==200,result.text
    doc=admin.get('/api/documents/'+result.json()['results'][0]['document_id']).json()
    assert 'Buyer: HTML Buyer' in doc['raw_text']
    assert 'Emilia Roth' in doc['raw_text']
    assert 'Buyer: Hidden' not in doc['raw_text']
    assert any('archive.zip' in note for note in doc['warnings'])
    assert doc['warnings']==result.json()['results'][0]['warnings']


def test_hybrid_pdf_runs_ocr_for_scanned_page_only(monkeypatch):
    import pytesseract
    seen=[]
    def ocr(image,**kwargs):
        seen.append(image.size)
        return 'Buyer: From scanned page'
    monkeypatch.setattr(pytesseract,'image_to_string',ocr)
    writer=PdfWriter();writer.append('samples/07_synthetic_property_purchase.pdf')
    writer.add_blank_page(width=612,height=792)
    raw=io.BytesIO();writer.write(raw)
    text,warnings=parse_document('hybrid.pdf',raw.getvalue())
    assert 'Emilia Roth' in text and 'From scanned page' in text
    assert len(seen)==1
    assert any('page 2' in note for note in warnings)


def test_all_tiff_frames_processed_and_failures_identified(monkeypatch):
    import pytesseract
    seen=[]
    def ocr(image,**kwargs):
        seen.append(image.tell())
        if image.tell()==1: raise RuntimeError('OCR unavailable')
        return 'Buyer: Frame '+str(image.tell())
    monkeypatch.setattr(pytesseract,'image_to_string',ocr)
    raw=io.BytesIO()
    Image.new('RGB',(20,20),'white').save(raw,format='TIFF',save_all=True,append_images=[Image.new('RGB',(20,20),'black'),Image.new('RGB',(20,20),'red')])
    text,warnings=parse_document('pages.tiff',raw.getvalue())
    assert seen==[0,1,2]
    assert 'Frame 0' in text and 'Frame 2' in text
    assert any('frame 2' in note for note in warnings)


def test_truncated_text_is_explicit():
    text,warnings=parse_document('long.txt',b'a'*200001)
    assert len(text)==200000
    assert any('remaining content' in note for note in warnings)


def test_demo_scope_csrf_and_cross_tenant_download(api_client):
    assert api_client.post('/api/demo/start').status_code==401
    sign_in(api_client);mid=demo(api_client);confirm_required(api_client,mid)
    api_client.post(f'/api/matters/{mid}/approve')
    exported=api_client.post(f'/api/matters/{mid}/exports',json={'format':'json'}).json()
    sign_in(api_client,'admin@weber.demo')
    assert api_client.get('/api/matters/'+mid).status_code==404
    assert api_client.get(exported['download_url']).status_code==404
    api_client.headers.pop('X-CSRF-Token')
    assert api_client.post('/api/demo/start').status_code==403
