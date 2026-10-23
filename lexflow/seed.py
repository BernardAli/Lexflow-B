"""Self-contained synthetic demonstration data; no real person or client records."""
from pathlib import Path
from uuid import uuid4
from hashlib import sha256
from .settings import PROJECT_ROOT, data_dir, seed_demo_enabled
from .db import db, utcnow, record_audit
from .auth import hash_password
from .extraction import rule_extract
from .exporter import DEFAULT_MAPPINGS, generate_export

DEMO_PASSWORD = "LexFlowDemo2026!"


def seed_if_empty():
    if not seed_demo_enabled():
        return
    with db() as conn:
        if conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]:
            return
        now = utcnow()
        t1, t2 = "tenant-keller-demo", "tenant-weber-demo"
        conn.executemany("INSERT INTO tenants VALUES(?,?,?)", [(t1, "Notariat Keller — Munich", now), (t2, "Notariat Weber — Berlin", now)])
        users = [
          ("usr-keller-admin",t1,"admin@keller.demo","Alex Keller","admin"),
          ("usr-keller-reviewer",t1,"reviewer@keller.demo","Marie Hoffmann","reviewer"),
          ("usr-keller-analyst",t1,"assistant@keller.demo","Jonas Becker","analyst"),
          ("usr-weber-admin",t2,"admin@weber.demo","Sophie Weber","admin"),
        ]
        pwhash = hash_password(DEMO_PASSWORD)
        conn.executemany("INSERT INTO users VALUES(?,?,?,?,?,?,?)",
                         [(user_id, tid, email, name, role, pwhash, now) for user_id, tid, email, name, role in users])
        for tid in (t1, t2):
            conn.executemany("INSERT INTO connector_mappings VALUES(?,?,?)",
                [(tid, field, target) for field, target in DEFAULT_MAPPINGS.items()])
        examples = [
          ("matter-demo-conflict",t1,"2026-KEL-0041","Sonnenallee 24 — Property purchase","property_purchase","in_review",["01_buyer_questionnaire.txt", "02_land_register_conflict.txt"]),
          ("matter-demo-intake",t1,"2026-KEL-0042","Lindenstraße 12 — Property purchase","property_purchase","in_review",["03_property_intake.txt"]),
          ("matter-demo-finished",t1,"2026-KEL-0039","Gartenweg 8 — Property transfer","property_purchase","exported",["04_approved_example.txt"]),
          ("matter-demo-company",t1,"2026-KEL-0043","Elbe Analytics GmbH — Incorporation","company_formation","in_review",["05_company_formation.txt"]),
          ("matter-demo-empty",t1,"2026-KEL-0044","New inheritance matter","inheritance","new",[]),
          ("matter-other-tenant",t2,"2026-WEB-0018","Confidential matter — separate workspace","property_purchase","new",[]),
        ]
        for mid, tid, reference, title, matter_type, status, files in examples:
            approved = now if status == "exported" else None
            reviewer = "usr-keller-reviewer" if approved else None
            conn.execute("INSERT INTO matters VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (mid, tid, reference, title, matter_type, status, now, now, reviewer, approved))
            for fname in files:
                content = (PROJECT_ROOT / "samples" / fname).read_bytes()
                text_content = content.decode("utf-8")
                doc_id = uuid4().hex
                target_dir = data_dir() / "uploads" / tid / mid
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / f"{doc_id}.txt"
                target.write_bytes(content)
                conn.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)",
                             (doc_id, tid, mid, fname, "text/plain", len(content), sha256(content).hexdigest(), text_content, str(target), now))
                for item in rule_extract(text_content, matter_type):
                    conn.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (uuid4().hex,tid,mid,doc_id,item["field_key"],item["value"],item["confidence"],item["evidence"],item["origin"],now))
            if status == "exported":
                fields = {}
                for row in conn.execute("SELECT id,field_key,value FROM candidates WHERE matter_id=?", (mid,)).fetchall():
                    if row["field_key"] in fields:
                        continue
                    fields[row["field_key"]] = row["value"]
                    conn.execute("INSERT INTO field_reviews VALUES(?,?,?,?,?,?,?,?,?)",
                        (uuid4().hex,tid,mid,row["field_key"],row["value"],row["id"],reviewer,"approved in synthetic demo",now))
                matter = {"reference": reference, "title": title, "matter_type": matter_type, "approved_at": now}
                export_dir = data_dir() / "exports" / tid
                export_dir.mkdir(parents=True, exist_ok=True)
                export_id = uuid4().hex
                filename = f"{reference}_approved.json"
                out = export_dir / f"{export_id}.json"
                out.write_bytes(generate_export(matter, fields, DEFAULT_MAPPINGS, "notary_demo", "json"))
                conn.execute("INSERT INTO exports VALUES(?,?,?,?,?,?,?,?,?)",
                    (export_id,tid,mid,str(out),filename,"json","notary_demo","usr-keller-reviewer",now))
            record_audit(conn,tid,mid,"usr-keller-admin" if tid == t1 else "usr-weber-admin", "demo_matter_seeded", {"reference":reference,"synthetic":True})
