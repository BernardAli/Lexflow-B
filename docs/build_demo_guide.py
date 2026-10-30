"""Build the presenter PDF from repository-owned text and synthetic screenshots.

Run from any directory: python /path/to/docs/build_demo_guide.py
Optional flags: --output PATH and --font-dir /path/to/dejavu
PDF-only dependencies are in docs/requirements-pdf.txt.
"""
import argparse
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'LexFlow_AI_Demonstration_Guide.pdf')
parser.add_argument('--font-dir', type=Path, default=Path('/usr/share/fonts/truetype/dejavu'))
args = parser.parse_args()
OUTPUT = args.output.expanduser().resolve()
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
FONT_DIR = args.font_dir.expanduser().resolve()
font_files = ['DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSerif.ttf', 'DejaVuSansMono.ttf']
if any(not (FONT_DIR / name).is_file() for name in font_files):
    parser.error('Install the four DejaVu TrueType fonts listed in docs/TEST_PLAN.md, or select them with --font-dir')
for name, file in [('Body','DejaVuSans.ttf'),('BodyBold','DejaVuSans-Bold.ttf'),
                   ('Display','DejaVuSerif.ttf'),('Mono','DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyBold', italic='Body', boldItalic='BodyBold')

W, H = A4
M = 43
CW = W - M * 2
INK = colors.HexColor('#142b30')
TEAL = colors.HexColor('#1c6a5c')
GOLD = colors.HexColor('#bb9b69')
TEXT = colors.HexColor('#203431')
MUTED = colors.HexColor('#5f716c')
IVORY = colors.HexColor('#f5f5f0')
LINE = colors.HexColor('#dce3dc')
PALE = colors.HexColor('#edf3ed')
WHITE = colors.white
styles = {
    'body': ParagraphStyle('body', fontName='Body', fontSize=11.5, leading=16.4, textColor=TEXT),
    'small': ParagraphStyle('small', fontName='Body', fontSize=9.5, leading=13.6, textColor=MUTED),
    'table': ParagraphStyle('table', fontName='Body', fontSize=10.5, leading=14.6, textColor=TEXT),
    'th': ParagraphStyle('th', fontName='BodyBold', fontSize=10, leading=14, textColor=WHITE),
    'white': ParagraphStyle('white', fontName='Body', fontSize=13, leading=20, textColor=WHITE),
    'mono': ParagraphStyle('mono', fontName='Mono', fontSize=10.1, leading=15.3, textColor=INK),
}
c = canvas.Canvas(str(OUTPUT), pagesize=A4, pageCompression=1)
c.setTitle('LexFlow AI — Demonstration Guide')
c.setAuthor('Allgift Technologies Ltd')
c.setSubject('Presenter walkthrough for LexFlow AI v0.12.0-prototype; synthetic demonstration')
c.setCreator('LexFlow AI documentation')


def para(text, top, x=M, width=CW, kind='body', gap=8):
    p = Paragraph(text, styles[kind])
    _, height = p.wrap(width, H)
    p.drawOn(c, x, H - top - height)
    return top + height + gap


def label(text, top, x=M, color=TEAL, size=9.2):
    c.setFillColor(color)
    c.setFont('BodyBold', size)
    c.drawString(x, H-top-size, text)
    return top+size+12


def subtitle(text, top):
    c.setFillColor(INK)
    c.setFont('BodyBold', 14.2)
    c.drawString(M, H-top-14.2, text)
    return top+26


def table(headers, rows, widths, top, size='table'):
    cells = [[Paragraph(h, styles['th']) for h in headers]]
    cells += [[Paragraph(str(cell), styles[size]) for cell in row] for row in rows]
    t = Table(cells, colWidths=widths, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),INK), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,IVORY]),
        ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6),
        ('LEFTPADDING',(0,0),(-1,-1),10), ('RIGHTPADDING',(0,0),(-1,-1),10),
        ('LINEBELOW',(0,0),(-1,0),0.4,INK),
        ('LINEBELOW',(0,1),(-1,-1),0.35,LINE),
    ]))
    _, height = t.wrap(CW, H)
    t.drawOn(c, M, H-top-height)
    return top+height+14


