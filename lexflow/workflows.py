"""Versioned literal-label rules. Examples are previewed, never persisted as training data."""
import json
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .auth import require_user, minimum_role
from .db import db, record_audit, utcnow
from .extraction import SCHEMAS, clean_value, comparison_value
from .validation import validate_field_value

router = APIRouter(prefix="/api/workflows", tags=["Workflow learning"])


class Rule(BaseModel):
    matter_type: str
    field_key: str
    label: str = Field(min_length=2, max_length=80)
    enabled: bool = True


class Preview(Rule):
    sample_text: str = Field(min_length=1, max_length=20000)


class Toggle(BaseModel):
    enabled: bool
    expected_version: int = Field(ge=1)


def validate_rule(rule):
    schema = SCHEMAS.get(rule.matter_type)
    if not schema or rule.field_key not in schema["required"] + schema["optional"]:
        raise HTTPException(422, "Choose a field in the selected matter schema")
    label = rule.label.strip()
    if len(label) < 2 or any(c in label for c in "\n\r:="):
        raise HTTPException(422, "Use a short field label without a colon, equals sign or line break")
    return label


def extract_rule(text, field, label, origin="workflow_preview"):
    results = []
    # Labels are escaped literals. Administrators cannot introduce arbitrary regex.
    pattern = r"(?<!\w)" + re.escape(label) + r"\s*[:=]\s*([^\n;]+)"
    for match in list(re.finditer(pattern, text[:200000], re.IGNORECASE))[:8]:
        try:
            value = validate_field_value(field, clean_value(field, match.group(1)))
        except ValueError:
            continue
        results.append({"field_key": field, "value": value, "confidence": .85,
                        "evidence": text[max(0, match.start()-20):match.end()+40][:260], "origin": origin})
    return results


def apply_rules(conn, tenant, matter_type, text, existing):
    seen = {(c["field_key"], comparison_value(c["field_key"], c["value"])) for c in existing}
    for rule in conn.execute("SELECT * FROM workflow_rules WHERE tenant_id=? AND matter_type=? AND enabled=1", (tenant, matter_type)):
        for candidate in extract_rule(text, rule["field_key"], rule["label"], f"workflow_rule:{rule['id']}:v{rule['version']}"):
            marker = (candidate["field_key"], comparison_value(candidate["field_key"], candidate["value"]))
            if marker not in seen:
                existing.append(candidate)
                seen.add(marker)
    return existing


@router.get("")
def rules(user=Depends(require_user)):
    with db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM workflow_rules WHERE tenant_id=? ORDER BY updated_at DESC,rowid DESC", (user["tenant_id"],))]
    return {"rules": rows, "policy": "All learned suggestions require human review; example text is never stored as a rule."}


@router.post("/preview")
def preview(data: Preview, user=Depends(minimum_role("reviewer"))):
    label = validate_rule(data)
    return {"candidates": extract_rule(data.sample_text, data.field_key, label), "sample_stored": False}


def save_version(conn, user, rule_id, config, version):
    conn.execute("INSERT INTO workflow_versions VALUES(?,?,?,?,?,?)", (uuid.uuid4().hex, rule_id, version,
                 json.dumps(config, sort_keys=True), user["id"], utcnow()))
    record_audit(conn, user["tenant_id"], None, user["id"], "workflow_rule_updated",
                 {"rule_id": rule_id, "version": version, "configuration": config})


@router.post("")
def create_rule(data: Rule, user=Depends(minimum_role("admin"))):
    label = validate_rule(data)
    rule_id = uuid.uuid4().hex
    with db(write=True) as conn:
        if conn.execute("SELECT 1 FROM workflow_rules WHERE tenant_id=? AND matter_type=? AND field_key=? AND lower(label)=lower(?)",
                        (user["tenant_id"], data.matter_type, data.field_key, label)).fetchone():
            raise HTTPException(409, "This rule already exists; enable or disable the saved version")
        count = conn.execute("SELECT COUNT(*) FROM workflow_rules WHERE tenant_id=?", (user["tenant_id"],)).fetchone()[0]
        if count >= 100:
            raise HTTPException(422, "Maximum 100 learned rules per workspace")
        conn.execute("INSERT INTO workflow_rules VALUES(?,?,?,?,?,?,?,?,?)", (rule_id, user["tenant_id"], data.matter_type,
                     data.field_key, label, int(data.enabled), 1, user["id"], utcnow()))
        save_version(conn, user, rule_id, {"matter_type": data.matter_type, "field_key": data.field_key, "label": label, "enabled": data.enabled}, 1)
    return {"id": rule_id, "version": 1}


@router.patch("/{rule_id}")
def toggle_rule(rule_id: str, data: Toggle, user=Depends(minimum_role("admin"))):
    with db(write=True) as conn:
        rule = conn.execute("SELECT * FROM workflow_rules WHERE id=? AND tenant_id=?", (rule_id, user["tenant_id"])).fetchone()
        if not rule:
            raise HTTPException(404, "Rule not found")
        if rule["version"] != data.expected_version:
            raise HTTPException(409, "This rule changed. Refresh before editing")
        version = rule["version"] + 1
        conn.execute("UPDATE workflow_rules SET enabled=?,version=?,updated_at=? WHERE id=?", (int(data.enabled), version, utcnow(), rule_id))
        config = {k: rule[k] for k in ("matter_type", "field_key", "label")}
        save_version(conn, user, rule_id, config | {"enabled": data.enabled}, version)
    return {"ok": True, "version": version}


@router.get("/{rule_id}/versions")
def versions(rule_id: str, user=Depends(require_user)):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM workflow_rules WHERE id=? AND tenant_id=?", (rule_id, user["tenant_id"])).fetchone():
            raise HTTPException(404, "Rule not found")
        return {"versions": [dict(r) for r in conn.execute("SELECT version,configuration_json,actor_id,created_at FROM workflow_versions WHERE rule_id=? ORDER BY version DESC", (rule_id,))]}
