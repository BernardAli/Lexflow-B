import copy
import hashlib
import json

import pytest

from lexflow.case_models import CaseData
from lexflow.connectors import canonical_bytes
from lexflow.db import db, initialize
from tests.conftest import sign_in

MID = "matter-demo-intake"


def checked(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def case_path(mid=MID):
    return f"/api/matters/{mid}/case-data"


def case_fixture(client):
    detail = checked(client.get(f"/api/matters/{MID}"))
    doc = detail["documents"][0]["id"]
    return {
        "category": "property_transaction", "designation": "Fictional seller/buyers KV", "naming_code": "KV",
        "participants": [
            {"id": "buyer-1", "roles": ["buyer"], "name": "Synthetic Buyer One", "short_name": "Buyer One",
             "birth_date": "1990-01-02", "source_document_ids": [doc]},
            {"id": "buyer-2", "roles": ["buyer", "representative"], "name": "Synthetic Buyer Two", "source_document_ids": [doc]},
            {"id": "seller-company", "entity_type": "company", "roles": ["seller"], "name": "Example Test GmbH",
             "legal_form": "GmbH", "register_court": "Example Court", "register_number": "HRB TEST",
             "representative_ids": ["buyer-2"], "source_note": "Synthetic company example for testing"}],
        "properties": [
            {"id": "property-1", "land_register": "Example district", "sheet": "001", "parcel": "04/5",
             "ownership_share": "1/2", "source_document_ids": [doc]},
            {"id": "property-2", "address": {"street": "Example Street 2"}, "area_sqm": "120.50",
             "source_document_ids": [doc]}],
        "tasks": [{"id": "task-1", "title": "Request missing questionnaire", "status": "pending", "due_date": "2026-11-02"}]
    }


def confirm_fields(client):
    detail = checked(client.get(f"/api/matters/{MID}"))
    for field in detail["fields"]:
        if field["required"]:
            checked(client.post(f"/api/matters/{MID}/fields/{field['key']}/confirm",
                                json={"candidate_id": field["candidates"][0]["id"]}))


def prepared_case(client):
    confirm_fields(client)
    return checked(client.put(case_path(), json={"expected_revision": 0, "data": case_fixture(client)}))


def test_structured_case_approval_export_and_reopen(admin):
    state = prepared_case(admin)
    assert state["revision"] == 1 and state["reviewed_at"] is None
    assert state["suggested_designation"] == "Example Test GmbH/Buyer One/Synthetic Buyer Two KV"
    detail = checked(admin.get(f"/api/matters/{MID}"))
    assert not detail["ready_for_approval"] and "structured" in detail["approval_blockers"][0]
    checked(admin.post(f"/api/matters/{MID}/approve"), 422)
    checked(admin.post(case_path()+"/review", json={"expected_revision": 1}))
    assert checked(admin.get(f"/api/matters/{MID}"))["ready_for_approval"]
    checked(admin.post(f"/api/matters/{MID}/approve"))
    preview = checked(admin.get(f"/api/matters/{MID}/export/preview?connector=case_bundle"))
    result = checked(admin.post(f"/api/matters/{MID}/exports", json={"connector": "case_bundle"}))
    bundle = checked(admin.get(result["download_url"]))
    assert bundle == json.loads(preview["preview"])
    assert bundle["not_a_live_transmission"] and not bundle["vendor_import_verified"]
    snapshot = bundle["snapshot"]
    assert snapshot["schema"] == "lexflow-case-v1"
    assert len(snapshot["case_data"]["participants"]) == 3
    assert len(snapshot["case_data"]["properties"]) == 2
    assert snapshot["case_data"]["participants"][2]["representative_ids"] == ["buyer-2"]
    assert snapshot["documents"][0]["sha256"]
    assert "file_path" not in snapshot["documents"][0]
    assert snapshot["field_reviews"][0]["document_id"]
    assert bundle["snapshot_sha256"] == hashlib.sha256(canonical_bytes(snapshot)).hexdigest()
    checked(admin.put(case_path(), json={"expected_revision": 1, "data": state["data"]}), 409)
    checked(admin.post(f"/api/matters/{MID}/reopen"))
    checked(admin.get(result["download_url"]), 409)
    reopened = checked(admin.get(case_path()))
    assert reopened["revision"] == 2 and reopened["reviewed_at"] is None
    actions = {e["action"] for e in checked(admin.get(f"/api/audit?matter_id={MID}"))["events"]}
    assert {"case_details_saved", "case_details_reviewed", "case_review_invalidated"} <= actions


def test_case_revision_conflicts_keep_stale_edits_out(admin):
    state = prepared_case(admin)
    changed = copy.deepcopy(state["data"])
    changed["designation"] = "New name"
    checked(admin.put(case_path(), json={"expected_revision": 1, "data": changed}))
    checked(admin.put(case_path(), json={"expected_revision": 1, "data": state["data"]}), 409)
    checked(admin.post(case_path()+"/review", json={"expected_revision": 1}), 409)
    assert checked(admin.get(case_path()))["data"]["designation"] == "New name"


@pytest.mark.parametrize("mutation", ["source", "field", "clear"])
def test_changes_invalidate_case_review(admin, mutation):
    prepared_case(admin)
    checked(admin.post(case_path()+"/review", json={"expected_revision": 1}))
    if mutation == "source":
        checked(admin.post("/api/intake/text", json={"matter_id": MID, "text": "Additional synthetic source information"}))
    elif mutation == "field":
        checked(admin.post(f"/api/matters/{MID}/fields/buyer_name/confirm", json={"value": "Changed Synthetic Buyer"}))
    else:
        checked(admin.post(f"/api/matters/{MID}/fields/buyer_name/clear"))
    state = checked(admin.get(case_path()))
    assert state["revision"] == 2 and state["reviewed_at"] is None
    checked(admin.post(case_path()+"/review", json={"expected_revision": 1}), 409)


def test_case_isolation_roles_and_csrf(admin):
    payload = {"expected_revision": 0, "data": case_fixture(admin)}
    checked(admin.put(case_path("matter-other-tenant"), json=payload), 404)
    checked(admin.get(case_path("matter-other-tenant")), 404)
    payload["data"]["master_matter_id"] = "matter-other-tenant"
    checked(admin.put(case_path(), json=payload), 404)
    payload["data"].pop("master_matter_id")
    sign_in(admin, "assistant@keller.demo")
    checked(admin.put(case_path(), json=payload))
    checked(admin.post(case_path()+"/review", json={"expected_revision": 1}), 403)
    admin.headers.pop("X-CSRF-Token")
    checked(admin.put(case_path(), json={"expected_revision": 1, "data": payload["data"]}), 403)
    sign_in(admin, "admin@weber.demo")
    checked(admin.get(case_path()), 404)


def test_sources_and_parent_cycles_are_validated(admin):
    data = case_fixture(admin)
    other = checked(admin.get("/api/matters/matter-demo-company"))["documents"][0]["id"]
    data["participants"][0]["source_document_ids"] = [other]
    checked(admin.put(case_path(), json={"expected_revision": 0, "data": data}), 422)
    data = case_fixture(admin)
    data["master_matter_id"] = MID
    checked(admin.put(case_path(), json={"expected_revision": 0, "data": data}), 422)
    data["master_matter_id"] = "matter-demo-company"
    checked(admin.put(case_path(), json={"expected_revision": 0, "data": data}))
    checked(admin.put(case_path("matter-demo-company"), json={"expected_revision": 0, "data": {"master_matter_id": MID}}), 422)


def test_case_review_requires_provenance_and_a_document(admin):
    data = {"participants": [{"id": "p1", "roles": ["client"], "name": "Synthetic Person"}]}
    checked(admin.put(case_path(), json={"expected_revision": 0, "data": data}))
    checked(admin.post(case_path()+"/review", json={"expected_revision": 1}), 422)
    checked(admin.put(case_path("matter-demo-empty"), json={"expected_revision": 0, "data": {}}))
    checked(admin.post(case_path("matter-demo-empty")+"/review", json={"expected_revision": 1}), 422)


@pytest.mark.parametrize("invalid", [
    {"schema_version": 2}, {"unexpected_vendor_field": "unverified"},
    {"participants": [{"id": "a", "roles": ["buyer"], "name": "Person", "birth_date": "2026-02-30"}]},
    {"participants": [{"id": "a", "roles": ["buyer"], "name": "Person", "email": "not-an-email"}]},
    {"participants": [{"id": "a", "roles": ["buyer"], "name": "Person", "representative_ids": ["missing"]}]},
    {"participants": [{"id": "a", "roles": ["seller"], "name": "Company", "entity_type": "company", "birth_name": "Wrong"}]},
    {"properties": [{"id": "p", "parcel": "01", "ownership_share": "2/1"}]},
    {"properties": [{"id": "p", "parcel": "01", "ownership_share": "1/0"}]},
    {"properties": [{"id": "p", "parcel": "01", "area_sqm": "-5"}]},
    {"properties": [{"id": "p"}]},
    {"tasks": [{"id": "t", "title": "Task"}, {"id": "t", "title": "Duplicate"}]},
    {"designation": "Hidden\ncontrol"},
])
def test_case_schema_rejects_invalid_records(invalid):
    with pytest.raises(ValueError):
        CaseData.model_validate(invalid)


def test_adapters_are_explicit_about_formats_and_latest_version(admin):
    catalog = checked(admin.get("/api/connectors"))
    vendor = next(c for c in catalog["connectors"] if c["id"] == "pronotar32")
    assert vendor["version_policy"] == "latest_vendor_supported" and vendor["verified_version"] is None
    assert vendor["status"] == "specification_required" and vendor["formats"] == []
    assert not vendor["live"] and not vendor["import_verified"]
    path = "/api/matters/matter-demo-finished"
    before = len(checked(admin.get("/api/exports"))["exports"])
    checked(admin.get(path+"/export/preview?connector=pronotar32"), 409)
    checked(admin.post(path+"/exports", json={"connector": "pronotar32"}), 409)
    checked(admin.post(path+"/exports", json={"connector": "case_bundle", "format": "csv"}), 422)
    assert len(checked(admin.get("/api/exports"))["exports"]) == before
    bundle = json.loads(checked(admin.get(path+"/export/preview?connector=case_bundle"))["preview"])
    assert bundle["snapshot"]["case_data"] is None
    assert checked(admin.get("/api/case-data/schema"))["additionalProperties"] is False


def test_additive_schema_upgrade_preserves_legacy_cases_and_new_records(admin):
    legacy = checked(admin.get("/api/matters/matter-demo-finished"))
    with db(write=True) as conn:
        conn.execute("DROP TABLE matter_case_data")
    initialize()
    assert checked(admin.get("/api/matters/matter-demo-finished")) == legacy
    state = prepared_case(admin)
    initialize()
    assert checked(admin.get(case_path())) == state


def test_case_data_survives_authenticated_backup_restore(admin, tmp_path, monkeypatch):
    from lexflow.snapshots import backup, restore
    state = prepared_case(admin)
    backup(tmp_path / "backup")
    restore(tmp_path / "backup", tmp_path / "restored")
    monkeypatch.setenv("LEXFLOW_DATA_DIR", str(tmp_path / "restored"))
    sign_in(admin)
    assert checked(admin.get(case_path())) == state