def box(title, text, top, color=PALE):
    p = Paragraph(text, styles['body'])
    _, height = p.wrap(CW-32, H)
    height += 44
    c.setFillColor(color)
    c.roundRect(M,H-top-height,CW,height,8,fill=1,stroke=0)
    label(title,top+12,x=M+16,size=8.6)
    p.drawOn(c,M+16,H-top-height+14)
    return top+height+14


def code(lines, top):
    text='<br/>'.join(escape(line).replace(' ','&#160;') for line in lines)
    p = Paragraph(text,styles['mono'])
    _,height=p.wrap(CW-28,H)
    height+=24
    c.setFillColor(IVORY)
    c.roundRect(M,H-top-height,CW,height,7,fill=1,stroke=0)
    p.drawOn(c,M+14,H-top-height+12)
    return top+height+13


def steps(items, top, start=1):
    for index,(title,description) in enumerate(items,start):
        c.setFillColor(TEAL)
        c.circle(M+10,H-top-10,10,fill=1,stroke=0)
        c.setFillColor(WHITE)
        c.setFont('BodyBold',9.2)
        c.drawCentredString(M+10,H-top-13,str(index))
        top=para('<b>'+title+'</b> '+description,top,x=M+30,width=CW-30,gap=8)
    return top


def image(name, top, max_height=235, caption=None):
    reader=ImageReader(str(ROOT/'assets'/name))
    iw,ih=reader.getSize()
    scale=min(CW/iw,max_height/ih)
    width,height=iw*scale,ih*scale
    left=M+(CW-width)/2
    c.setFillColor(WHITE)
    c.setStrokeColor(LINE)
    c.roundRect(left-1,H-top-height-1,width+2,height+2,4,fill=1,stroke=1)
    c.drawImage(reader,left,H-top-height,width,height,mask='auto')
    top+=height+7
    if caption: top=para(caption,top,kind='small',gap=8)
    return top


def page(number, section, title, intro):
    if number>1: c.showPage()
    c.setFillColor(WHITE)
    c.rect(0,0,W,H,fill=1,stroke=0)
    c.bookmarkPage('p'+str(number))
    c.addOutlineEntry(title,'p'+str(number),level=0,closed=False)
    label('LEXFLOW AI  /  DEMONSTRATION GUIDE',27,size=8.5,color=MUTED)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.2)
    c.line(M,H-51,W-M,H-51)
    label(section.upper(),67,size=9)
    c.setFont('Display',26)
    c.setFillColor(INK)
    c.drawString(M,H-112,title)
    top=para(intro,125,kind='body',gap=17)
    footer(number)
    return top


def footer(number):
    c.setStrokeColor(LINE)
    c.setLineWidth(.5)
    c.line(M,43,W-M,43)
    c.setFillColor(MUTED)
    c.setFont('Body',8)
    c.drawString(M,28,'Allgift Technologies Ltd  ·  30 October 2026  ·  v0.12.0-prototype')
    c.drawRightString(W-M,28,f'{number:02d} / 14')


def finish(top, number):
    if top>H-58:
        raise RuntimeError(f'Page {number} overflows: bottom {top:.1f}, limit {H-58:.1f}')
    print(f'Page {number}: content ends at {top:.1f} / {H-58:.1f}')


