"""Pilot evidence with explicit denominators and reported-time provenance."""
import csv
import io
import json
import uuid
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from typing import Literal
from .auth import require_user, minimum_role
from .db import db, record_audit, utcnow
from .extraction import SCHEMAS, comparison_value
from .settings import seed_demo_enabled

router = APIRouter(prefix="/api/pilot", tags=["Pilot measurement"])


class Baseline(BaseModel):
    matter_type: str
    minutes: float = Field(gt=0, le=480, allow_inf_nan=False)
    sample_size: int = Field(ge=1, le=10000)


class Observation(BaseModel):
    matter_id: str
    seconds: int = Field(ge=1, le=28800)
    source: Literal["manual", "timer"] = "manual"
    idempotency_key: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=8, max_length=100)


def percent(numerator, denominator):
    return round(numerator / denominator * 100, 1) if denominator else None


def measurement(conn, tenant, matter_type):
    if matter_type not in SCHEMAS:
        raise HTTPException(422, "Unknown matter type")
    matters = conn.execute("SELECT * FROM matters WHERE tenant_id=? AND matter_type=?", (tenant, matter_type)).fetchall()
    eligible = [m for m in matters if conn.execute("SELECT 1 FROM documents WHERE matter_id=? AND tenant_id=?", (m["id"], tenant)).fetchone()]
    schema = SCHEMAS[matter_type]
    required, extracted, reviewed, corrections, candidate_fields, low_confidence = 0, 0, 0, 0, 0, 0
    expected, recorded = 0, 0
    for matter in eligible:
        mid = matter["id"]
        grouped = {}
        for candidate in conn.execute("SELECT * FROM candidates WHERE matter_id=? AND tenant_id=?", (mid, tenant)):
            grouped.setdefault(candidate["field_key"], []).append(candidate)
        required += len(schema["required"])
        extracted += sum(bool(grouped.get(field)) for field in schema["required"])
        for field in schema["required"] + schema["optional"]:
            options = grouped.get(field, [])
            if options:
                candidate_fields += 1
                low_confidence += max(c["confidence"] for c in options) < .9
        events = [(e["action"], json.loads(e["details_json"])) for e in conn.execute("SELECT action,details_json FROM audit WHERE matter_id=? AND tenant_id=?", (mid, tenant))]
        for review in conn.execute("SELECT * FROM field_reviews WHERE matter_id=? AND tenant_id=?", (mid, tenant)):
            reviewed += 1
            corrections += not any(comparison_value(review["field_key"], c["value"]) == comparison_value(review["field_key"], review["value"]) for c in grouped.get(review["field_key"], []))
            expected += 1
            recorded += any(action == "field_confirmed" and detail.get("field") == review["field_key"]
                            and detail.get("review", {}).get("value") == review["value"] for action, detail in events)
        for doc in conn.execute("SELECT id FROM documents WHERE matter_id=? AND tenant_id=?", (mid, tenant)):
            expected += 1
            recorded += any(action == "document_ingested" and detail.get("document_id") == doc["id"] for action, detail in events)
        if matter["approved_at"]:
            expected += 1
            recorded += any(action == "matter_approved" for action, _ in events)
        for export in conn.execute("SELECT id FROM exports WHERE matter_id=? AND tenant_id=?", (mid, tenant)):
            expected += 1
            recorded += any(action == "approved_export_generated" and detail.get("export_id") == export["id"] for action, detail in events)
    baseline = conn.execute("SELECT * FROM pilot_baselines WHERE tenant_id=? AND matter_type=?", (tenant, matter_type)).fetchone()
    observations = conn.execute("""SELECT o.*,m.reference FROM pilot_observations o JOIN matters m ON m.id=o.matter_id
                                   WHERE o.tenant_id=? AND m.matter_type=? ORDER BY o.rowid DESC""", (tenant, matter_type)).fetchall()
    per_matter = {}
    for obs in observations:
        per_matter[obs["matter_id"]] = per_matter.get(obs["matter_id"], 0) + obs["seconds"]
    pilot_minutes = sum(per_matter.values()) / len(per_matter) / 60 if per_matter else None
    transfers = [dict(r) for r in conn.execute("""SELECT t.connector,t.status,COUNT(*) AS count FROM integration_transfers t
                            JOIN matters m ON m.id=t.matter_id WHERE t.tenant_id=? AND m.matter_type=? GROUP BY t.connector,t.status""", (tenant, matter_type))]
    transfer_rates = []
    for connector in ("demo_receiver", "webhook"):
        total = sum(r["count"] for r in transfers if r["connector"] == connector)
        accepted = sum(r["count"] for r in transfers if r["connector"] == connector and r["status"] == "accepted")
        transfer_rates.append({"connector": connector, "accepted": accepted, "total": total, "percent": percent(accepted, total), "simulated": connector == "demo_receiver"})
    return {"matter_type": matter_type, "eligible_matters": len(eligible), "baseline": dict(baseline) if baseline else None,
            "pilot_minutes": round(pilot_minutes, 2) if pilot_minutes is not None else None, "timed_matters": len(per_matter),
            "time_saved_percent": round((baseline["minutes"] - pilot_minutes) / baseline["minutes"] * 100, 1) if baseline and pilot_minutes is not None else None,
            "coverage": {"numerator": extracted, "denominator": required, "percent": percent(extracted, required)},
            "corrections": {"numerator": corrections, "denominator": reviewed, "percent": percent(corrections, reviewed)},
            "low_confidence": {"numerator": low_confidence, "denominator": candidate_fields, "percent": percent(low_confidence, candidate_fields)},
            "audit_coverage": {"numerator": recorded, "denominator": expected, "percent": percent(recorded, expected)},
            "transfers": transfer_rates, "observations": [dict(o) for o in observations[:100]],
            "definitions": {"coverage": "Required fields with at least one candidate / required fields in matters with documents",
                "corrections": "Current confirmations that differ from every candidate, including manual missing-field entries / current confirmations",
                "low_confidence": "Fields whose highest candidate heuristic is below 0.90 / fields with candidates",
                "audit_coverage": "Expected intake, current field review, approval and file export activities with a matching event / expected activities; seeded historical fixtures may have gaps",
                "time": "Reported work sessions summed per matter, then averaged. Baseline is operator supplied; time savings are indicative, not independently validated.",
                "transfers": "Accepted unique transfer keys / unique transfer keys, separated by simulated and HTTPS destinations"}}


