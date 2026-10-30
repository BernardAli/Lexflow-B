"""Build an offline, narrated 1080p presentation from the demonstration guide.

Requires Pillow, FFmpeg/FFprobe with libx264, libass and Flite, and DejaVu fonts.
The editable story is presentation_video.json. All speech is generated locally.
"""
import argparse
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import tempfile
import textwrap
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT, FPS, RATE = 1920, 1080, 25, 24000
INK, TEAL, GOLD, IVORY = '#142b30', '#1c6a5c', '#bb9b69', '#f5f5f0'
MUTED, LINE, PALE = '#5f716c', '#dce3dc', '#edf3ed'


def run(args):
    result = subprocess.run([str(v) for v in args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Command failed: ' + str(args[0]) + '\n' + result.stderr[-3000:])
    return result.stdout


def probe(path):
    return json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-show_chapters', '-of', 'json', path]))


def font(directory, size, kind='body'):
    filename = {'body':'DejaVuSans.ttf', 'bold':'DejaVuSans-Bold.ttf',
                'display':'DejaVuSerif.ttf', 'mono':'DejaVuSansMono.ttf'}[kind]
    return ImageFont.truetype(str(directory / filename), size)


def lines(text, selected_font, max_width):
    result = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split():
            value = (line + ' ' + word).strip()
            if selected_font.getlength(value) <= max_width:
                line = value
            elif line:
                result.append(line)
                line = word
            else:
                raise ValueError('A word does not fit in the presentation layout')
        result.append(line)
    return result


def text(draw, value, xy, selected_font, color, width, leading=None):
    x, y = xy
    leading = leading or round(selected_font.size * 1.35)
    for line in lines(value, selected_font, width):
        if selected_font.getlength(line) > width:
            raise ValueError('Text overflows its slide column: ' + line)
        draw.text((x, y), line, font=selected_font, fill=color)
        y += leading
    return y


def box(draw, bounds, fill='white', outline=LINE, radius=18):
    draw.rounded_rectangle(bounds, radius=radius, fill=fill, outline=outline, width=2)


def render(scene, index, total, fonts, output):
    dark = scene['visual'] == 'cover'
    frame = Image.new('RGB', (WIDTH, HEIGHT), INK if dark else IVORY)
    draw = ImageDraw.Draw(frame)
    f = lambda size, kind='body': font(fonts, size, kind)
    draw.text((90, 47), 'LEXFLOW AI', font=f(30, 'bold'), fill='white' if dark else INK)
    draw.text((1160, 55), 'PRESENTATION GUIDE  /  v0.11', font=f(22), fill=GOLD if dark else MUTED)
    draw.text((1745, 52), f'{index+1:02d} / {total:02d}', font=f(22, 'bold'), fill=GOLD)
    draw.line((90, 108, 1830, 108), fill=GOLD, width=2)
    if dark:
        draw.text((95, 180), 'REVIEWED. APPROVED. TRACEABLE.', font=f(24, 'bold'), fill=GOLD)
        text(draw, scene['title'], (90, 270), f(84, 'display'), 'white', 1720, 110)
        text(draw, 'From source documents to a signed demonstration handoff.', (96, 545), f(34), '#dce3dc', 1600)
        for n, label in enumerate(('Receive', 'Extract', 'Review', 'Approve', 'Hand off')):
            x = 96 + n * 347
            box(draw, (x, 686, x+312, 790), fill='#203c40', outline='#3b5658')
            draw.text((x+25, 702), f'0{n+1}', font=f(20, 'bold'), fill=GOLD)
            draw.text((x+25, 735), label, font=f(28, 'bold'), fill='white')
        draw.text((96, 843), 'Synthetic records  ·  Fictional destination  ·  Human approval', font=f(25), fill='#c8d4cd')
    else:
        draw.text((90, 153), scene['section'].upper(), font=f(22, 'bold'), fill=TEAL)
        title_end = text(draw, scene['title'], (90, 215), f(57, 'display'), INK, 710, 77)
        if title_end > 390:
            raise ValueError('Slide heading is too tall: ' + scene['id'])
        y = 423
        for number, bullet in enumerate(scene['bullets'], 1):
            draw.ellipse((94, y+7, 130, y+43), fill=TEAL)
            draw.text((105, y+10), str(number), font=f(19, 'bold'), fill='white')
            y = text(draw, bullet, (153, y), f(28), INK, 607, 39) + 30
        if y > 828:
            raise ValueError('Slide bullets exceed the available height: ' + scene['id'])
        box(draw, (846, 198, 1830, 836))
        draw.text((878, 221), 'WORKING PROTOTYPE  /  SYNTHETIC EXAMPLE', font=f(19, 'bold'), fill=MUTED)
        visual = scene['visual']
        if visual == 'image':
            with Image.open(ROOT / 'assets' / scene['image']) as original:
                source = original.convert('RGB')
            if scene.get('crop'):
                source = source.crop(scene['crop'])
            image = ImageOps.contain(source, (916, 505), Image.Resampling.LANCZOS)
            x, y_image = 880+(916-image.width)//2, 285+(505-image.height)//2
            frame.paste(image, (x, y_image))
            draw.rounded_rectangle((x-1, y_image-1, x+image.width+1, y_image+image.height+1), radius=3, outline=LINE, width=2)
        elif visual == 'conflict':
            for n, (label, value, selected) in enumerate((('Questionnaire', 'Blatt 812', False), ('Register extract', 'Blatt 872', True))):
                top = 300+n*202
                box(draw, (882, top, 1794, top+165), fill=PALE if selected else IVORY, outline=TEAL if selected else LINE)
                draw.text((915, top+22), label.upper(), font=f(22, 'bold'), fill=MUTED)
                draw.text((915, top+66), value, font=f(53, 'display'), fill=INK)
                if selected:
                    draw.text((1485, top+80), 'REVIEWED', font=f(22, 'bold'), fill=TEAL)
            draw.text((915, 734), 'Source selection + reviewer + note + time', font=f(25), fill=TEAL)
        elif visual == 'mapping':
            box(draw, (880, 291, 1794, 711), fill=INK, outline=INK)
            code = ['APPROVED JSON / CSV', '', 'Buyer          Anna Schmidt', 'Price (EUR)    850000.00', 'Property       Sonnenallee 24', 'Register       München Blatt 872']
            for n, line in enumerate(code):
                draw.text((917, 320+n*54), line, font=f(28, 'mono'), fill=GOLD if n==0 else 'white')
            draw.text((917, 755), 'Mapped values, generated from human review.', font=f(25), fill=TEAL)
        elif visual in ('metrics', 'closing'):
            values = [('100%', 'Precision'), ('97.2%', 'Recall'), ('98.6%', 'F1')] if visual=='metrics' else [('111', 'Backend tests'), ('21', 'UI tests'), ('141', 'Browser views')]
            for n, (value, label) in enumerate(values):
                x = 882+n*308
                box(draw, (x, 321, x+290, 530), fill=PALE)
                draw.text((x+20, 352), value, font=f(58, 'display'), fill=TEAL)
                draw.text((x+20, 455), label, font=f(24, 'bold'), fill=INK)
            heading = 'SYNTHETIC TEXT REGRESSION SET' if visual=='metrics' else 'LOCAL RELEASE VERIFICATION'
            draw.text((906, 589), heading, font=f(23, 'bold'), fill=INK)
            description = '28 hand-authored cases.\nTwo damaged labels remain misses.\nNo OCR or real-office accuracy claim.' if visual=='metrics' else 'A supported vendor connection.\nRepresentative office evaluation.\nValidated deployment and recovery.'
            text(draw, description, (906, 641), f(27), MUTED, 846, 45)
        else:
            cards = [('01', 'Authenticator + recovery', 'Required before case access in hardened mode.'), ('02', 'Session and role controls', 'Approval and delivery require reviewer access.'), ('03', 'Audit verification', 'Keep checkpoints outside the local database.')] if visual=='security' else [('01', 'Durable transfer intent', 'Retry the original key after checking the outcome.'), ('02', 'Authenticated snapshot', 'Verify files, audit history and encrypted records.'), ('03', 'Portable restore', 'New paths. Revoked sessions. Preserved evidence.')]
            for n, (number, heading, description) in enumerate(cards):
                top = 295+n*166
                box(draw, (882, top, 1794, top+143), fill=PALE)
                draw.text((909, top+21), number, font=f(22, 'bold'), fill=GOLD)
                draw.text((969, top+19), heading, font=f(29, 'bold'), fill=INK)
                text(draw, description, (969, top+70), f(23), MUTED, 789, 32)
        end = text(draw, scene['detail'], (94, 870), f(22), MUTED, 1730, 29)
        if end > 924:
            raise ValueError('Slide detail is too long: ' + scene['id'])
    draw.rectangle((0, 925, WIDTH, HEIGHT), fill=INK)
    draw.line((90, 1070, 1830, 1070), fill='#3b5658', width=1)
    for n in range(total):
        x = 90+n*(1740/total)
        draw.rectangle((x, 1070, x+1740/total-4, 1077), fill=GOLD if n<=index else '#3b5658')
    pages = ', '.join(str(p) for p in scene['pages'])
    draw.text((93, 1041), 'Guide p. '+pages, font=f(16), fill='#a7bdb1')
    frame.save(output)
    return frame


def silence(seconds):
    return b'\0' * round(seconds*RATE) * 2


def speech(scene, directory, voice, silent=False):
    directory.mkdir(parents=True, exist_ok=True)
    raw, cues, offset = [silence(.7)], [], .7
    for n, sentence in enumerate(scene['narration']):
        if silent:
            duration = max(3.5, len(sentence.split()) / 2.4)
            spoken = silence(duration)
        else:
            source, target = directory/f'line-{n}.txt', directory/f'line-{n}.wav'
            source.write_text(sentence, encoding='utf-8')
            source_filter = str(source).replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
            run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f"flite=textfile='{source_filter}':voice={voice}",
                 '-af', 'atempo=1.04,highpass=f=65,alimiter=limit=0.93:level=false', '-ar', RATE, '-ac', '1', '-c:a', 'pcm_s16le', target])
            with wave.open(str(target), 'rb') as stream:
                if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) != (RATE, 1, 2):
                    raise ValueError('Unexpected synthesized audio format')
                spoken = stream.readframes(stream.getnframes())
            duration = len(spoken)/(RATE*2)
        cues.append({'start':offset, 'end':offset+duration, 'text':sentence})
        raw.extend((spoken, silence(.18)))
        offset += duration+.18
    raw.append(silence(.82))
    audio = b''.join(raw)
    duration = math.ceil(len(audio)/(RATE*2)*FPS)/FPS
    audio += silence(duration-len(audio)/(RATE*2))
    output = directory/'narration.wav'
    with wave.open(str(output), 'wb') as stream:
        stream.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        stream.writeframes(audio)
    return output, duration, cues