# 1 — Cover.
c.bookmarkPage('p1')
c.addOutlineEntry('Demonstration guide','p1',level=0)
c.setFillColor(IVORY)
c.rect(0,0,W,H,fill=1,stroke=0)
c.setFillColor(INK)
c.rect(0,H-508,W,508,fill=1,stroke=0)
label('ALLGIFT TECHNOLOGIES LTD',45,color=GOLD,size=10)
c.setFillColor(WHITE)
c.setFont('Display',42)
c.drawString(M,H-155,'LexFlow AI')
c.setFont('Display',31)
c.drawString(M,H-205,'Demonstration guide')
para('From source documents to reviewed,<br/>approved structured data.',244,kind='white')
c.setStrokeColor(GOLD)
c.setLineWidth(1)
c.line(M,H-323,W-M,H-323)
label('PRESENTER EDITION',346,color=GOLD,size=10)
para('A 15-minute core walkthrough, plus structured case preparation and the ProNotar extension foundation.',374,kind='white')
para('Version 0.12.0-prototype  ·  30 October 2026',454,kind='white')
top=label('THE STORY TO TELL',541)
top=para('Receive a document. Surface disagreement.<br/><b>Let a person decide. Keep the evidence.</b>',top)
nodes=['Receive','Extract','Review','Approve','Export']
gap=9
width=(CW-gap*4)/5
for index,name in enumerate(nodes):
    x=M+index*(width+gap)
    c.setFillColor(WHITE)
    c.roundRect(x,H-669,width,48,5,fill=1,stroke=0)
    c.setFillColor(TEAL)
    c.setFont('BodyBold',10)
    c.drawCentredString(x+width/2,H-649,name)
    if index<4:
        c.setFillColor(GOLD)
        c.setFont('BodyBold',10)
        c.drawCentredString(x+width+gap/2,H-649,'›')
top=para('Use the supplied fictional records throughout. NotaryDesk Demo demonstrates a signed HTTPS handoff; a live notary vendor is not connected.',699,kind='small')
top=para('This guide documents the working prototype. It does not claim production certification or measured client savings.',top,kind='small')
footer(1)
finish(top,1)


# 2 — Setup and timed route.
top=page(2,'Before the meeting','Prepare the demonstration','Use the Keller administrator account for the full walkthrough. Allow one rehearsal before presenting.')
top=para('<b>Local demo for this command:</b> <link href="http://127.0.0.1:3000" color="#1c6a5c">http://127.0.0.1:3000</link><br/>To start it from the project folder on Linux/macOS:',top)
top=code(['LEXFLOW_PORT=3000 ./start.sh'],top)
top=para('The launcher requires Python 3.12 and installs dependencies on first use. Docker (<b>docker compose up --build</b>) and Windows (<b>.\\start.ps1</b>) use port <b>8000</b> by default.',top,kind='small')
top=table(['Account','Use during the demonstration'],[
    ['admin@keller.demo','Review, approve, teach rules and record baselines'],
    ['reviewer@keller.demo','Review, approve and export'],
    ['assistant@keller.demo','Create/intake/prepare; approval is restricted'],
    ['admin@weber.demo','Show a separate office workspace'],
],[220,CW-220],top)
top=para('<b>Shared demo password:</b> <font name="Mono">LexFlowDemo2026!</font><br/>Use the current password if it was changed. If MFA is enabled, have an authenticator or unused recovery code ready.',top,kind='small')
top=table(['Time','Screen and purpose','Page'],[
    ['0:00–4:00','Opening, guided case, review and approval','3–4'],
    ['4:00–5:00','Generate an approved export','5'],
    ['5:00–6:30','Send to NotaryDesk Demo; inspect receipt','6'],
    ['6:30–8:30','Teach a reusable extraction label','7'],
    ['8:30–15:00','Pilot evidence, security and close','8–12'],
],[81,CW-146,65],top)
top=para('<b>Preflight:</b> sign in and locate <b>Start guided demo</b>; each run creates a fresh matter. Add five minutes for <b>Case details</b> and the bundle on pages 13–14.',top,kind='small',gap=0)
top=para('<b>Historical video:</b> <link href="LexFlow_AI_Presentation.html" color="#1c6a5c">Watch the v0.11 presentation</link>. Its narration and the screenshots retained here cover the earlier core workflow.',top+10,kind='small',gap=0)
finish(top,2)


