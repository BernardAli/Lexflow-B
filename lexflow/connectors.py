"""File adapter boundary: validated case snapshot in, explicitly supported bytes out.

Implement a vendor's documented mapping here without changing intake or approval.
Transport adapters remain in delivery.py; exporting a file never confirms import.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Protocol

from fastapi import APIRouter, Depends

from .auth import require_user
from .case_data import case_state
from .exporter import generate_export

router = APIRouter(prefix="/api/connectors", tags=["Connector capabilities"])


@dataclass(frozen=True)
class Capability:
    id: str
    label: str
    formats: tuple[str, ...]
    status: str
    includes_case_data: bool
    import_verified: bool = False
    live: bool = False
    requirements: tuple[str, ...] = ()
    version_policy: str | None = None
    verified_version: str | None = None


class FileAdapter(Protocol):
    capability: Capability

    def serialize(self, snapshot: dict, mapping: dict, fmt: str) -> bytes: ...


class ConnectorUnavailable(ValueError):
    pass


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def approved_snapshot(conn, user, matter, fields):
    """Call only after shared approval gates; stable output with no export-time values."""
    state = case_state(conn, matter)
    documents = [dict(row) for row in conn.execute(
        "SELECT id,name,media_type,byte_size,sha256 FROM documents WHERE matter_id=? AND tenant_id=? ORDER BY id",
        (matter["id"], user["tenant_id"]))]
    reviews = [dict(row) for row in conn.execute(
        """SELECT r.field_key,r.value,r.candidate_id,r.reviewer_id,r.note,r.reviewed_at,c.document_id
           FROM field_reviews r LEFT JOIN candidates c ON c.id=r.candidate_id
           WHERE r.matter_id=? AND r.tenant_id=? ORDER BY r.field_key""", (matter["id"], user["tenant_id"]))]
    return {"schema": "lexflow-case-v1", "schema_version": 1, "workspace_id": user["tenant_id"],
            "matter": {key: matter[key] for key in ("id", "reference", "title", "matter_type", "approved_at", "approved_by")},
            "reviewed_fields": {f["key"]: f["value"] for f in fields if f["status"] == "confirmed"},
            "field_reviews": reviews,
            "case_data": state["data"] if state["revision"] else None,
            "case_review": {key: state[key] for key in ("revision", "reviewed_by", "reviewed_at")},
            "documents": documents}


class LegacyFileAdapter:
    def __init__(self, identifier, label):
        self.capability = Capability(identifier, label, ("json", "csv"), "available", False)

    def serialize(self, snapshot, mapping, fmt):
        return generate_export(snapshot["matter"], snapshot["reviewed_fields"], mapping, self.capability.id, fmt)


class CaseBundleAdapter:
    capability = Capability("case_bundle", "Structured case bundle", ("json",), "available", True)

    def serialize(self, snapshot, mapping, fmt):
        bundle = {"specification": "lexflow-case-bundle-v1", "connector": self.capability.id,
                  "not_a_live_transmission": True, "vendor_import_verified": False,
                  "snapshot_sha256": hashlib.sha256(canonical_bytes(snapshot)).hexdigest(),
                  "snapshot": snapshot}
        return json.dumps(bundle, ensure_ascii=False, indent=2).encode()


class ProNotar32Adapter:
    capability = Capability("pronotar32", "ProNotar32", (), "specification_required", True,
                            requirements=("Installed ProNotar version and licensed modules",
                                          "Supported import schema and accepted sample files",
                                          "Field mapping, identifiers and duplicate/update rules",
                                          "Successful import tests in an authorized test installation"),
                            version_policy="latest_vendor_supported")

    def serialize(self, snapshot, mapping, fmt):
        raise ConnectorUnavailable("ProNotar32 import is not verified. Obtain its import specification and validate an adapter first")


ADAPTERS: dict[str, FileAdapter] = {
    adapter.capability.id: adapter for adapter in (
        LegacyFileAdapter("approved_export", "Approved flat-field export"),
        LegacyFileAdapter("notary_demo", "Mock notary flat-field export"),
        CaseBundleAdapter(), ProNotar32Adapter())
}


def serialize_snapshot(snapshot, mapping, connector, fmt):
    adapter = ADAPTERS.get(connector)
    if adapter is None:
        raise ValueError("Unknown connector")
    if adapter.capability.status != "available":
        raise ConnectorUnavailable("ProNotar32 requires a documented and tested import adapter; no file was generated")
    if fmt not in adapter.capability.formats:
        raise ValueError("This connector does not support the selected format")
    return adapter.serialize(snapshot, mapping, fmt)


@router.get("")
def capabilities(user=Depends(require_user)):
    return {"case_schema": "lexflow-case-v1", "connectors": [asdict(a.capability) for a in ADAPTERS.values()]}