def timestamp(seconds, ass=False):
    scale = 100 if ass else 1000
    count = round(seconds*scale)
    hours, count = divmod(count, 3600*scale)
    minutes, count = divmod(count, 60*scale)
    whole, fraction = divmod(count, scale)
    return f'{hours:01d}:{minutes:02d}:{whole:02d}.{fraction:02d}' if ass else f'{hours:02d}:{minutes:02d}:{whole:02d}.{fraction:03d}'


def captions(cues, path):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,34,&H00FFFFFF,&H00FFFFFF,&H00302B14,&H00302B14,0,0,0,0,100,100,0,0,1,0,0,2,150,150,57,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    rows = []
    for cue in cues:
        value = cue['text'].replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}')
        wrapped = '\\N'.join(textwrap.wrap(value, width=87, break_long_words=False))
        rows.append(f"Dialogue: 0,{timestamp(cue['start'],True)},{timestamp(cue['end'],True)},Caption,,0,0,0,,{wrapped}")
    path.write_text(header+'\n'.join(rows)+'\n', encoding='utf-8')


def write_player(output, poster, manifest, story):
    e = html.escape
    chapter_buttons = ''.join(f'<button type="button" data-start="{c["start"]}"><span>{int(c["start"])//60}:{int(c["start"])%60:02d}</span>{e(c["title"])}</button>' for c in manifest['chapters'])
    transcript = ''.join(f'<section><h3>{e(s["title"].replace(chr(10)," "))}</h3><p>{e(" ".join(s["narration"]))}</p></section>' for s in story['scenes'])
    page = '''<!doctype html><html lang="en"><head><link rel="icon" href="data:,"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LexFlow AI · Presentation video</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f5f0;color:#142b30;font:16px/1.7 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:40px 24px 70px}a{color:#1c6a5c}header{margin-bottom:24px}.eyebrow{color:#5f716c;letter-spacing:.12em;font-size:12px;font-weight:700}h1{font:40px/1.2 Georgia,serif;margin:14px 0}h2{font:28px Georgia,serif}video{display:block;width:100%;background:#142b30;border-radius:12px}.intro{max-width:860px;color:#5f716c}.links{display:flex;gap:22px;flex-wrap:wrap;margin:18px 0}.chapters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:20px 0 35px}button{font:inherit;font-size:14px;color:#142b30;border:1px solid #dce3dc;border-radius:8px;background:white;padding:14px;text-align:left;cursor:pointer}button span{display:block;font-size:12px;color:#5f716c}button[aria-current=true]{border-color:#1c6a5c;background:#edf3ed}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #bb9b69;outline-offset:4px}details{border:1px solid #dce3dc;border-radius:10px;padding:20px;background:#fff}summary{cursor:pointer;font-weight:700}h3{margin:25px 0 5px}section p{margin-top:5px}.note{font-size:13px;color:#5f716c}@media(max-width:700px){main{padding:24px 15px}h1{font-size:31px}.chapters{grid-template-columns:1fr 1fr}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style></head><body><main><header><p class="eyebrow">ALLGIFT TECHNOLOGIES LTD · HISTORICAL LEXFLOW AI v0.11 WALKTHROUGH</p><h1>From documents to an approved handoff.</h1><p class="intro">This narrated v0.11 presentation uses synthetic records and the fictional NotaryDesk Demo. It predates the v0.12 structured-case editor and bundle; see the current 14-page guide for those steps. English narration is generated locally with Flite, with captions included in the video picture.</p></header>
<video id="presentation" controls playsinline preload="metadata" poster="POSTER" aria-label="LexFlow AI narrated presentation"><source src="VIDEO" type="video/mp4">Download the presentation using the link below.</video>
<nav class="links" aria-label="Presentation downloads"><a href="VIDEO" download>Download MP4</a><a href="CAPTIONS" download>English captions (WebVTT)</a><a href="LexFlow_AI_Demonstration_Guide.pdf">Current v0.12 guide (14 pages)</a><a href="SOURCEPDF">Original v0.11 guide (12 pages)</a><a href="../README.md">Project documentation</a></nav>
<h2>Chapters</h2><div class="chapters">CHAPTERS</div><details><summary>Read the full narration transcript</summary>TRANSCRIPT</details><p class="note">This is a presentation of the documented prototype, not a live screen recording or a production certification. Real vendor integration and deployment validation remain future milestones.</p></main><script>
const video=document.querySelector('video');const buttons=[...document.querySelectorAll('[data-start]')];buttons.forEach(button=>button.addEventListener('click',()=>{video.currentTime=Number(button.dataset.start);video.play().catch(()=>{});}));video.addEventListener('timeupdate',()=>{const active=buttons.findLast(button=>Number(button.dataset.start)<=video.currentTime);buttons.forEach(button=>button.setAttribute('aria-current',String(button===active)));});
</script></body></html>'''
    page = page.replace('POSTER', e(poster.name)).replace('VIDEO', e(output.name)).replace('CAPTIONS', e(output.with_suffix('.vtt').name)).replace('SOURCEPDF', e(story['source_pdf'])).replace('CHAPTERS', chapter_buttons).replace('TRANSCRIPT', transcript)
    output.with_suffix('.html').write_text(page, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--story', type=Path, default=ROOT/'presentation_video.json')
    parser.add_argument('--output', type=Path, default=ROOT/'LexFlow_AI_Presentation.mp4')
    parser.add_argument('--font-dir', type=Path, default=Path('/usr/share/fonts/truetype/dejavu'))
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--voice', choices=['slt','rms','awb','kal','kal16'], default='slt')
    parser.add_argument('--silent', action='store_true', help='Create captioned video without speech synthesis')
    parser.add_argument('--preview-only', action='store_true', help='Render layout previews without encoding video')
    args = parser.parse_args()
    story = json.loads(args.story.read_text())
    if story.get('format') != 'lexflow-presentation-story-v1' or not story.get('scenes'):
        parser.error('Provide a valid presentation story')
    work = args.work_dir.expanduser().resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix='lexflow-video-'))
    work.mkdir(parents=True, exist_ok=True)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, scene in enumerate(story['scenes']):
        path = work/f'slide-{index:02d}.png'
        frames.append(render(scene, index, len(story['scenes']), args.font_dir, path))
    contact = Image.new('RGB', (1280, math.ceil(len(frames)/3)*260), IVORY)
    for index, frame in enumerate(frames):
        contact.paste(ImageOps.contain(frame, (420,237)), ((index%3)*426,(index//3)*260))
    contact.save(work/'contact-sheet.jpg', quality=90)
    poster = output.with_suffix('.jpg')
    frames[0].save(poster, quality=92, optimize=True)
    print('Slide previews: '+str(work/'contact-sheet.jpg'), flush=True)
    if args.preview_only:
        return
    for name in ('ffmpeg','ffprobe'):
        if not shutil.which(name):
            parser.error('Install '+name+' to encode this presentation')
    manifest = {'format':'lexflow-presentation-video-v1', 'version':story['version'], 'source_pdf':story['source_pdf'],
                'source_pdf_sha256':hashlib.sha256((ROOT/story['source_pdf']).read_bytes()).hexdigest(),
                'story_sha256':hashlib.sha256(args.story.read_bytes()).hexdigest(), 'width':WIDTH, 'height':HEIGHT,
                'fps':FPS, 'narration':'silent' if args.silent else 'local synthetic English / Flite '+args.voice,
                'captions':'burned into picture; WebVTT sidecar supplied', 'synthetic_content':True, 'chapters':[]}
    offset, all_cues, segments = 0.0, [], []
    for index, scene in enumerate(story['scenes']):
        directory = work/f'scene-{index:02d}'
        audio, duration, cues = speech(scene, directory, args.voice, args.silent)
        ass, segment = directory/'captions.ass', directory/'segment.mp4'
        captions(cues, ass)
        escaped = str(ass).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
        color = '0x142b30' if scene['visual']=='cover' else '0xf5f5f0'
        video_filter = f"fade=t=in:st=0:d=0.4:color={color},fade=t=out:st={duration-.4}:d=0.4:color={color},ass=filename='{escaped}'"
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',FPS,'-i',work/f'slide-{index:02d}.png','-i',audio,
             '-vf',video_filter,'-t',f'{duration:.3f}','-c:v','libx264','-preset','veryfast','-tune','stillimage','-crf','21',
             '-pix_fmt','yuv420p','-r',FPS,'-c:a','aac','-b:a','128k','-ar','48000','-ac','1','-movflags','+faststart',segment])
        actual_duration = float(probe(segment)['format']['duration'])
        title = scene['title'].replace('\n',' ')
        manifest['chapters'].append({'id':scene['id'], 'title':title, 'start':round(offset,3), 'duration':round(actual_duration,3), 'source_pages':scene['pages']})
        all_cues.extend({'start':cue['start']+offset,'end':cue['end']+offset,'text':cue['text']} for cue in cues)
        offset += actual_duration
        segments.append(segment)
        print(f'Encoded {index+1:02d}/{len(frames):02d}: {title} ({actual_duration:.1f}s)', flush=True)
    concat = work/'segments.txt'
    concat.write_text(''.join("file '"+str(path).replace("'", "'\\''")+"'\n" for path in segments))
    metadata = work/'chapters.txt'
    rows = [';FFMETADATA1','title=LexFlow AI — From documents to an approved handoff','artist=Allgift Technologies Ltd','comment=Narrated presentation of synthetic demonstration guide v0.11; locally generated Flite speech.']
    for chapter in manifest['chapters']:
        title = re.sub(r'([\\=;#])', r'\\\1', chapter['title'])
        rows += ['[CHAPTER]','TIMEBASE=1/1000',f'START={round(chapter["start"]*1000)}',f'END={round((chapter["start"]+chapter["duration"])*1000)}','title='+title]
    metadata.write_text('\n'.join(rows)+'\n', encoding='utf-8')
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',concat,'-i',metadata,
         '-map','0:v:0','-map','0:a:0','-map_metadata','1','-map_chapters','1','-c','copy','-movflags','+faststart',output])
    details = probe(output)
    manifest.update(duration_seconds=float(details['format']['duration']),bytes=output.stat().st_size)
    output.with_suffix('.metadata.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    vtt = ['WEBVTT','']
    for cue in all_cues:
        vtt += [timestamp(cue['start'])+' --> '+timestamp(cue['end']),cue['text'],'']
    output.with_suffix('.vtt').write_text('\n'.join(vtt),encoding='utf-8')
    write_player(output, poster, manifest, story)
    print(json.dumps({'video':str(output),'seconds':manifest['duration_seconds'],'megabytes':round(output.stat().st_size/1024**2,2),'chapters':len(manifest['chapters'])}),flush=True)


if __name__ == '__main__':
    main()