# 3 — Start from the dashboard.
top=page(3,'01 / Opening and intake','Start a fresh case','The shortest convincing story starts with two documents that disagree about one important field.')
top=image('11-overview-hero.png',top,145,'The Overview screen introduces the source → human approval workflow.')
top=steps([
    ('Sign in.', 'Open the local demo, use the Keller admin account and select <b>Enter your workspace</b>.'),
    ('Create the scenario.', 'On <b>Overview</b>, select <b>Start guided demo</b>. A fresh “Demo — Sonnenallee property purchase” matter opens.'),
    ('Inspect the inputs.', 'Open the buyer questionnaire and fictional land-register extract in the source-document list. Point out the source names and extracted evidence.'),
    ('Show the exception.', 'Find <b>Land register / Grundbuch</b>. The field is marked <b>Conflict</b>; it contains two different source suggestions.'),
],top)
top=table(['Fictional document','Land-register value'],[
    ['01_buyer_questionnaire.txt','München Blatt 812'],
    ['02_land_register_conflict.txt','München Blatt 872'],
],[CW-190,190],top)
top=box('SAY TO THE AUDIENCE','“LexFlow turns incoming documents into structured suggestions and shows where sources disagree. The reviewer can inspect the evidence before making a decision.”',top)
top=para('<b>Optional intake extension:</b> create a <b>Property purchase</b> matter, go to <b>Document intake</b> and upload <b>samples/07_synthetic_property_purchase.pdf</b> or <b>08_synthetic_property_purchase.docx</b>. Use <b>Paste document text → Insert synthetic example</b> for a quick fallback.',top,kind='small')
finish(top,3)


# 4 — Review.
top=page(4,'02 / Human review','Resolve, verify, approve','In this fictional scenario, the presenter chooses Blatt 872 after inspecting the fictional land-register extract.')
top=image('12-source-suggestions.png',top,150,'Actual source suggestions from the synthetic rehearsal. Neither source is preselected for the conflict.')
top=steps([
    ('Resolve the disagreement.', 'Select <b>Review field</b> under Land register. Choose <b>München Blatt 872</b>, add a short review note and select <b>Confirm value</b>.'),
    ('Verify the remaining required fields.', 'Open each field, compare it with its source, then select <b>Confirm value</b>. A suggestion alone is not a confirmation.'),
    ('Approve the matter.', 'If case details were saved, confirm them first (page 14). Once all gates pass, select <b>Approve matter</b> and accept the dialog.'),
],top)
top=table(['Required field','Expected value in this example'],[
    ['Buyer / Käufer','Anna Schmidt'],
    ['Seller / Verkäufer','Peter Müller'],
    ['Purchase price / Kaufpreis','EUR 850,000.00 (display may be normalized)'],
    ['Property address / Objektadresse','Sonnenallee 24, 80331 München'],
    ['Land register / Grundbuch','München Blatt 872 — chosen by the reviewer'],
],[190,CW-190],top)
top=box('EXPECTED RESULT','All five required fields are confirmed and the matter becomes <b>Approved</b>. Every conflict must be resolved, including conflicts on optional fields. The review decision and note remain in the audit trail.',top)
finish(top,4)


# 5 — Export.
top=page(5,'03 / Controlled output','Generate approved data','Inspect the reviewed values and their destination field names before export.')
top=steps([
    ('Open the preview.', 'From the approved matter, select <b>Export approved data</b>.'),
    ('Select the output.', 'Choose <b>JSON — structured payload</b> and <b>Flat reviewed fields</b>. This exports extraction fields only; the complete bundle is on page 14.'),
    ('Generate and open the file.', 'Select <b>Generate export</b>. The browser downloads the file and the matter records the generated output.'),
    ('Show the alternative.', 'Repeat with <b>CSV — mapped key-value rows</b> if the audience wants a spreadsheet-friendly format. Find outputs again under <b>Transfers &amp; exports</b>.'),
],top)
top=subtitle('Example destination fields',top)
top=table(['Destination key','Reviewed value'],[
    ['Beteiligter.Kaeufer.Name','Anna Schmidt'],
    ['Vorgang.KaufpreisEUR','850000.00'],
    ['Immobilie.Anschrift','Sonnenallee 24, 80331 München'],
    ['Grundbuch.Blatt','München Blatt 872'],
],[CW-206,206],top)
top=code(['"connector": "approved_export",','"not_a_live_transmission": true'],top)
top=box('SAY TO THE AUDIENCE','“This is a real file generated from reviewed values. We can inspect the mapping and keep the output linked to its source matter. A downloadable export does not mean a vendor system received it.”',top)
top=subtitle('Show that approval stays meaningful',top)
top=para('Reopening a matter, adding documents or changing destination mappings requires renewed approval. Earlier outputs become superseded and further downloads are blocked. Downloaded copies remain outside the application’s control.',top)
top=para('Demonstrate re-review last; keep this approved matter available for the receiver demonstration.',top,kind='small')
finish(top,5)


