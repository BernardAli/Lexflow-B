"""Generate approved, auditable demo exports. No live notary-system writes."""
import csv
import io
import json
import re
from .extraction import FIELD_META
from .validation import validate_field_value

DEFAULT_MAPPINGS = {
 "buyer_name": "Beteiligter.Kaeufer.Name",
 "seller_name": "Beteiligter.Verkaufer.Name",
 "purchase_price": "Vorgang.KaufpreisEUR",
 "property_address": "Immobilie.Anschrift",
 "land_register": "Grundbuch.Blatt",
 "buyer_email": "Beteiligter.Kaeufer.Email",
 "appointment_date": "Vorgang.Termin",
 "parcel_reference": "Immobilie.Flurstueck",
 "company_name": "Gesellschaft.Firma",
 "founder_name": "Gruender.Name",
 "registered_address": "Gesellschaft.Sitz",
 "deceased_name": "Nachlass.Erblasser",
 "heir_name": "Nachlass.Erbe",
 "estate_reference": "Nachlass.Aktenzeichen",
 "client_name": "Mandant.Name",
 "matter_reference": "Vorgang.Aktenzeichen",
}


def validate_mappings(mapping: dict):
    destinations = {}
    for key, target in mapping.items():
        if key not in FIELD_META or not isinstance(target, str) or not re.fullmatch(r"[\w.\-]{2,100}", target):
            raise ValueError(f"Invalid mapping: {key}")
        if target in destinations:
            raise ValueError(f"Destination {target} is used by both {destinations[target]} and {key}")
        destinations[target] = key


def generate_export(matter: dict, fields: dict, mapping: dict, connector: str, fmt: str):
    # Check the effective mapping too: legacy configuration and fallback keys must
    # never silently overwrite another approved value.
    effective = {key: mapping.get(key, key) for key in fields}
    validate_mappings(effective)
    fields = {key: validate_field_value(key, value) for key, value in fields.items()}
    mapped = {mapping.get(key, key): value for key, value in fields.items()}
    if fmt == "json":
        obj = {"specification": "lexflow-demo-connector-v1", "connector": connector,
               "not_a_live_transmission": True,
               "matter": {"reference": matter["reference"], "title": matter["title"],
                          "matter_type": matter["matter_type"], "approved_at": matter["approved_at"]},
               "fields": mapped}
        return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["matter_reference", "destination_field", "value"])
        for field, value in mapped.items():
            writer.writerow([matter["reference"], field, value])
        return ("\ufeff" + out.getvalue()).encode("utf-8")
    raise ValueError("Unsupported export format")
