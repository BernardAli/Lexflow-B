# Proposed Product Roadmap — Concept to Commercial LexFlow

The presented product concept is broader than this local demonstrator. The steps below prioritize evidence that a customer will pay for a differentiated product rather than building generic AI features.

## Phase 0 — Working demonstration (this ZIP)

- Web workbench with seeded German notarial matters.
- Local document parsing for email, text, PDFs, DOCX and OCR-capable images/scanned PDFs.
- Field extraction, candidate evidence, conflict detection, human review and approval.
- Cross-tenant application scoping, role-based demo access, audit events.
- Approved structured CSV/JSON and mapped notary-connector **simulator**.

**Acceptance test:** complete an entirely synthetic property-purchase intake and export with no silent conflict resolution. `pytest -q` must pass.

## Phase 1 — Field-tested discovery and integration spike

- Partner with 1–3 German notarial offices and map one real workflow (property-purchase intake recommended).
- Agree authorized data-processing and sanitized evaluation data.
- Select one exact supported destination software and identify its officially documented integration interface.
- Collect 50–200 sanitized documents for extraction quality benchmarking.
- Formalize input schema, data ownership and human approval matrix.

**Success gate:** demonstrably feasible authorized write path, measurable baseline time per case and validated reviewer tasks.

## Phase 2 — First customer pilot

- Build one production-reviewed, authorized connector with dry-run and acknowledgment handling.
- Introduce robust tenant storage, encryption and key management.
- Deliver secured authentication, SSO/MFA where relevant, rate limiting and centralized logging.
- Implement German OCR + vision extraction benchmarks, source page/rectangle evidence, improved conflict validation.
- Add user-configurable workflow rules and versioned templates.
- Operate pilot in GDPR-approved environment under appropriate contracts.

**Pilot KPIs:** extraction coverage by mandatory field, correction rate, validation time, connector transfer success, audit completeness and minutes saved per case.

## Phase 3 — Commercial platform

- Outlook web add-in for intake and exception notifications.
- Word/DMS verification plugin and scanner/folder agent.
- More connectors selected by actual customer demand, not marketing breadth.
- Dedicated tenant/private deployment, managed SLAs, observability and operational response.
- Workflow studio, integration marketplace, permissioned API and reporting.

## Differentiation to prove against competitors

1. **Integration reliability**: legally authorized, high-quality and well-supported transfers into existing notary software.
2. **Verified precision**: field-level source evidence, explicit conflict handling and well-measured error rates.
3. **Operational efficiency**: fewer manual corrections and case-handling minutes, not merely successful demonstrations.
4. **Privacy posture**: isolation, key ownership and processor arrangements appropriate for German notarial requirements.
5. **Low adoption cost**: employees continue to use familiar workflows; training and onboarding are simple.

## Not in scope for this release

Do not present this prototype as a certified e-notary record system, a BNotK-endorsed interface, an electronic notarization service, or a replacement for legal judgment.
