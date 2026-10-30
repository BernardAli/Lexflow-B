"""Build the source-cited EU safety/security roadmap PDF, without runtime changes.

Usage: python docs/build_eu_security_blueprint.py [--output PATH]
Requires docs/requirements-pdf.txt and the system DejaVu TrueType fonts.
Content and references live in eu_security_blueprint.json.
"""
import argparse
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfdoc import PDFString
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'LexFlow_EU_Safety_Security_Blueprint.pdf')
parser.add_argument('--font-dir', type=Path, default=Path('/usr/share/fonts/truetype/dejavu'))
args = parser.parse_args()
data = json.loads((ROOT / 'eu_security_blueprint.json').read_text())
for name, filename in [('Body', 'DejaVuSans.ttf'), ('Bold', 'DejaVuSans-Bold.ttf'),
                       ('Serif', 'DejaVuSerif.ttf'), ('Italic', 'DejaVuSans-Oblique.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(args.font_dir / filename)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold', italic='Italic', boldItalic='Bold')
W, H = A4
M = 44
CW = W - 2*M
GREEN = colors.HexColor('#173d35')
INK = colors.HexColor('#203c36')
MUTED = colors.HexColor('#5b6f65')
GOLD = colors.HexColor('#b49762')
PAPER = colors.HexColor('#f8f7f2')
PALE = colors.HexColor('#eaf0e7')
LINE = colors.HexColor('#d9dfd5')
AMBER = colors.HexColor('#f1eadb')
WHITE = colors.white
styles = {
    'body': ParagraphStyle('body', fontName='Body', fontSize=10.4, leading=15.4, textColor=INK, spaceAfter=0),
    'small': ParagraphStyle('small', fontName='Body', fontSize=8.5, leading=12.4, textColor=MUTED),
    'table': ParagraphStyle('table', fontName='Body', fontSize=9.0, leading=12.7, textColor=INK),
    'th': ParagraphStyle('th', fontName='Bold', fontSize=8.6, leading=12, textColor=WHITE),
    'heading': ParagraphStyle('heading', fontName='Bold', fontSize=12, leading=16, textColor=GREEN),
    'title': ParagraphStyle('title', fontName='Serif', fontSize=29, leading=33, textColor=GREEN),
    'white': ParagraphStyle('white', fontName='Body', fontSize=11, leading=17, textColor=WHITE),
}
output = args.output.expanduser().resolve()
output.parent.mkdir(parents=True, exist_ok=True)
c = canvas.Canvas(str(output), pagesize=A4, pageCompression=1, invariant=1)
c.setTitle(data['title'])
c.setAuthor('Allgift Technologies Ltd — LexFlow AI project')
c.setSubject('Evidence-based implementation roadmap for EU and German notarial safety, security and privacy requirements; not a compliance certification')
c.setCreator('LexFlow documentation / ReportLab')
c.setKeywords('LexFlow, GDPR, AI Act, CRA, NIS2, BNotO, ProNotar, security, compliance roadmap')
c._doc.Catalog.Lang = PDFString('en-GB')
c.setDateFormatter(lambda *_: 'D:20261030000000Z')
page_stats = []
overflows = []
source_by_id = {s['id']:s for s in data['sources']}


def rich(text):
    for sid, ref in source_by_id.items():
        text = text.replace(f'[{sid}]', f'<link href="{escape(ref["url"], {chr(34): "&quot;"})}" color="#416e59">[{sid}]</link>')
    return text


def p(text, y, x=M, width=CW, kind='body', gap=9):
    obj = Paragraph(rich(text), styles[kind])
    _, h = obj.wrap(width, H)
    obj.drawOn(c, x, H-y-h)
    return y+h+gap


def label(text, y, color=GOLD, x=M, size=8.6):
    c.setFillColor(color)
    c.setFont('Bold', size)
    c.drawString(x, H-y-size, text)
    return y+size+12


def mark(x, y, color=GREEN):
    c.setFillColor(color)
    for offset, height in [(0,24),(8,17),(16,10)]:
        if offset==16:c.setFillColor(GOLD)
        c.rect(x+offset, y, 4.5, height, stroke=0, fill=1)


def footer(number):
    c.setStrokeColor(LINE)
    c.line(M, 45, W-M, 45)
    c.setFillColor(MUTED)
    c.setFont('Body', 7.3)
    c.drawString(M, 30, '30 OCT 2026  /  v0.12 prototype  /  Planning document')
    c.drawRightString(W-M, 30, f'{number:02d} / {len(data["pages"])+1:02d}')


def base(page, number):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    mark(M, H-53)
    c.setFont('Bold', 9.5)
    c.setFillColor(GREEN)
    c.drawString(M+31, H-44, 'LexFlow AI')
    c.setFont('Body', 7.6)
    c.setFillColor(MUTED)
    c.drawRightString(W-M, H-42, 'EU SAFETY & SECURITY BLUEPRINT')
    c.setStrokeColor(LINE)
    c.line(M, H-66, W-M, H-66)
    c.bookmarkPage(page['id'])
    c.addOutlineEntry(page['title'].replace('<br/>', ' '), page['id'], level=0)
    y = label(page['kicker'], 85, color=MUTED)
    y = p(page['title'], y, kind='title', gap=15)
    if page.get('intro'):y = p(page['intro'], y, gap=16)
    footer(number)
    return y


def table(block, y):
    widths = [CW*x/sum(block['widths']) for x in block['widths']]
    cells = [[Paragraph(rich(str(v)), styles['th']) for v in block['headers']]]
    cells += [[Paragraph(rich(str(v)), styles['table']) for v in row] for row in block['rows']]
    t = Table(cells, colWidths=widths, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),GREEN), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,colors.HexColor('#f0f2ec')]),
        ('LEFTPADDING',(0,0),(-1,-1),9), ('RIGHTPADDING',(0,0),(-1,-1),9),
        ('TOPPADDING',(0,0),(-1,-1),6.5), ('BOTTOMPADDING',(0,0),(-1,-1),6.5),
        ('LINEBELOW',(0,1),(-1,-1),0.35,LINE),
    ]))
    _, h = t.wrap(CW,H)
    t.drawOn(c,M,H-y-h)
    return y+h+15


