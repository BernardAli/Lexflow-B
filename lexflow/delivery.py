"""Durable transfer intents with bounded leases; network calls hold no DB lock."""
import json
import secrets
import time
from types import SimpleNamespace

from .db import db, record_audit, utcnow


def deliver(tenant, transfer_id):
    from .integrations import approved_payload, payload_hash, destination_target, target_hash, send_webhook
    lease = secrets.token_hex(16)
    with db(write=True) as conn:
        transfer = conn.execute("SELECT * FROM integration_transfers WHERE tenant_id=? AND id=?", (tenant, transfer_id)).fetchone()
        if not transfer:
            raise ValueError("Transfer not found in this workspace")
        result = json.loads(transfer["receipt_json"])
        if transfer["status"] == "accepted":
            return result | {"replayed": True}
        job = conn.execute("SELECT * FROM integration_jobs WHERE transfer_id=?", (transfer_id,)).fetchone()
        if not job:
            raise ValueError("No durable delivery intent exists")
        if transfer["status"] == "sending" and job["lease_until"] > int(time.time()):
            return result | {"status": "sending", "message": "This delivery is already in progress. Check its receipt shortly."}
        actor = conn.execute("SELECT role FROM users WHERE id=? AND tenant_id=?", (transfer["actor_id"], tenant)).fetchone()
        user = {"id": transfer["actor_id"], "tenant_id": tenant}
        data = SimpleNamespace(matter_id=transfer["matter_id"], connector=transfer["connector"])
        target = destination_target(tenant, transfer["connector"])
        failure = None
        try:
            payload = approved_payload(conn, user, data)
            if not actor or actor["role"] not in ("reviewer", "admin"):
                failure = "The initiating reviewer no longer has delivery access"
            elif payload_hash(payload) != transfer["payload_hash"] or json.loads(job["payload_json"]) != payload:
                failure = "Approved data changed. Preview it again and use a new transfer key"
            elif target_hash(target) != job["target_hash"]:
                failure = "The configured destination changed. Check the earlier outcome before preparing another transfer"
            elif transfer["connector"] != "demo_receiver" and target is None:
                failure = "The configured destination is unavailable"
        except Exception:
            failure = "The matter is no longer approved for this delivery"
        if failure:
            result.update(status="cancelled", message=failure)
            conn.execute("UPDATE integration_transfers SET status='cancelled',receipt_json=? WHERE id=?", (json.dumps(result), transfer_id))
            record_audit(conn, tenant, transfer["matter_id"], transfer["actor_id"], "connector_transfer_cancelled", {"transfer_id": transfer_id, "reason": failure})
            return result
        attempt = job["attempt_count"] + 1
        conn.execute("UPDATE integration_jobs SET attempt_count=?,lease_until=?,lease_token=?,updated_at=? WHERE transfer_id=?", (attempt, int(time.time()) + 120, lease, utcnow(), transfer_id))
        result.update(status="sending", attempt_count=attempt)
        conn.execute("UPDATE integration_transfers SET status='sending',receipt_json=? WHERE id=?", (json.dumps(result), transfer_id))
        record_audit(conn, tenant, transfer["matter_id"], transfer["actor_id"], "connector_delivery_started", {"transfer_id": transfer_id, "attempt": attempt})

    # The intent and lease survive a process crash before, during or after I/O.
    if transfer["connector"] == "demo_receiver":
        state, receipt = "accepted", {"receipt_id": "DEMO-" + transfer_id[:12].upper()}
    else:
        try:
            state, receipt = send_webhook(target, payload, transfer["idempotency_key"])
        except Exception:
            state, receipt = "uncertain", {"message": "Delivery was interrupted. Check the destination before retrying with the same key."}
    with db(write=True) as conn:
        current = conn.execute("SELECT j.lease_token,t.receipt_json FROM integration_jobs j JOIN integration_transfers t ON t.id=j.transfer_id WHERE j.transfer_id=?", (transfer_id,)).fetchone()
        if current["lease_token"] != lease:
            return json.loads(current["receipt_json"]) | {"message": "A newer attempt owns this delivery. Inspect its receipt."}
        result.update(receipt, status=state, updated_at=utcnow())
        conn.execute("UPDATE integration_transfers SET status=?,receipt_json=? WHERE id=?", (state, json.dumps(result), transfer_id))
        conn.execute("UPDATE integration_jobs SET lease_until=0,lease_token=NULL,updated_at=? WHERE transfer_id=?", (utcnow(), transfer_id))
        if state == "accepted":
            if transfer["connector"] == "demo_receiver":
                conn.execute("INSERT OR IGNORE INTO receiver_records VALUES(?,?,?,?,?)", (transfer_id, tenant, transfer["matter_id"], json.dumps(payload), utcnow()))
            # Do not overwrite a newer workflow state if an abandoned lease expired.
            try:
                fresh = approved_payload(conn, user, data)
                still_current = payload_hash(fresh) == transfer["payload_hash"]
            except Exception:
                still_current = False
            if still_current:
                conn.execute("UPDATE matters SET status='exported',updated_at=? WHERE id=? AND tenant_id=?", (utcnow(), transfer["matter_id"], tenant))
            else:
                result["superseded"] = True
                conn.execute("UPDATE integration_transfers SET receipt_json=? WHERE id=?", (json.dumps(result), transfer_id))
        record_audit(conn, tenant, transfer["matter_id"], transfer["actor_id"], "connector_transfer_" + state, {"transfer_id": transfer_id, "connector": transfer["connector"], "payload_hash": transfer["payload_hash"], "receipt": result})
    return result


def resume_pending(limit=20):
    """Resume only unsent/abandoned intents. Uncertain outcomes need explicit review."""
    with db() as conn:
        jobs = conn.execute("""SELECT t.tenant_id,t.id FROM integration_transfers t JOIN integration_jobs j ON j.transfer_id=t.id
                               WHERE t.status='pending' OR (t.status='sending' AND j.lease_until<=?) ORDER BY t.rowid LIMIT ?""", (int(time.time()), limit)).fetchall()
    return [deliver(row["tenant_id"], row["id"]) for row in jobs]
