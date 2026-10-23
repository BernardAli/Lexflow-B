"""Validate reviewed values without inferring missing facts."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .extraction import FIELD_META


def currency_value(value: str) -> str:
    match = re.fullmatch(r"\s*(?:(?:EUR|€)\s*)?([0-9][0-9., \u00a0]*?)(?:\s*(?:EUR|€))?\s*", value, re.I)
    if not match:
        raise ValueError("Enter a positive EUR amount, for example 850000.00 or 850.000,00 €")
    number = match[1].strip().replace("\u00a0", " ")
    if " " in number:
        if not re.fullmatch(r"\d{1,3}(?: \d{3})+(?:[.,]\d{1,2})?", number):
            raise ValueError("Invalid thousands grouping in amount")
        number = number.replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", number):
        number = number.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", number):
        number = number.replace(",", "")
    elif re.fullmatch(r"\d+(?:[.,]\d{1,2})?", number):
        number = number.replace(",", ".")
    else:
        raise ValueError("Invalid amount or more than two decimal places")
    try:
        amount = Decimal(number)
        if not amount.is_finite() or amount <= 0:
            raise ValueError("Purchase price must be positive")
        return format(amount.quantize(Decimal("0.01")), "f")
    except InvalidOperation as exc:
        raise ValueError("Amount is outside the supported range") from exc


def validate_field_value(key: str, value: str) -> str:
    if key not in FIELD_META:
        raise ValueError("Unknown field")
    value = value.strip()
    if not value or len(value) > 300 or any(ord(c) < 32 for c in value):
        raise ValueError("Enter a value of 1–300 characters without control characters")
    kind = FIELD_META[key][1]
    if kind == "currency":
        return currency_value(value)
    if kind == "date":
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                pass
        raise ValueError("Enter a valid calendar date as YYYY-MM-DD or DD.MM.YYYY")
    if kind == "email":
        parts = value.rsplit("@", 1)
        if len(parts) != 2 or not re.fullmatch(r"[^\s@<>]+", parts[0]) or len(parts[0]) > 64:
            raise ValueError("Enter a valid email address")
        try:
            domain = parts[1].encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ValueError("Enter a valid email domain") from exc
        labels = domain.split(".")
        if len(labels) < 2 or len(domain) > 253 or not all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels
        ):
            raise ValueError("Enter a valid email domain")
        return parts[0].lower() + "@" + domain
    if kind == "person" and not any(c.isalpha() for c in value):
        raise ValueError("A person name must contain letters")
    return value