def box(block,y):
    title = Paragraph(block['title'],styles['heading'])
    text = Paragraph(rich(block['text']),styles['body'])
    _, h1=title.wrap(CW-30,H)
    _, h2=text.wrap(CW-30,H)
    h=h1+h2+36
    c.setFillColor(AMBER if block.get('tone')=='amber' else PALE)
    c.roundRect(M,H-y-h,CW,h,5,fill=1,stroke=0)
    title.drawOn(c,M+15,H-y-13-h1)
    text.drawOn(c,M+15,H-y-22-h1-h2)
    return y+h+14


def flow(block,y):
    # Two explicit lanes distinguish deployed boundaries from proposed controls.
    for lane in block['lanes']:
        y=label(lane['label'],y,color=MUTED,size=8)
        count=len(lane['nodes']); gap=16; width=(CW-gap*(count-1))/count; height=72
        for i,(title,text) in enumerate(lane['nodes']):
            x=M+i*(width+gap)
            c.setFillColor(WHITE);c.setStrokeColor(LINE)
            c.roundRect(x,H-y-height,width,height,5,fill=1,stroke=1)
            p(title,y+12,x+10,width-20,'heading',0)
            p(text,y+36,x+10,width-20,'small',0)
            if i<count-1:
                c.setStrokeColor(GOLD);xx=x+width+3;yy=H-y-height/2
                c.line(xx,yy,xx+10,yy);c.line(xx+7,yy+3,xx+10,yy);c.line(xx+7,yy-3,xx+10,yy)
        y+=height+12
    return y