# 6 — Receiver.
top=page(6,'04 / Integration evidence','Demonstrate a handoff','NotaryDesk Demo receives approved flat extraction fields and returns a signed receipt. Structured case records are not sent by this delivery flow.')
top=image('17-notary-handoff.png',top,220,'The isolated rehearsal produced an accepted NotaryDesk receipt. Case references will differ.')
top=steps([
    ('Choose the approved matter.', 'Open <b>Integrations</b>. Under <b>Preview a transfer</b>, select the Sonnenallee matter you just approved or exported.'),
    ('Preview before sending.', 'Set Destination to <b>NotaryDesk Demo (HTTPS)</b> and select <b>Dry run</b>. Inspect the mapped payload.'),
    ('Send deliberately.', 'Select <b>Send approved data</b>. The separate encrypted destination stores the case and returns a signed <b>accepted</b> receipt.'),
    ('Inspect the evidence.', 'Open <b>Transfer receipts</b>, then choose <b>Open demo notary</b>. Inspect the destination case and its <b>Delivery evidence</b> tab (page 11).'),
],top)
top=box('SAY TO THE AUDIENCE','“The demonstration destination has accepted this approved payload and returned a receipt. This demonstrates the handoff controls. Connecting a real notary vendor requires its supported interface and a configured destination.”',top)
top=para('<b>Optional integrations:</b> a signed HTTPS webhook adapter and a folder intake agent are included. The webhook requires operator configuration; the folder agent runs from <b>agents/folder_agent.py</b>. Native Outlook, Word and BNotK/XNP connectors are not connected.',top,kind='small')
finish(top,6)


# 7 — Learning.
top=page(7,'05 / Workflow learning','Teach a reusable label','Demonstrate a small, understandable rule that changes future intake while preserving human review.')
top=image('14-learning.png',top,150,'Workflow studio saves workspace-specific label rules with version history.')
top=steps([
    ('Open the studio.', 'Select <b>Workflow studio → Teach a field</b>.'),
    ('Define the rule.', 'Choose <b>Property purchase</b>, set <b>Extract into</b> to <b>Buyer / Käufer</b> and use the label <b>Erwerbende Person</b>.'),
    ('Test the example.', 'Enter the text below in <b>Example text · preview only</b>, then select <b>Test rule</b>. The preview should identify Anna Beispiel as the buyer.'),
],top)
top=code(['Erwerbende Person: Anna Beispiel'],top)
top=steps([
    ('Save and inspect.', 'Select <b>Save learned rule</b>. The table shows an enabled rule at <b>Version 1</b>. An administrator can pause it and inspect later versions.'),
    ('Prove future use.', 'Create a new <b>Property purchase</b> matter. Under <b>Document intake → Paste document text</b>, paste the same line and select <b>Extract structured fields</b>. Open the buyer field to see the learned suggestion; it still needs review.'),
],top,start=4)
top=box('SAY TO THE AUDIENCE','“We taught LexFlow how this office labels a buyer. We saved the label and field configuration, not the preview example as training data. Future matching documents receive suggestions for a person to verify.”',top)
top=para('If this rule already exists after rehearsal, demonstrate its preview and version history instead of saving a duplicate. Reviewers can test rules; only administrators save or pause them. Stored intake documents remain ordinary case records.',top,kind='small')
finish(top,7)


