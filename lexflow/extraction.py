"""Auditable extraction. Rules run offline; external LLM is optional and opt-in."""
import json
import re
import unicodedata
import httpx
from .settings import allow_external_ai, ai_model
import os

FIELD_META = {
 "buyer_name": ("Buyer / Käufer", "person"),
 "seller_name": ("Seller / Verkäufer", "person"),
 "purchase_price": ("Purchase price / Kaufpreis", "currency"),
 "property_address": ("Property address / Objektadresse", "text"),
 "land_register": ("Land register / Grundbuch", "text"),
 "buyer_email": ("Buyer email", "email"),
 "appointment_date": ("Appointment / Termin", "date"),
 "parcel_reference": ("Parcel reference / Flurstück", "text"),
 "deceased_name": ("Deceased / Erblasser", "person"),
 "heir_name": ("Heir / Erbe", "person"),
 "estate_reference": ("Estate reference / Aktenzeichen", "text"),
 "company_name": ("Company name / Firma", "text"),
 "founder_name": ("Founder / Gründer", "person"),
 "registered_address": ("Registered address / Sitz", "text"),
 "client_name": ("Client name", "person"),
 "matter_reference": ("Matter reference", "text"),
}
SCHEMAS = {
  "property_purchase": {"label": "Property purchase / Grundstückskauf", "required": ["buyer_name", "seller_name", "purchase_price", "property_address", "land_register"], "optional": ["buyer_email", "appointment_date", "parcel_reference"]},
  "inheritance": {"label": "Inheritance / Erbrecht", "required": ["deceased_name", "heir_name", "estate_reference"], "optional": ["appointment_date"]},
  "company_formation": {"label": "Company formation / Gründung", "required": ["company_name", "founder_name", "registered_address"], "optional": ["appointment_date"]},
  "general": {"label": "General matter / Sonstiges", "required": ["client_name", "matter_reference"], "optional": ["appointment_date"]},
}

# Explicitly labeled fields only: avoids inferring legally relevant data from context.
PATTERNS = {
 "buyer_name": [r"(?:Käufer(?:in)?|Kaeufer(?:in)?|Erwerber(?:in)?|Buyer(?:\s+name)?)\s*[:=\-]\s*([^\n;]+)"],
 "seller_name": [r"(?:Verkäufer(?:in)?|Verkaeufer(?:in)?|Veräußerer(?:in)?|Seller(?:\s+name)?)\s*[:=\-]\s*([^\n;]+)"],
 "purchase_price": [r"(?:Kaufpreis(?:betrag)?|Purchase\s+price)\s*[:=\-]\s*(?:EUR|€)?\s*([\d][\d., \u00a0]*(?:\s*(?:€|EUR))?)"],
 "property_address": [r"(?:Objektadresse|Grundstücksadresse|Grundstuecksadresse|Immobilienadresse|Property\s+address|Adresse\s+(?:des\s+)?(?:Objekts|Grundstücks))\s*[:=\-]\s*([^\n;]+)"],
 "land_register": [r"(?:Grundbuch(?:blatt|auszug)?|Land\s+register)\s*[:=\-]\s*([^\n;]+)"],
 "buyer_email": [r"(?:Käufer\s*E-?Mail|Kaeufer\s*E-?Mail|Buyer\s*e-?mail)\s*[:=\-]\s*([^\s;]+)"],
 "appointment_date": [r"(?:Beurkundungstermin|Termin|Appointment\s+date)\s*[:=\-]\s*([^\n;]+)"],
 "parcel_reference": [r"(?:Flurstück(?:snummer)?|Flurstueck(?:snummer)?|Parcel(?:\s+reference)?)\s*[:=\-]\s*([^\n;]+)"],
 "deceased_name": [r"(?:Erblasser(?:in)?|Verstorben(?:e|er)|Deceased)\s*[:=\-]\s*([^\n;]+)"],
 "heir_name": [r"(?:Erb(?:e|in)|Heir)\s*[:=\-]\s*([^\n;]+)"],
 "estate_reference": [r"(?:Nachlassakte|Nachlassaktenzeichen|Estate\s+reference)\s*[:=\-]\s*([^\n;]+)"],
 "company_name": [r"(?:Firma|Gesellschaftsname|Company\s+name)\s*[:=\-]\s*([^\n;]+)"],
 "founder_name": [r"(?:Gründer(?:in)?|Gruender(?:in)?|Founder)\s*[:=\-]\s*([^\n;]+)"],
 "registered_address": [r"(?:Sitz\s+der\s+Gesellschaft|Geschäftssitz|Geschaeftssitz|Registered\s+address)\s*[:=\-]\s*([^\n;]+)"],
 "client_name": [r"(?:Mandant(?:in)?|Client\s+name)\s*[:=\-]\s*([^\n;]+)"],
 "matter_reference": [r"(?:Aktenzeichen|Matter\s+reference)\s*[:=\-]\s*([^\n;]+)"],
}


