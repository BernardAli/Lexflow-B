"""Vendor-neutral case records. These fields are not a ProNotar import schema."""
from datetime import date
from fractions import Fraction
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator


def clean_text(value: str) -> str:
    if any(ord(char) < 32 for char in value):
        raise ValueError("Control characters are not allowed")
    return value


Text = Annotated[str, Field(max_length=300), AfterValidator(clean_text)]
Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)


class Address(Record):
    street: Text = ""
    postal_code: Text = ""
    city: Text = ""
    country: Text = ""


class SourcedRecord(Record):
    id: Identifier
    source_document_ids: list[Identifier] = Field(default_factory=list, max_length=20)
    source_note: Text = ""


class Participant(SourcedRecord):
    entity_type: Literal["person", "company"] = "person"
    roles: list[Literal["buyer", "seller", "founder", "shareholder", "director", "representative",
                        "deceased", "heir", "principal", "agent", "client", "other"]] = Field(min_length=1, max_length=12)
    name: Annotated[Text, Field(min_length=1)]
    short_name: Text = ""
    address: Address = Field(default_factory=Address)
    email: Text = ""
    phone: Text = ""
    tax_id: Text = ""
    birth_name: Text = ""
    birth_date: date | None = None
    citizenship: Text = ""
    marital_status: Literal["", "single", "married", "divorced", "widowed", "other"] = ""
    matrimonial_regime: Text = ""
    legal_form: Text = ""
    registered_seat: Text = ""
    register_court: Text = ""
    register_number: Text = ""
    vat_id: Text = ""
    representative_ids: list[Identifier] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_entity(self):
        if self.email:
            from .validation import validate_field_value
            self.email = validate_field_value("buyer_email", self.email)
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("Participant roles must be unique")
        if self.entity_type == "company" and any((self.birth_name, self.birth_date, self.citizenship,
                                                  self.marital_status, self.matrimonial_regime)):
            raise ValueError("Personal details belong to a person, not a company")
        if self.entity_type == "person" and any((self.legal_form, self.registered_seat, self.register_court,
                                                 self.register_number, self.vat_id)):
            raise ValueError("Company details belong to a company record")
        return self


class Property(SourcedRecord):
    address: Address = Field(default_factory=Address)
    land_register: Text = ""
    sheet: Text = ""
    volume: Text = ""
    inventory_number: Text = ""
    district: Text = ""
    section: Text = ""
    parcel: Text = ""
    area_sqm: Annotated[str, Field(max_length=30, pattern=r"^(?:[0-9]+(?:\.[0-9]{1,4})?)?$")] = ""
    ownership_share: Text = ""
    property_type: Literal["", "built", "unbuilt", "residential", "condominium", "agricultural", "other"] = ""
    encumbered: bool | None = None

    @model_validator(mode="after")
    def validate_property(self):
        if not any((self.address.street, self.land_register, self.parcel)):
            raise ValueError("Provide a property address, land register or parcel reference")
        if self.ownership_share:
            if not re.fullmatch(r"[1-9][0-9]*/[1-9][0-9]*", self.ownership_share) or Fraction(self.ownership_share) > 1:
                raise ValueError("Ownership share must be a positive fraction no greater than 1, such as 1/2")
        return self


class ExecutionTask(Record):
    id: Identifier
    title: Annotated[Text, Field(min_length=1)]
    status: Literal["pending", "initiated", "completed"] = "pending"
    due_date: date | None = None
    note: Text = ""


class CaseData(Record):
    schema_version: Literal[1] = 1
    category: Literal["property_transaction", "company_agreement", "power_of_attorney", "will", "bulk_certification", "other"] = "other"
    designation: Annotated[Text, Field(max_length=160)] = ""
    naming_code: Annotated[str, Field(max_length=16, pattern=r"^[\w-]*$")] = ""
    master_matter_id: Identifier | None = None
    template_reference: Text = ""
    with_execution: bool = True
    participants: list[Participant] = Field(default_factory=list, max_length=100)
    properties: list[Property] = Field(default_factory=list, max_length=100)
    tasks: list[ExecutionTask] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_links(self):
        records = [*self.participants, *self.properties, *self.tasks]
        ids = [record.id for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("Record IDs must be unique within a case")
        people = {p.id for p in self.participants if p.entity_type == "person"}
        for participant in self.participants:
            if participant.id in participant.representative_ids or any(r not in people for r in participant.representative_ids):
                raise ValueError("Representatives must reference other people in this case")
        return self


class CaseUpdate(Record):
    expected_revision: int = Field(ge=0, strict=True)
    data: CaseData


class CaseReview(Record):
    expected_revision: int = Field(ge=1, strict=True)


def default_case(matter_type):
    category = {"property_purchase": "property_transaction", "company_formation": "company_agreement"}.get(matter_type, "other")
    return CaseData(category=category).model_dump(mode="json")


def suggested_designation(data):
    participants = data["participants"]
    names = [p["short_name"] or p["name"] for role in ("seller", "buyer")
             for p in participants if role in p["roles"]]
    if not names:
        names = [p["short_name"] or p["name"] for p in participants if p["entity_type"] == "company"]
    if not names:
        names = [p["short_name"] or p["name"] for p in participants]
    return ("/".join(dict.fromkeys(names)) + " " + data["naming_code"]).strip()[:160]