# 8 — Pilot.
top=page(8,'06 / Measuring value','Present evidence honestly','The dashboard distinguishes missing measurements, reported work time and actual transfer outcomes.')
top=image('15-pilot-comparison.png',top,115,'Synthetic rehearsal: time comparisons need recorded work, and acceptance is counted separately for each destination.')
top=steps([
    ('Choose the workflow.', 'Open <b>Pilot measurement</b> and select <b>Property purchase</b>.'),
    ('Explain the time comparison.', 'An administrator records an observed average and sample count under <b>Record measurements → Record your baseline</b>. Use <b>Record work time</b> or a matter’s work timer for actual sessions.'),
    ('Show the evidence export.', 'Select <b>Export evidence</b> to download the CSV report. If measurements are absent, explain the empty state.'),
],top)
top=table(['Metric','How to explain it'],[
    ['Extraction coverage','Required fields with a suggestion / required fields in matters with documents. This is coverage, not accuracy.'],
    ['Manual correction rate','Current confirmations that differ from every candidate / current confirmations.'],
    ['Low-confidence rate','Fields whose best candidate heuristic is below 0.90 / fields with candidates.'],
    ['Time and acceptance','Work sessions are summed per matter, then averaged. Acceptance is separated by destination.'],
],[154,CW-154],top)
top=box('SAY TO THE AUDIENCE','“The software can collect pilot evidence. Client savings must come from observed baseline and work-session data. A successful demonstration is not evidence of a live vendor’s reliability.”',top)
finish(top,8)


# 9 — Security and roles.
top=page(9,'07 / Trust and access','Explain the active controls','Open Security and show the configuration that is actually active in this demonstration.')
top=table(['Control','What to show or say'],[
    ['Passwords and sessions','Argon2 password hashes, sign-in limits, idle expiry and the option to sign out other sessions.'],
    ['Audit integrity','Security verifies the workspace HMAC chain. Select Audit checkpoint to download a checkpoint for separate storage.'],
    ['Document and export files','Workspace file encryption is optional and needs configured keys. Show its actual status on screen.'],
    ['HTTPS and database','The local HTTP demo does not use secure HTTPS cookies. SQLite and extracted text need encrypted-volume protection in deployment.'],
],[160,CW-160],top)
top=steps([
    ('Inspect the chain.', 'In <b>Security</b>, point out <b>Audit integrity</b> and select <b>Audit checkpoint</b>. Keep checkpoints outside the database to detect coordinated truncation.'),
    ('Inspect a decision.', 'Open <b>Audit trail</b>, find a field confirmation or approval and select <b>View decision details</b>.'),
    ('Optionally show isolation.', 'Sign out and sign in as <b>admin@weber.demo</b>. Keller matters should not appear. Return to the Keller administrator afterwards.'),
],top)
top=table(['Role','Review and output permissions'],[
    ['Admin','Confirms, approves, exports; manages rules, mappings and baselines.'],
    ['Reviewer','Confirms, approves and exports; previews rules.'],
    ['Analyst','Creates, ingests and prepares case records; cannot confirm, approve or generate exports.'],
],[107,CW-107],top)
top=box('SAY TO THE AUDIENCE','“The prototype makes its controls visible. A dedicated HTTPS deployment profile, provisioning and backup tools are included. Authenticator-app MFA is included (page 12). Hosting validation, SSO and independent certification remain deployment work.”',top)
finish(top,9)