def cover():
    c.setFillColor(GREEN);c.rect(0,0,W,H,fill=1,stroke=0)
    c.setStrokeColor(colors.HexColor('#36574a'))
    for radius in (155,190,225):c.circle(W-25,H-65,radius,stroke=1,fill=0)
    mark(M,H-83,WHITE)
    c.setFont('Bold',19);c.setFillColor(WHITE);c.drawString(M+35,H-77,'LexFlow AI')
    label('ASSURANCE BLUEPRINT  /  OCTOBER 2026',137,color=GOLD,size=9)
    title=Paragraph('EU safety,<br/>security &amp;<br/>data protection.',ParagraphStyle('cover',fontName='Serif',fontSize=42,leading=48,textColor=WHITE))
    _,h=title.wrap(CW,H);title.drawOn(c,M,H-184-h)
    p('A practical path to high-assurance software<br/>for German notarial workflows.',365,width=CW-25,kind='white')
    c.setStrokeColor(GOLD);c.line(M,H-445,M+75,H-445)
    p('From the v0.12 prototype to a controlled, independently assessed deployment: regulatory scope, engineering safeguards, operating responsibilities and evidence for release.',470,width=CW-35,kind='white')
    for i,(title,text) in enumerate([('PROTECT','Confidential information'),('VERIFY','Sources and decisions'),('DEMONSTRATE','Controls and evidence')]):
        x=M+i*174
        label(title,591,color=GOLD,x=x,size=8)
        p(text,614,x=x,width=155,kind='white')
    c.setFillColor(colors.HexColor('#c3cdbf'));c.setFont('Body',8.8)
    c.drawString(M,99,'Prepared for Allgift Technologies Ltd')
    c.drawString(M,82,'Assessment date: 30 October 2026  |  Project: v0.12.0-prototype')
    c.setFillColor(GOLD);c.setFont('Bold',8.3)
    c.drawString(M,53,'IMPLEMENTATION ROADMAP — NOT A CERTIFICATION OR LEGAL OPINION')
    c.bookmarkPage('cover');c.addOutlineEntry('Cover','cover',level=0)
    c.showPage()


cover()
for number,page in enumerate(data['pages'],2):
    y=base(page,number)
    for b in page['blocks']:
        if b['type']=='p':y=p(b['text'],y,kind=b.get('style','body'))
        elif b['type']=='h':y=p(b['text'],y+4,kind='heading',gap=7)
        elif b['type']=='table':y=table(b,y)
        elif b['type']=='box':y=box(b,y)
        elif b['type']=='flow':y=flow(b,y)
        elif b['type']=='sources':
            for sid in b['ids']:
                s=source_by_id[sid]
                y=p(f'<b>[{sid}]</b> <link href="{escape(s["url"], {chr(34): "&quot;"})}" color="#173d35">{escape(s["title"])}</link>',y,gap=3)
                y=p(escape(s['note']),y,kind='small',gap=13)
        else:raise ValueError(f'Unknown block: {b["type"]}')
    if y>H-66:
        overflows.append(f'Page {number} ({page["id"]}): {y:.1f} > {H-66:.1f}')
    page_stats.append({'page':number,'id':page['id'],'content_bottom':round(y,1)})
    c.showPage()
if overflows:raise RuntimeError('Content overflows: ' + '; '.join(overflows))
c.save()
manifest={'title':data['title'],'assessment_date':data['assessment_date'],'project_version':data['project_version'],
          'pdf_sha256':hashlib.sha256(output.read_bytes()).hexdigest(), 'page_count':len(data['pages'])+1,
          'source_sha256':hashlib.sha256((ROOT/'eu_security_blueprint.json').read_bytes()).hexdigest(),
          'page_layout':page_stats,'evidence':[]}
for relative in data['evidence_files']:
    file=ROOT.parent/relative
    manifest['evidence'].append({'path':relative,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
output.with_suffix('.metadata.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(f'Built {output.name}: {len(data["pages"])+1} pages; all content fits within page boundaries.')
