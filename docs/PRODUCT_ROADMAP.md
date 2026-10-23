# Product Roadmap — v0.11 to Customer Pilot

**Updated:** 23 October 2026 · **Current release:** 0.11.0-prototype

The working release supports a synthetic demonstration and pilot preparation. Commercial readiness depends on an authorized customer workflow, representative evaluation and validated infrastructure. See the [demonstration PDF](LexFlow_AI_Demonstration_Guide.pdf), [verification evidence](TEST_PLAN.md) and [security boundaries](SECURITY_AND_LIMITATIONS.md).

## Delivered in v0.11

| Area | Implemented behavior |
|---|---|
| Document workflow | Email/TXT/PDF/DOCX/image intake, local OCR support, explicit candidates, evidence, conflicts, human review and approval |
| Browser workspaces | Responsive views, keyboard-accessible tabs, preserved drafts, role controls and two synthetic offices |
| Workflow studio | Literal-label previews, tenant-scoped saved rules, version history and use on future intake |
| Output and integration | Approved JSON/CSV files, local receiver, generic signed HTTPS adapter and authenticated folder intake agent |
| NotaryDesk Demo | Fictional case-management workspace with separate encrypted case storage, verified local TLS, signed receipts and revision-checked preparation stages |
| Delivery reliability | Durable payload intents, destination binding, bounded leases, no writer lock during HTTP and same-key crash recovery |
| Identity and integrity | Authenticator MFA/recovery codes, required hardened enrollment, throttled sessions, CSRF, optional file encryption and audit HMAC chains |
| Operations | Dedicated HTTPS deployment configuration, provisioning, artifact rotation, authenticated snapshots and verified portable restore |
| Measurement | Defined pilot rates, reported work time, CSV evidence, a versioned synthetic extraction benchmark and CI release checks |

**Release evidence:** 111 backend tests and 21 UI tests passed; Chromium checks covered 141 page/panel views. The 28-case synthetic text benchmark records 100% precision, 97.2% recall and 98.6% F1, with two damaged-label misses. These figures do not establish OCR quality, office accuracy or customer savings.

NotaryDesk remains the demonstration destination while a real vendor is undecided. No vendor commitment or third-party test account is needed to run the local demo.

## Phase 1 — Field-tested discovery and integration spike

- Partner with 1–3 German notarial offices and map one real workflow (property-purchase intake recommended).
- Agree authorized data-processing and sanitized evaluation data.
- Select one exact supported destination software and identify its officially documented integration interface.
- Collect an agreed, representative set of sanitized documents across actual document families, including scans, missing fields and conflicts. A proposed initial range is 50–200 documents; set field-level acceptance criteria with the office.
- Formalize input schema, data ownership and human approval matrix.

**Success gate:** demonstrably feasible authorized write path, measurable baseline time per case and validated reviewer tasks.

## Phase 2 — First customer pilot

- Adapt the existing dry-run, signing, idempotency and receipt flow to the selected vendor's supported API/import format; test permissions and uncertain-outcome reconciliation against its test destination.
- Validate a dedicated office instance, encrypted database/backup volumes, managed key custody, monitoring and a restore drill in the target environment.
- Add SSO where required, managed MFA recovery, account lifecycle operations and centralized security telemetry to the existing authenticator/session controls.
- Evaluate German OCR and extraction on the office corpus, add source page/rectangle anchoring and agree reviewer escalation thresholds. Keep these results separate from the synthetic benchmark.
- Validate the existing learned-rule/version controls with office staff; extend templates and permissions only for observed needs.
- Arrange the required data-processing review, contracts and hosting controls before introducing office data.

**Pilot gate:** an authorized, traceable vendor handoff, agreed extraction quality, a completed restore drill and observed baseline/pilot work times. Track mandatory-field coverage, correction rate, reviewer time, unique-key acceptance, audit activity coverage and minutes per case; do not infer savings from a successful demo alone.

## Phase 3 — Commercial platform

- Outlook web add-in for intake and exception notifications.
- Word/DMS verification plugins and managed scanner/folder-agent rollout; the supervised folder agent already exists.
- More connectors selected by actual customer demand, not marketing breadth.
- Dedicated tenant/private deployment, managed SLAs, observability and operational response.
- Extend the existing workflow studio/API/reporting with customer-supported integrations, managed administration and service-level commitments.

## Differentiation to prove against competitors

1. **Integration reliability**: legally authorized, high-quality and well-supported transfers into existing notary software.
2. **Verified precision**: field-level source evidence, explicit conflict handling and well-measured error rates.
3. **Operational efficiency**: fewer manual corrections and case-handling minutes, not merely successful demonstrations.
4. **Privacy posture**: isolation, key ownership and processor arrangements appropriate for German notarial requirements.
5. **Low adoption cost**: employees continue to use familiar workflows; training and onboarding are simple.

## Not in scope for this release

The release does not provide certified notarization, BNotK/XNP endorsement, a real notary-vendor connection, native Outlook/Word add-ins or a managed production service. Approval records a human workflow decision; it does not replace legal judgment.