# 10 — Closing, contingencies and checks.
top=page(10,'08 / Close and recover','Finish with a clear result','Close on the approved case, generated file, receipt and reviewer decision.')
top=box('CLOSING SCRIPT','“You have seen two source documents become reviewed structured data, a person resolve a conflict, an approved export and a signed demonstration handoff. The next pilot step is one supported vendor connection and observed office measurements.”',top)
top=subtitle('Presenter recovery notes',top)
top=table(['If this happens','Use this recovery'],[
    ['The page does not open','Run the launcher from page 2 on port 3000; default launchers use 8000. This is FastAPI, not Django runserver.'],
    ['Approve is disabled','Confirm required fields, resolve all conflicts and confirm saved case details. Analysts cannot approve.'],
    ['Export is superseded','Complete the required re-review, approve again and generate a new output.'],
    ['A learned label does not match','Check the matter type, chosen field, exact label and a colon or equals sign before the value. Keep the rule enabled.'],
    ['A scan has no useful text','Use the supplied digital PDF, DOCX or pasted synthetic text. Image recognition requires local OCR setup.'],
    ['There is no pilot saving yet','Explain that baseline or work-time evidence is missing. Enter measured observations when available.'],
],[166,CW-166],top)
top=subtitle('Optional account-recovery demonstration',top)
top=para('At sign-in, select <b>Forgot password?</b> and request a link for a seeded account. The local demo shows <b>Create a new password</b> on screen; no email is sent. Links expire after 30 minutes. A completed reset changes the password and closes that account’s sessions, so rehearse with a secondary demo account.',top,kind='small')
top=subtitle('Verification and supporting material',top)
top=para('<b>30 October 2026:</b> 134 backend tests and 26 UI logic tests passed. A synthetic browser rehearsal covered structured preparation through bundle download at widths 390, 768 and 1440. Earlier v0.11 checks covered 141 panel views; that broader run was not fully repeated.',top,kind='small')
top=para('Retained screenshots show v0.11; references and counts vary. See <b>README.md</b>, <b>docs/DEPLOYMENT.md</b> and <b>docs/TEST_PLAN.md</b>. Repository: <link href="https://github.com/BernardAli/Lexflow-B" color="#1c6a5c">BernardAli/Lexflow-B</link>.',top,kind='small',gap=0)
finish(top,10)

# 11 — Separate demo destination.
top=page(11,'09 / NotaryDesk Demo','Continue in the destination','A fictional case-management product with a working independent case store. Every handoff crosses verified local TLS.')
top=image('18-notary-desk.png',top,265,'The destination shows the approved values received from LexFlow and its own preparation stage.')
top=steps([
    ('Open the case register.', 'From <b>Integrations</b>, select <b>Open demo notary</b>. Choose the Sonnenallee case. The approved mapped values are read-only.'),
    ('Prepare the case.', 'In <b>Case details</b>, choose <b>In preparation</b> and select <b>Save case stage</b>. The case register and counts update.'),
    ('Inspect delivery evidence.', 'Open <b>Delivery evidence</b> to show the receipt, source approval and payload fingerprint. Follow the link back to the source matter.'),
],top)
top=box('SAY TO THE AUDIENCE','“This fictional destination keeps its own encrypted case and preparation stage. Delivery is signed and duplicate-protected. ProNotar is the planned vendor target; its version and import contract still need verification.”',top)
top=para('Reviewers and administrators can change stages; analysts have read access. The server rejects stale revisions and other workspaces’ case IDs. The destination is available only with demo seeding enabled.',top,kind='small')
finish(top,11)

# 12 — MFA, recovery and evaluation.
top=page(12,'10 / Reliability and access','Show the operational gains','Demonstrate account protection with a secondary synthetic account, then explain the verified recovery and evaluation tools.')
top=steps([
    ('Enroll an authenticator.', 'In <b>Settings → My account</b>, choose <b>Set up authenticator</b>. Confirm the password, enter the setup key in an authenticator app, and confirm its current code.'),
    ('Save recovery codes.', 'Keep the ten codes privately. Each can replace a second factor once. Sign out and sign in again to see the second-factor challenge.'),
    ('Respect the policy.', 'A hardened deployment requires enrollment before case access. Password reset preserves an existing factor. Use your saved factor or recovery code afterwards.'),
],top)
top=table(['Evidence','Verified result'],[
    ['Backup and restore','Authenticated file manifest, artifact/audit verification and restoration to a new path. Restored sessions are revoked; enrolled factors and case records survive.'],
    ['Interrupted transfer','The intent and original key survive. Same-key retry after receiver commit does not create a duplicate. Uncertain outcomes require destination inspection.'],
    ['Extraction benchmark','28 hand-authored synthetic text cases: precision 100%, recall 97.2%, F1 98.6%. Two damaged labels remain misses. Not an OCR or real-office accuracy claim.'],
    ['Release checks','134 backend and 26 UI logic tests pass. The structured-case browser flow passes at three widths. CI runs tests and the synthetic benchmark.'],
],[145,CW-145],top)
top=box('OPERATOR FOLLOW-UP','See <b>docs/DEPLOYMENT.md</b> for <b>backup</b>, <b>verify-backup</b>, <b>restore</b> and <b>deliver-pending</b> commands. The versioned synthetic dataset and report are in <b>evaluations/</b>. Keep external encryption and signing keys separately protected.',top)
top=para('Real-vendor integration, representative office evaluation, SSO and target infrastructure validation remain separate release milestones.',top,kind='small')
finish(top,12)