def normalize_currency(value: str) -> str:
    from .validation import currency_value
    try:
        return currency_value(value)
    except ValueError:
        return value.strip()


def clean_value(key: str, raw: str) -> str:
    val = re.sub(r"\s+", " ", raw).strip().strip(".;, ")
    val = re.split(r"\s{2,}|\s+\|\s+", val)[0].strip()
    if key == "purchase_price":
        return normalize_currency(val)
    if key == "buyer_email":
        return val.lower()
    return val[:280]


def comparison_value(key: str, value: str) -> str:
    if key == "purchase_price":
        return normalize_currency(value)
    x = unicodedata.normalize("NFKC", value).lower().strip()
    return re.sub(r"[\s.,]+", " ", x)


def infer_matter_type(text: str) -> str:
    t = text.lower()
    if any(word in t for word in ("grundbuch", "kaufpreis", "kaufvertrag", "immobilienkauf")):
        return "property_purchase"
    if any(word in t for word in ("erbschein", "erblasser", "nachlass")):
        return "inheritance"
    if any(word in t for word in ("gesellschaftsgründung", "handelsregister", "gesellschafter")):
        return "company_formation"
    return "general"


def rule_extract(text: str, matter_type: str):
    schema = SCHEMAS.get(matter_type, SCHEMAS["general"])
    valid_fields = set(schema["required"] + schema["optional"])
    found = []
    for key in valid_fields:
        for regex in PATTERNS.get(key, []):
            for match in re.finditer(r"(?<!\w)" + regex, text[:200_000], flags=re.IGNORECASE):
                raw = match.group(1)
                value = clean_value(key, raw)
                if not value or len(value) < 2:
                    continue
                evidence = text[max(0, match.start() - 20):min(len(text), match.end() + 50)].replace("\n", " ").strip()
                confidence = 0.98 if key in ("buyer_name", "seller_name", "purchase_price", "company_name") else 0.92
                if key == "land_register": confidence = 0.88
                found.append({"field_key": key, "value": value, "confidence": confidence,
                              "evidence": evidence[:260], "origin": "local_rules"})
                if len([v for v in found if v["field_key"] == key]) >= 8:
                    break
    unique = []
    existing = set()
    for item in found:
        marker = (item["field_key"], comparison_value(item["field_key"], item["value"]))
        if marker not in existing:
            unique.append(item)
            existing.add(marker)
    return unique


async def external_ai_extract(text: str, matter_type: str):
    """Send docs to external API ONLY when env enabled and user opted in per intake."""
    if not allow_external_ai():
        raise ValueError("External AI is disabled. Set LEXFLOW_ALLOW_EXTERNAL_AI=1 and OPENAI_API_KEY.")
    schema = SCHEMAS.get(matter_type, SCHEMAS["general"])
    fields = schema["required"] + schema["optional"]
    prompt = ("Extract only literally present facts from the German or English notarial document. "
              "Do not guess, invent or provide legal advice. Return one JSON object with 'fields': "
              "a dictionary using ONLY these keys, with string values or omit missing values: " + ", ".join(fields) + ". "
              "For monetary values use a numeric string without currency.\n\nDOCUMENT:\n" + text[:36_000])
    payload = {"model": ai_model(), "temperature": 0,
               "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": "You extract explicitly stated legal document data. Return JSON only."},
                            {"role": "user", "content": prompt}]}
    async with httpx.AsyncClient(timeout=55.0) as client:
        response = await client.post("https://api.openai.com/v1/chat/completions",
                                     headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}, json=payload)
        response.raise_for_status()
    result = response.json()
    obj = json.loads(result["choices"][0]["message"]["content"])
    data = obj.get("fields", {})
    candidates = []
    if not isinstance(data, dict):
        return candidates
    for key, value in data.items():
        if key not in fields or value is None or not isinstance(value, (str, int, float)):
            continue
        cleaned = clean_value(key, str(value))
        if cleaned:
            candidates.append({"field_key": key, "value": cleaned, "confidence": 0.72,
                               "evidence": "External AI suggestion — verify against source document",
                               "origin": "external_ai_unverified"})
    return candidates
