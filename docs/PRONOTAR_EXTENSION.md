# ProNotar32 extension foundation

Release 0.12.0-prototype · 30 October 2026

LexFlow can now prepare structured case records independently of a vendor's import format. The compatibility target is the **latest vendor-supported ProNotar32 release**, as requested. No exact build, import schema or successful ProNotar import has been verified. `GET /api/connectors` reports `version_policy: latest_vendor_supported`, `verified_version: null`, and `status: specification_required` for this target.

The photographs supplied for discovery show XML import buttons for property and legal-entity records. They do not document the accepted schemas or establish a general-purpose case import. The [vendor's application guidance](https://www.pronotar.eu/pts/hinweise.aspx) directs users to **? → Handbücher** for manuals. Confirm the latest supported build and import contract through the office's licensed installation and vendor support before implementing a vendor serializer. No software version or XML specification is inferred from the screenshots or the ProTicket version number.

## Use the new workflow

1. Open a matter and select **Case details**.
2. Use **Edit case setup** to choose a category, office naming code, optional master case and template reference. **Use suggestion** proposes a designation from seller/buyer short names and the code; saving it does not rename the existing matter or its reference.
3. Add people and companies separately. Assign roles, contact details, person or company attributes and representative links. Add each property separately, including register sheet, cadastral district, section, parcel, area and ownership share.
4. Link each participant/property to source documents or enter a verification note. Add execution tasks with pending, initiated or completed status when needed. These tasks record work; they do not schedule notifications or perform external actions.
5. Confirm the existing extracted fields. A reviewer then uses **Confirm case details**, checking all structured records against the documents and the extracted fields. Finally, approve the matter.
6. Select **Export approved data → Structured case bundle (JSON)**. The preview and download contain the reviewed records, source metadata and review provenance. This file is a LexFlow interchange format, **not a ProNotar import file**.

Analysts can prepare records; only reviewers/admins can confirm them, approve or export. Approved/exported matters must be reopened before editing. Every saved case revision requires review, including an empty saved structure. Unsaved legacy matters retain their existing approval behavior.

Case categories follow the photographed creation dialog: property transaction, company agreement, power of attorney, will, bulk certification and other. Categories are handoff metadata; they do not add new automatic extraction engines. Existing extraction still uses the four established matter schemas. Names extracted into flat fields are not automatically split into participants, and no record is silently inferred from the photographs.

## Architecture

| Component | Responsibility |
|---|---|
| `lexflow/case_models.py` | Strict, bounded, versioned Pydantic records: participants, addresses, properties, execution tasks and local relationships |
| `lexflow/case_data.py` | Tenant-scoped storage, reference checks, optimistic revisions, review and audit |
| `matter_case_data` | Additive SQLite table; one validated JSON document and review metadata per matter |
| `lexflow/matter_service.py` | Shared approval/export gate, including structured-case review |
| `lexflow/connectors.py` | Capability registry, vendor-neutral approved snapshot and file adapter protocol |
| `static/case-data.js` | Case editor with repeatable records and source selection |

The additive schema is created at startup. Existing rows, identifiers, approvals and exports are preserved. No migration rewrites flat buyer/seller names into guessed participants. Repeated initialization is safe. The existing authenticated backup/restore includes the new table.

Follow the [upgrade and rollback procedure](DEPLOYMENT.md#upgrading-to-v012) when updating an existing workspace. For integration development, use the [API request sequence](API.md#example--prepare-review-and-export-case-details) and the authenticated case model schema; the [README walkthrough](../README.md#demonstrate-structured-case-preparation) covers the browser flow.

`PUT` requires the complete case document plus `expected_revision`. A successful save increments the revision and clears its review. A stale save/review returns 409. Source intake, field confirmation/clearing and reopening also clear case review and increment the revision, so an open form cannot overwrite changes made against a different source state. Reviewer confirmation is a separate action from final matter approval. Existing delivery locks and export invalidation remain in force.

Participant/property source IDs must belong to the same matter. Representative IDs must reference another person in the same case. Master-case IDs must be in the same workspace; cycles are rejected. Record IDs are stable local identifiers, not vendor identifiers. Reuse them when editing; there is no automatic person/company deduplication across cases.

## Bundle contract

The envelope uses `specification: lexflow-case-bundle-v1`, `not_a_live_transmission: true` and `vendor_import_verified: false`. `snapshot_sha256` is SHA-256 over the snapshot encoded as UTF-8 JSON with sorted keys, compact separators and unescaped Unicode (`canonical_bytes`). It detects changed content; it is not a vendor receipt or a digital signature.

The `lexflow-case-v1` snapshot includes:

- Workspace and matter IDs, reference, title, extraction workflow and approval actor/time.
- Reviewed extraction fields using internal keys, and per-field source candidate/document references and review notes.
- `case_data` with `schema_version: 1`, structured records and their source links; `null` for legacy cases without saved case details.
- Case revision and reviewer metadata.
- Source-document IDs, filenames, media types, byte sizes and SHA-256 digests. Original document bytes and local filesystem paths are excluded.

The case model's JSON Schema is available at authenticated `GET /api/case-data/schema`. `samples/09_structured_case.json` is a synthetic case-data example, not an approved bundle or vendor file. Add a valid source link or retain a verification note before review.

Flat `approved_export` and `notary_demo` JSON/CSV profiles retain their previous formats and omit structured records. The existing local receiver, NotaryDesk and HTTPS transfer contracts also remain flat-field contracts. Use the structured case bundle when the new records are required. Destination field mappings in Settings apply to flat exports; they are not a nested ProNotar mapping engine.

## Implement the eventual adapter

1. Obtain the latest supported ProNotar build/module information, the exact documented import schema, accepted files, required identifiers, supported create/update operations and error behavior. Verify whether the photographed XML actions are limited to register exports.
2. Map the snapshot to that specific format inside a `FileAdapter.serialize(snapshot, mapping, fmt)` implementation. Apply required-field and cardinality checks, supported-value mappings, encoding rules and schema validation. Do not invent a general XML format or infer compatibility from field labels.
3. Replace the disabled `ProNotar32Adapter`, register its actual formats and expose only validated capabilities. Extend the API export format allow-list and browser export choices when the verified format requires it (for example XML). Set `verified_version` to the tested build; revalidate on vendor updates.
4. Maintain an explicit crosswalk between local record IDs and vendor case/participant/property IDs. Test creation, matching, duplicates, updates, rejected records and partial imports before enabling writes. Do not write directly to a vendor database.
5. Verify imports using synthetic cases in an authorized test installation. Compare every field and relationship, including repeated participants and properties. A generated file does not prove receipt; record an import result separately before claiming a successful handoff.
6. If the vendor supports an automated transport, adapt the existing delivery job, destination binding, preview hash and same-key recovery mechanisms in `integrations.py`/`delivery.py` to its actual protocol. The existing signed HTTPS contract must not be assumed to match ProNotar.

The disabled adapter deliberately rejects preview/export attempts with 409 and never emits speculative XML. This release does not connect Word, Outlook, BNotK/XNP, billing, scanners or a live ProNotar installation.

## Verification

`tests/test_case_data.py` covers structured record round trips, approval gates, source changes, stale revisions, workspace isolation, analyst/reviewer permissions, CSRF, invalid dates/shares/relationships, master-case cycles, schema upgrades, export capability limits and authenticated backup/restore. Browser logic tests cover participant editing, company/person switching, stale edit recovery, escaped text, approved-state controls, naming suggestions and bundle selection.