# 13 — Structured preparation.
top=page(13,'11 / Structured case preparation','Prepare the complete case','The v0.12 editor holds repeatable participants, properties and tasks. People prepare these records; flat extraction does not populate them automatically.')
top=steps([
    ('Open Case details.', 'Use a synthetic matter. If it is approved or exported, select <b>Reopen</b> first. This clears approval and supersedes earlier exports.'),
    ('Add participants.', 'Create each person or company separately, assign roles and enter known details. A representative link selects another person in this case.'),
    ('Add properties.', 'Enter each property with its register sheet, cadastral district, section, parcel, area and ownership share where known.'),
    ('Keep source evidence.', 'Link each participant/property to documents in this matter or enter a verification note. Compare the records with the extracted fields; they are not synchronized automatically.'),
    ('Set up the case.', 'Choose <b>Edit case setup</b>: category, office naming code, optional master case and template reference. <b>Use suggestion</b> proposes a handoff designation; it does not rename the matter.'),
    ('Record execution tasks.', 'Track tasks as pending, initiated or completed. These are preparation records; no notification, court submission or external action runs.'),
],top)
top=table(['Preparation choice','Boundary to explain'],[
    ['Six case categories','Handoff metadata; the four existing extraction workflows remain unchanged.'],
    ['Office references','Master-case links and template names are stored locally; no Word template or vendor case is created.'],
    ['Synthetic example','samples/09_structured_case.json illustrates the case model. It is not an intake upload or a ProNotar file.'],
],[145,CW-145],top)
top=box('REVIEW BEFORE APPROVAL','Analysts may prepare records. A reviewer/admin must confirm each saved revision, even an empty saved structure. Leave unknown facts blank and verify against source documents.',top)
finish(top,13)

# 14 — Structured review and extension boundary.
top=page(14,'12 / Complete output and extension','Review, export, extend','The complete JSON bundle is the stable input for a future vendor adapter. It carries reviewed records without claiming a successful ProNotar import.')
top=steps([
    ('Finish field review.', 'Confirm required extracted fields and resolve every conflict. Changing a field or adding source documents clears saved case review.'),
    ('Confirm case details.', 'As reviewer/admin, check participants, properties, sources and tasks, then select <b>Confirm case details</b>. Save conflicts require refreshing the current revision.'),
    ('Approve the matter.', 'Both field review and saved case review must pass. Case confirmation alone does not approve the matter.'),
    ('Download the complete bundle.', 'Select <b>Export approved data → Structured case bundle (JSON)</b>. Inspect the preview, generate the file and compare its records with the approved case.'),
],top)
top=table(['Output','What it includes'],[
    ['Structured case bundle','Participants, properties, tasks, case metadata, field review provenance and source hashes; no original document bytes or local paths.'],
    ['Flat exports and deliveries','Reviewed extraction fields only. JSON/CSV profiles and NotaryDesk/HTTPS delivery omit the new structured records.'],
    ['ProNotar32 target','Latest vendor-supported release policy. Exact build and import specification unverified; the adapter remains disabled.'],
],[145,CW-145],top)
top=box('NEXT INTEGRATION STEP','Obtain the supported ProNotar build, licensed modules, import schema and accepted sample files. Implement and test a serializer in an authorized test installation before enabling it. No ProNotar XML is generated today.',top)
top=para('The bundle digest detects content changes; it is not a digital signature or vendor receipt. See <b>docs/PRONOTAR_EXTENSION.md</b> for the adapter contract and <b>docs/API.md</b> for the revision-checked request sequence.',top,kind='small')
finish(top,14)

c.save()
print(OUTPUT)