@router.get("")
def summary(matter_type: str = "property_purchase", user=Depends(require_user)):
    with db() as conn:
        return measurement(conn, user["tenant_id"], matter_type)


@router.put("/baseline")
def baseline(data: Baseline, user=Depends(minimum_role("admin"))):
    if data.matter_type not in SCHEMAS:
        raise HTTPException(422, "Unknown matter type")
    with db(write=True) as conn:
        conn.execute("""INSERT INTO pilot_baselines VALUES(?,?,?,?,?) ON CONFLICT(tenant_id,matter_type)
                        DO UPDATE SET minutes=excluded.minutes,sample_size=excluded.sample_size,updated_at=excluded.updated_at""",
                     (user["tenant_id"], data.matter_type, data.minutes, data.sample_size, utcnow()))
        record_audit(conn, user["tenant_id"], None, user["id"], "pilot_baseline_updated", data.model_dump())
    return {"ok": True}


@router.post("/observations")
def observation(data: Observation, user=Depends(require_user)):
    digest = hashlib.sha256(json.dumps({"matter_id": data.matter_id, "seconds": data.seconds, "source": data.source}, sort_keys=True).encode()).hexdigest()
    with db(write=True) as conn:
        if not conn.execute("SELECT 1 FROM matters WHERE id=? AND tenant_id=?", (data.matter_id, user["tenant_id"])).fetchone():
            raise HTTPException(404, "Matter not found")
        previous = conn.execute("SELECT payload_hash FROM pilot_observation_keys WHERE tenant_id=? AND idempotency_key=?", (user["tenant_id"], data.idempotency_key)).fetchone()
        if previous:
            if previous["payload_hash"] != digest:
                raise HTTPException(409, "Time observation key was used for different values")
            return {"ok": True, "replayed": True}
        conn.execute("INSERT INTO pilot_observation_keys VALUES(?,?,?)", (user["tenant_id"], data.idempotency_key, digest))
        conn.execute("INSERT INTO pilot_observations VALUES(?,?,?,?,?,?,?)", (uuid.uuid4().hex, user["tenant_id"], data.matter_id, data.seconds, data.source, user["id"], utcnow()))
        record_audit(conn, user["tenant_id"], data.matter_id, user["id"], "pilot_time_recorded", {"seconds": data.seconds, "source": data.source})
    return {"ok": True}


@router.get("/report.csv")
def report(matter_type: str = "property_purchase", user=Depends(require_user)):
    with db() as conn:
        data = measurement(conn, user["tenant_id"], matter_type)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value", "numerator", "denominator", "definition"])
    for key in ("coverage", "corrections", "low_confidence", "audit_coverage"):
        row = data[key]
        writer.writerow([key, row["percent"], row["numerator"], row["denominator"], data["definitions"][key]])
    for key in ("pilot_minutes", "timed_matters", "time_saved_percent"):
        writer.writerow([key, data[key], "", "", data["definitions"]["time"]])
    writer.writerow(["baseline_minutes", data["baseline"]["minutes"] if data["baseline"] else "", "", data["baseline"]["sample_size"] if data["baseline"] else "", "Operator-supplied average and sample size"])
    for row in data["transfers"]:
        writer.writerow([row["connector"] + "_acceptance_percent", row["percent"], row["accepted"], row["total"], data["definitions"]["transfers"]])
    return Response("\ufeff" + output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="lexflow-pilot-report.csv"'})
