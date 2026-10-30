# Demonstration and Verification Checklist

**Release:** 0.12.0-prototype · **Evidence date:** 30 October 2026

Version 0.12 passed **134 backend tests and 26 UI logic tests**. A Chromium check using isolated synthetic data completed participant/property/task creation, case naming, review, approval, preview and download of the structured bundle. The downloaded snapshot matched the preview digest, no JavaScript errors were recorded, and layouts had no horizontal page overflow at widths 390, 768 and 1440 pixels. Dependency consistency and JavaScript syntax checks passed. The unchanged 28-case synthetic extraction benchmark reports precision 1.0, recall 0.971831 and F1 0.985714; this does not measure extraction of the new structured records or office documents.

The backend run used `PYTHONDONTWRITEBYTECODE=1 .venv-demo/bin/python -m pytest -q -p no:cacheprovider`; browser logic used `node tests/ui.test.cjs`. Loopback access was needed for the FastAPI test client and local demo receiver. One existing audit regression was made deterministic by selecting the current workspace's audit row before tampering with it. An upstream Starlette/httpx deprecation warning remains; it did not affect the passing checks.

ProNotar itself was not tested: the installed version, import schema and test installation remain unavailable. See [ProNotar extension verification](PRONOTAR_EXTENSION.md#verification) for the new coverage. The earlier v0.11 release passed 111 backend tests, 21 UI tests and 141 Chromium page/panel checks at widths 320, 390, 768, 1440 and 1920; those broader checks were not all repeated for v0.12. See [historical release verification](#0110-release-verification--2026-10-23). The [14-page PDF guide](LexFlow_AI_Demonstration_Guide.pdf) covers v0.12, including structured preparation on pages 13–14; its earlier screenshots and the narrated video show v0.11.

| ID | Scenario | Expected outcome |
|---|---|---|
| A01 | Visit `/api/health` | HTTP 200 and prototype status |
| A02 | Open app without login | Login screen; protected API returns HTTP 401 |
| A03 | Login as admin@keller.demo | Dashboard for Notariat Keller only |
| A04 | Open 2026-KEL-0041 | Land register 812/872 conflict with two sources |
| A05 | Try approving before review | HTTP 422; approval blocked |
| A06 | Confirm required fields, resolve every conflict and review saved case details | Approval unlocks when a source exists and every gate is satisfied |
| A07 | Approve matter | State changes to approved; audit event written |
| A08 | Export as JSON | Downloadable mapped file, no live transmission |
| A09 | Export as CSV | BOM-prefixed UTF-8 CSV, mapped key-value rows |
| A10 | Reopen approved matter | Matter becomes in_review; approval reset |
| A11 | Upload another document | Existing confirmations cleared for re-review |
| A12 | Login as analyst | Can view/create/intake and prepare case details; cannot confirm, approve, generate exports or send transfers |
| A13 | Login as reviewer | Can confirm; cannot alter admin mappings |
| A14 | Login as Weber admin | Keller matter cannot be read or modified |
| A15 | Remove CSRF header | State mutation returns HTTP 403 |
| A16 | Upload an unsupported extension | HTTP 415 |
| A17 | Opt into external AI without config | HTTP 400, no external transmission |
| A18 | Process sample PDF | Extract buyer, seller, price, address and land register |
| A19 | Process sample DOCX | Recognize labeled values in two-column table |
| A20 | Process sample EML | Extract plain-text email body |
| A21 | Start guided demo twice | Two independent synthetic matters with the 812/872 conflict |
| A22 | Confirm required fields with an optional conflict outstanding | Approval remains blocked |
| A23 | Save duplicate destinations, including a partial update | HTTP 422 and mappings unchanged |
| A24 | Confirm invalid currency/date/email | HTTP 422; candidate selection also validates |
| A25 | Correct twice, clear, then add documents | Earlier values, complete notes and source decisions remain in audit |
| A26 | Upload good TXT then malformed PDF | No batch documents, reviews, files or audit changes persist |
| A27 | Simulate storage failure on the second file | Database rolls back; newly written files are removed |
| A28 | Process HTML email with a PDF attachment | Both bodies and attachment data appear; unsupported attachments warn |
| A29 | Process mixed PDF or multipage TIFF | OCR runs per needed page/frame; failures identify the affected page/frame |
| A30 | Reopen, change input, or change mappings after exporting | Previous output is superseded and download returns HTTP 409 |
| A31 | Use Close, Cancel, Clear review and edit corrections | Buttons work; saved correction/note/source remain selected |
| A32 | Change export connector profile | Preview refreshes to match generated payload |
| A33 | Use Forgot password for a seeded account | Clearly labeled local reset link appears; no email is sent |
| A34 | Set and confirm a new password | New password works; old password and previous sessions fail |
| A35 | Reuse/expire a link or request a newer one | Invalid link rejected; no password change |
| A36 | Submit mismatched, short or oversized passwords | Error shown; valid reset token remains usable |
| A37 | Request unknown/non-seeded account in demo mode | Neutral response; no reset link exposed |
| A38 | Repeated requests or failed redemptions | HTTP 429 with Retry-After; counters expire |
| A39 | Configure SMTP with test transport | TLS delivery uses configured origin; API response contains no token |
| A40 | Open reset link directly on desktop/mobile | Public reset form loads, errors are accessible, all text is at least 12px |

Additional platform verification:

| ID | Scenario | Expected outcome |
|---|---|---|
| B01 | Test a new label rule and save it | Preview values stay transient; only label/schema configuration persists |
| B02 | Upload a matching future document | Tenant/matter-specific learned candidate appears and still needs review |
| B03 | Pause a rule or submit a stale rule version | New version recorded; stale updates return 409 |
| B04 | Attempt another tenant's rule or receipt | No disclosure; missing resources return 404 |
| B05 | Dry run an unapproved matter | Transfer blocked |
| B06 | Send an approved preview twice with one key | One destination record, one receipt; second request replays |
| B07 | Change approved content after preview | Fingerprint check rejects stale preview |
| B08 | Mock HTTPS rejection/timeout/acceptance | `failed`/`uncertain`/`accepted` outcomes remain distinct; secrets are not returned |
| B09 | Run folder agent twice on the same file | One document and atomic intake receipt; second run reports already received |
| B10 | Inspect pilot with no baseline/time/transfers | Missing evidence stays empty; no fabricated savings or success rate |
| B11 | Add baseline and work sessions, retry an observation | Correct per-case totals and rates; observation key prevents double counting |
| B12 | Alter an audit event directly | Chain verification reports invalid |
| B13 | Configure workspace file keys and rotate | Stored bytes are encrypted; authenticated download reproduces original bytes |
| B14 | Back up a workspace | Authenticated v2 database/file snapshot verifies; local fallback keys are included and configured external keys are excluded |
| B15 | Start incomplete hardened configuration | Startup fails closed |
| B16 | Provision one dedicated workspace and start with HTTPS | Secure cookies, no seeded credentials, hidden API docs and valid audit verification |
| B17 | Use forged Host or exhausted sign-in attempts | Host rejected or 429 with Retry-After |
| B18 | Leave a session idle or revoke other sessions | Expired/revoked sessions fail; retained current session continues |

Tabbed interface verification:

| ID | Scenario | Expected outcome |
|---|---|---|
| C01 | Switch sections with mouse, arrow keys, Home or End | One selected tab and visible panel; keyboard focus follows selection |
| C02 | Switch intake modes with text and files selected | Draft text, document label and selected upload files remain intact |
| C03 | Edit mappings, visit another tab and return | Unsaved edits remain; switching tabs submits no forms |
| C04 | Save a baseline or refresh the same matter | The selected section remains open; another matter has its own selection |
| C05 | Inspect receipts or connectors after a dry run | Preview and transfer key remain ready until the matter or destination changes |
| C06 | Generate an approved matter export | Exports tab opens with the generated download and updated count |
| C07 | Sign out or enter a reviewer workspace | Tab preferences clear; membership data and its tab remain admin-only |

The tab regression covers 125 panel views across 12 routes, checking panel relationships, keyboard focus, the 12px text minimum, horizontal overflow and the review/approval/export/receiver flow. The v0.11 browser run adds 16 checks of destination/MFA views, for 141 in total. These are manual CDP-driven Chromium checks; the committed UI suite uses jsdom.

Structured case verification in v0.12:

| ID | Scenario | Expected outcome |
|---|---|---|
| D01 | Add people, a company and multiple properties | Records round-trip independently with stable local IDs |
| D02 | Save a category, naming code, designation, master case and template reference | Case metadata persists separately from matter title/reference and extraction schema |
| D03 | Add a representative and execution tasks | Local relationships and pending/initiated/completed statuses persist; no external action occurs |
| D04 | Save details as an analyst; attempt confirmation | Preparation succeeds; reviewer-only confirmation returns 403 |
| D05 | Approve with saved, unreviewed details, including an empty structure | Approval blocked until the current case revision is reviewed |
| D06 | Review a participant/property without sources or a verification note | Review rejected with actionable validation |
| D07 | Add intake, confirm/clear a field or reopen after case review | Review cleared and revision incremented; earlier export invalidation remains enforced |
| D08 | Save/review from a stale form | HTTP 409; newer records remain intact and the browser asks for refresh |
| D09 | Link a foreign-matter source, foreign-tenant master or cyclic master chain | Invalid reference rejected without modifying saved data |
| D10 | Submit invalid dates, shares, duplicate IDs or representative links | Structured validation rejects the document |
| D11 | Preview and download an approved case bundle | Snapshot/digest agree; repeated records, review provenance and source hashes present; original bytes/paths absent |
| D12 | Export flat JSON/CSV or send to NotaryDesk | Existing flat contract retained; structured records omitted |
| D13 | Select ProNotar32 or request an unsupported format | Vendor adapter remains blocked; no guessed XML is emitted |
| D14 | Initialize an existing database, then back up/restore structured records | Additive table and existing data survive; authenticated snapshot verifies |
| D15 | Edit malicious-looking text or switch person/company forms | Text escaped, incompatible attributes cleared and approval-state controls respected |
| D16 | Walk through preparation/review/export at 390, 768 and 1440 px | No script errors or horizontal page overflow; downloaded bundle matches preview |

Run automated checks from the project root:

```bash
.venv-demo/bin/python -m pytest -q
.venv-demo/bin/python -m pip check
.venv-demo/bin/python -m compileall -q lexflow agents
npm ci
npm run test:ui
node --check static/app.js
node --check static/features.js
node --check static/case-data.js
node --check static/notary.js
.venv-demo/bin/python -m lexflow.benchmark --output /tmp/extraction-report.json --min-f1 0.95
```

Tests create isolated temporary data directories, leaving your running demo environment intact.

Python 3.12 is the tested demo runtime. Interface checks use jsdom and Node.js; they do not replace a graphical browser walkthrough. OCR tests mock recognition so they run without installing Tesseract. SMTP tests mock both TLS transports and never send email. Password reset tests cover all demo roles, concurrent redemption, expiration, replay, session revocation, account boundaries, password-change invalidation, private errors and rate limits. Docker execution and Windows PowerShell launch require their respective platforms.

The earlier workspaces were also exercised end-to-end in Chromium at widths 320, 390, 768 and 1440 pixels, checking visible text at least 12px, text contrast and horizontal overflow. The real folder agent was run against a temporary HTTP server twice to verify receipt replay. Docker execution, Caddy/ACME and live third-party SMTP/webhook destinations were not available; third-party transports are mocked in automated checks.

## 0.11.0 release verification — 2026-10-23

**111 backend tests and 21 interface tests passed.** Dependency compatibility and JavaScript syntax checks pass. The complete 125-view tab/browser regression was repeated, followed by 16 checks of the new destination and MFA screens at 320, 390, 768, 1440 and 1920 pixels. No script errors or horizontal page overflow were observed; visible text is at least 12px.

| Area | Evidence |
|---|---|
| Authenticator MFA | RFC test vectors, encrypted identity binding, required enrollment, replay/window/expiry controls, bounded challenge attempts, session revocation and password-reset factor preservation |
| Recovery | Hashed single-use codes, code replacement, mandatory-policy enforcement, inline invalid proof and browser recovery sign-in with decremented remaining count |
| NotaryDesk Demo | Actual certificate-verified local HTTPS, signed request/receipt, independently encrypted destination case, duplicate prevention, stage revisions, tenant scoping and analyst restrictions |
| Delivery recovery | Crash simulated after destination commit; expired lease resumes the original key without another case. Unrelated writers proceed during network I/O; approval-invalidating writes return 409 |
| Portable restore | Moved snapshot, encrypted artifacts, original-document hash, MFA secret, audit chain, destination case, session/reset revocation and authenticated restored download |
| Snapshot rejection | Modified/missing/extra files, symlinks, altered manifest, wrong external key, unsafe database paths and existing restore destinations are rejected |
| Extraction | 28 versioned synthetic cases across four schemas, negative/empty labels, aliases, duplicate normalization and conflicting values. Two damaged labels remain documented misses |

Run `python -m lexflow.benchmark --output /tmp/extraction-report.json --min-f1 0.95`. The committed report records 100% precision, 97.2% recall and 98.6% micro F1 on this small synthetic text set. It does not measure OCR, external AI, legal correctness or representative office performance. CI is configured for pushes and pull requests; a hosted run has not been claimed. Docker, external SMTP and an actual vendor destination still require target-environment validation.

## Extending the extraction evaluation

Use a separately labelled JSON dataset with this shape, and set `synthetic` honestly:

```json
{
  "format": "lexflow-extraction-evaluation-v1",
  "version": "example-synthetic-v1",
  "synthetic": true,
  "limitations": "One synthetic text example; no OCR or office-performance claim.",
  "cases": [
    {
      "id": "example-1",
      "matter_type": "general",
      "text": "Client name: Taylor Example\nMatter reference: SYN-101",
      "expected": {
        "client_name": ["Taylor Example"],
        "matter_reference": ["SYN-101"]
      }
    }
  ]
}
```

Run `python -m lexflow.benchmark --dataset /path/to/labelled.json --output /tmp/office-report.json --min-f1 0.95`. Cases need unique IDs, a supported matter type, at most 200,000 text characters and supported field keys with non-empty value lists. List every expected distinct value for a conflicting field. An empty `expected` map represents a negative example. The complete dataset is limited to 16 MiB.

Metrics compare normalized field/value sets: precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2TP/(2TP+FP+FN). A wrong value counts as an unexpected value and a missed expected value. Undefined rates are `null`; a missing F1 or one below `--min-f1` fails the command. Reports record the dataset SHA-256, per-schema/case counts and missed/unexpected field names. They omit source text and values, but case IDs and paths should still avoid private information. This CLI evaluates built-in offline rules; it does not load a workspace's learned rules or call external AI.

## Rebuilding the demonstration PDF

The source is [build_demo_guide.py](build_demo_guide.py), with synthetic screenshots in `docs/assets/`. From the repository root, use a separate documentation environment:

```bash
python3.12 -m venv /tmp/lexflow-pdf-env
/tmp/lexflow-pdf-env/bin/python -m pip install -c constraints.txt -r docs/requirements-pdf.txt
/tmp/lexflow-pdf-env/bin/python docs/build_demo_guide.py
```

The builder needs the DejaVu Sans, Sans Bold, Serif and Sans Mono TrueType fonts (the Linux default is `/usr/share/fonts/truetype/dejavu`; use `--font-dir` for another installation). It writes the tracked 14-page v0.12 PDF, includes bookmarks and checks each page's content boundary. Open the result and inspect screenshots, footers and page breaks after editing. The six retained screenshots show the v0.11 core workflow; pages 13–14 document the new structured-case steps. Runtime users do not need these optional PDF dependencies.

The October 30 documentation refresh built all 14 pages within their content boundaries, verified the 14 bookmarks and release footers, and visually checked pages 2, 4, 10, 13 and 14. Local Markdown/player links resolved and the API case examples validated against the actual Pydantic models. Historical video/poster/caption hashes remained unchanged and source provenance verified. These are documentation checks; the application test results above come from the preceding v0.12 implementation verification.

## Rebuilding the presentation video

[Watch the narrated MP4](LexFlow_AI_Presentation.mp4) or open the [browser player and transcript](LexFlow_AI_Presentation.html). This is the **historical v0.11 presentation**, **4:04**, 1920×1080 at 25 fps, H.264/AAC, with 12 embedded chapters, locally generated English narration and captions burned into the picture. A [WebVTT sidecar](LexFlow_AI_Presentation.vtt) supports reuse in other players. Its [original 12-page source PDF](archive/LexFlow_AI_Demonstration_Guide_v0.11.pdf) is retained for reproducibility. It does not demonstrate v0.12 case preparation or ProNotar compatibility.

Edit [presentation_video.json](presentation_video.json) for scene titles, bullets, narration and source-page references. [build_presentation_video.py](build_presentation_video.py) renders landscape slides from those statements and the guide's screenshot assets, synthesizes speech locally with Flite, adds synchronized captions and encodes the MP4. It also writes the poster, HTML player/transcript and [provenance metadata](LexFlow_AI_Presentation.metadata.json), including the source PDF/story hashes and chapter timings. This is an adapted presentation rather than a live screen recording or a verbatim reading of every guide paragraph.

Requirements: Python 3.12 with the project's Pillow dependency, DejaVu fonts, and FFmpeg/FFprobe with the `libx264` encoder and `ass`/`flite` filters. The default speech voice is `slt`. No online speech service or API key is used. On a system with those tools available:

```bash
# Review all slide layouts without encoding.
.venv-demo/bin/python docs/build_presentation_video.py --preview-only --work-dir /tmp/lexflow-video-preview

# Rebuild the complete media package.
.venv-demo/bin/python docs/build_presentation_video.py --work-dir /tmp/lexflow-video-build

# Inspect media streams, duration and chapter metadata.
ffprobe -v error -show_streams -show_format -show_chapters -of json docs/LexFlow_AI_Presentation.mp4

# Decode the complete video/audio to detect corrupt media.
ffmpeg -v error -i docs/LexFlow_AI_Presentation.mp4 -map 0:v:0 -map 0:a:0 -f null -
```

Use `--font-dir` for another DejaVu installation, `--voice` for an available Flite voice, `--output` for an alternate MP4 destination or `--silent` for a captioned version without narration. Source assets resolve relative to `docs/`; output files sit beside the selected MP4. The generated player's PDF/README links assume the normal `docs/` destination. The current story points to the archived v0.11 PDF, so updating the v0.12 guide does not require rebuilding historical media. To publish a new video edition, update the story, narration, slide labels, player edition and source PDF together, then regenerate and verify provenance hashes, duration and chapter references. The October 30 metadata note records the source-path relocation; video, poster and captions are unchanged.

Playback verification covers H.264/AAC streams, non-silent narration, 12 chapters, 48 timed captions, source hashes and page coverage, full media decoding and browser chapter navigation. If your browser restricts file playback, use the included [local viewer](serve_presentation.py), which supports HTTP byte ranges for reliable chapter seeking and serves only the docs plus the README. The player also supplies a direct MP4 download and readable transcript. The viewer is for loopback document viewing, not application deployment:

```bash
.venv-demo/bin/python docs/serve_presentation.py --port 8002
```

Open `http://127.0.0.1:8002/docs/LexFlow_AI_Presentation.html`. Application startup and the document/video player are separate; watching the video needs no demo account.
