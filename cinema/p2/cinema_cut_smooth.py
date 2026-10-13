#!/usr/bin/env python3
# cinema_cut_smooth.py (v1.2 + 3x pre-scale for jitter-free stills) (caption chunks no longer overlap): Kling clips -> TikTok short-drama variants (A/B/C), covers, -14 LUFS. TikTok-only.
# usage: python3 cinema_cut.py cut.json            (render)
#        python3 cinema_cut.py cut.json --check    (MASA gate + craft checks only, no render)
import json, os, re, subprocess, sys, shutil, tempfile
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
FONT = '/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'
BLUE, GOLD = (27, 69, 131), (184, 134, 43)
BANNED = r'^\s*(remember to|it\'?s important|make sure|don\'?t forget|you should|always|never)\b'

def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: sys.exit('FFMPEG FAIL: ' + ' '.join(cmd[:6]) + '\n' + r.stderr[-1500:])
    return r

def probe(p):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height', '-of', 'json', p], capture_output=True, text=True).stdout or '{}')
    v = [s for s in j.get('streams', []) if s.get('codec_type') == 'video']
    a = [s for s in j.get('streams', []) if s.get('codec_type') == 'audio']
    return float(j.get('format', {}).get('duration', 0)), (v[0]['width'], v[0]['height']) if v else (0, 0), bool(a)

def font(n): return ImageFont.truetype(FONT, n)

def wrap(d, text, f, maxw):
    out, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else: out.append(cur); cur = w
    if cur: out.append(cur)
    return out

def png_text(path, text, size, y, fill=(255, 255, 255), stroke=7, box=None, maxw=940):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = font(size)
    lines = wrap(d, text, f, maxw); lh = int(size * 1.18)
    if box:
        tw = max(d.textlength(l, font=f) for l in lines)
        d.rounded_rectangle([W / 2 - tw / 2 - 36, y - 22, W / 2 + tw / 2 + 36, y + lh * len(lines) + 14], radius=34, fill=box)
    for i, l in enumerate(lines):
        d.text((W / 2, y + i * lh), l, font=f, fill=fill, anchor='ma', stroke_width=0 if box else stroke, stroke_fill=(0, 0, 0))
    im.save(path)

def png_badge(path, text):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = font(34)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([40, 150, 40 + tw + 48, 150 + 62], radius=31, fill=BLUE + (235,))
    d.text((64, 162), text, font=f, fill=(255, 255, 255))
    im.save(path)

def png_endcard(path, ec, base):
    im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
    for yy in range(H):
        t = yy / H; d.line([(0, yy), (W, yy)], fill=tuple(int(255 * (1 - t) + c * t) for c in (222, 234, 248)))
    lp = os.path.join(base, ec.get('logo', 'alpro_logo_1200_white.png'))
    if os.path.exists(lp):
        lg = Image.open(lp).convert('RGBA'); lg.thumbnail((600, 600)); im.paste(lg, ((W - lg.width) // 2, 300), lg)
    d.rounded_rectangle([150, 990, 930, 1140], radius=75, fill=BLUE)
    d.text((W / 2, 1065), ec['cta'], font=font(58), fill=(255, 255, 255), anchor='mm')
    d.text((W / 2, 1225), ec['outlet_line'], font=font(48), fill=BLUE, anchor='mm')
    d.text((W / 2, 1330), ec['teaser'], font=font(46), fill=GOLD, anchor='mm')
    d.text((W / 2, 1420), ec.get('follow', 'Follow so you don\'t miss Part 2'), font=font(36), fill=(120, 130, 150), anchor='mm')
    im.save(path)

def speech_spans(src, a, b):
    """Speech islands in [a,b] of the clip's own audio (ffmpeg silencedetect, no model needed)."""
    e = subprocess.run(['ffmpeg', '-hide_banner', '-ss', f'{a:.3f}', '-t', f'{b - a:.3f}', '-i', src, '-af', 'silencedetect=n=-32dB:d=0.28', '-f', 'null', '-'], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r'silence_start: (-?[\d.]+)', e)]; en = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', e)]
    sil = list(zip(st, en + [b - a] * (len(st) - len(en)))); spans, t = [], 0.0
    for s0, s1 in sil:
        if s0 - t > 0.25: spans.append((a + t, a + s0))
        t = max(t, s1)
    if (b - a) - t > 0.25: spans.append((a + t, b))
    return spans

def chunks(shot, src, n=3):
    """Caption chunks (≤n words) on the shot's own timeline. One speech island per line when the counts match,
    else words spread over the whole spoken span. speech_in/speech_out in cut.json override detection."""
    lines = shot.get('lines', [])
    if not lines: return []
    a, b = shot.get('in', 0), shot['out']
    spans = [] if ('speech_in' in shot or src is None) else speech_spans(src, a, b)
    if len(spans) == len(lines): wins = spans
    else:
        s0 = shot.get('speech_in', spans[0][0] if spans else a + 0.3); s1 = shot.get('speech_out', spans[-1][1] if spans else b - 0.3)
        tot = sum(len(l['text'].split()) for l in lines); wins, t = [], s0
        for l in lines:
            dt = (s1 - s0) * len(l['text'].split()) / tot; wins.append((t, t + dt)); t += dt
    out = []
    for l, (w0, w1) in zip(lines, wins):
        ws = l['text'].split(); gs = [' '.join(ws[i:i + n]) for i in range(0, len(ws), n)]; t = w0
        for g in gs:
            dt = (w1 - w0) * len(g.split()) / len(ws); out.append((t, t + dt - 0.04, g)); t += dt
    return out

MASA = [r'diabet\w*', r'kencing manis', r'hypertensi\w*', r'darah tinggi', r'high blood pressure', r'heart disease', r'penyakit jantung',
        r'kidney disease', r'penyakit buah pinggang', r'epileps\w*', r'penyakit sawan', r'asthma\w*', r'penyakit lelah', r'cancer\w*', r'kanser',
        r'infertil\w*', r'mandul', r'impoten\w*', '糖尿病', '高血压', '心脏病', '肾病', '肾脏病', '癫痫', '哮喘', '癌', '不孕', '阳痿']
CLAIMS = [r'\bcures?\b', r'\bcured\b', r'\btreats?\b(?!ment plan)', r'\bprevents?\b', r'\bheals (?:your|you|the)\b', r'\bguarantee\w*', r'\bmiracle\b', r'\b100% safe\b']
CLUSTERS = {'blood sugar signs': [r'thirst', r'frequent (?:toilet|urinat|pee)', r'slow[- ]heal', r'blurr?y (?:vision|eyes?)', r'numb (?:feet|toes)'],
            'blood pressure / heart signs': [r'pounding head', r'nose ?bleed', r'chest (?:pain|tight)', r'palpitation'],
            'breathing signs': [r'wheez', r'short(?:ness)? of breath', r'chest tight', r'night(?:time)? cough']}

def gate(C):
    """MASA / claims gate over everything a viewer sees or reads: dialogue, hooks, end card, TikTok copy, Kling prompts."""
    tk = C.get('tiktok', {})
    txt = ' '.join([l['text'] for s in C['shots'] for l in s.get('lines', [])] + [s.get('prompt', '') for s in C['shots']] +
                   list(C.get('hooks', {}).values()) + [str(v) for v in C['endcard'].values()] +
                   [tk.get('caption', ''), tk.get('pinned_comment', ''), tk.get('comment_question', ''), ' '.join(tk.get('hashtags', []))]).lower()
    bad = []
    for p in MASA:
        m = re.search(p, txt)
        if m: bad.append(f'MASA: "{m.group(0)}" named')
    for p in CLAIMS:
        m = re.search(p, txt)
        if m: bad.append(f'Claim word "{m.group(0)}"')
    for name, pats in CLUSTERS.items():
        hit = [p for p in pats if re.search(p, txt)]
        if len(hit) >= 2: bad.append(f'MASA: {len(hit)} classic {name} together implies a scheduled condition')
    m = re.search(r'\b\d+(?:\.\d+)?\s*(?:mmol|mg/dl|mmhg)\b|\b\d{2,3}\s*/\s*\d{2,3}\b', txt)
    if m: bad.append(f'MASA: numeric reading "{m.group(0)}"')
    if re.search(r'\bfree\b(?! sugars?)(?!-)', txt) and not C.get('free_confirmed'): bad.append('"free" used but Yeoh has not confirmed the promo')
    if re.search(r'07[- ]?288[- ]?8560|07[- ]?352[- ]?0338', txt): bad.append('Landline in copy (WhatsApp lines only)')
    if re.search(r'medicpak|oncohelp|stand against prediabet|respiratory teleconsult', txt): bad.append('Banned service name')
    if tk and len(tk.get('caption', '')) > 2200: bad.append('TikTok caption over 2,200 chars')
    if tk and not 3 <= len(tk.get('hashtags', [])) <= 6: bad.append('TikTok: use 3–6 hashtags')
    return bad

def check(C, base):
    bad = gate(C)
    for v, hk in C.get('hooks', {}).items():
        if len(hk.split()) > 8: bad.append(f'Hook {v} over 8 words: "{hk}"')
        if re.match(r'\s*previously', hk, re.I): bad.append(f'Hook {v} opens with "Previously"')
    if len(set(C.get('hooks', {}).values())) < len(C.get('hooks', {})): bad.append('Hooks A/B/C must differ')
    for i, s in enumerate(C['shots']):
        if s.get('image'):
            p = os.path.join(base, s['image'])
            if not os.path.exists(p): bad.append(f'Shot {i}: image missing {s["image"]}'); continue
            w, h = Image.open(p).size; dur = 999
            if s.get('ambience') and not os.path.exists(os.path.join(base, s['ambience'])): bad.append(f'Shot {i}: ambience missing {s["ambience"]}')
        else:
            p = os.path.join(base, s['clip'])
            if not os.path.exists(p): bad.append(f'Shot {i}: clip missing {s["clip"]}'); continue
            dur, (w, h), _ = probe(p)
        if w > h: bad.append(f'Shot {i}: {s.get("clip") or s.get("image")} is landscape {w}x{h} (regenerate 9:16)')
        if s['out'] > dur + 0.05: bad.append(f'Shot {i}: out {s["out"]} > clip length {dur:.2f}')
        if s.get('image') and s['out'] - s.get('in', 0) > 5: bad.append(f'Shot {i}: animated still over 5s (keep stills 2–5s)')
        for l in s.get('lines', []):
            t = l['text']
            if len(t.split()) > 12: bad.append(f'Line over 12 words: "{t}"')
            if re.search(BANNED, t, re.I): bad.append(f'Lecture line (banned opener): "{t}"')
            if len(re.findall(r'\b(lah|leh|lor|meh|kan)\b', t, re.I)) > 1: bad.append(f'More than one Manglish particle: "{t}"')
    for v, segs in C['variants'].items():
        tot = sum(seg_len(C, sg) for sg in segs) + C['endcard'].get('seconds', 2.0)
        if not 30 <= tot <= 60: bad.append(f'Variant {v}: {tot:.1f}s (allowed 30–60s; sweet spot 40–50s)')
    first = C['variants']['A'][0]; s0 = C['shots'][first if isinstance(first, int) else first[0]]
    if not s0.get('lines') and not C.get('hooks', {}).get('A'): bad.append('Shot 1 of A has no line and no hook text: viewers need words in the first second')
    return bad

def seg(C, sg):
    if isinstance(sg, int): s = C['shots'][sg]; return sg, s['in'], s['out'], None
    return sg[0], sg[1], sg[2], (sg[3] if len(sg) > 3 else None)

def seg_len(C, sg): _, a, b, _ = seg(C, sg); return b - a

MOVES = {'in': "z='1+0.10*on/{n}'", 'out': "z='1.10-0.10*on/{n}'"}

def still_inputs(s, base, a, b):
    """Animated still (budget tiers L/L+/M): slow push-in/out or pan over a Kling start frame, with quiet room tone
    or a looped ambience bed taken from a clip ("ambience": "g1.mp4")."""
    d = b - a; n = max(1, int(d * FPS)); mv = s.get('move', 'in')
    vin = ['-loop', '1', '-framerate', str(FPS), '-t', f'{d:.3f}', '-i', os.path.join(base, s['image'])]
    pre = f'scale={W*3}:{H*3}:force_original_aspect_ratio=increase:flags=lanczos,crop={W*3}:{H*3},setsar=1'
    if mv in MOVES: vf = pre + ',' + f"zoompan={MOVES[mv].format(n=n)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}"
    else:
        sx = '0+(iw-ow)*t/' + f'{d:.3f}' if mv == 'right' else '(iw-ow)-(iw-ow)*t/' + f'{d:.3f}'
        vf = f'scale={int(W * 1.12)}:{int(H * 1.12)}:force_original_aspect_ratio=increase,crop={W}:{H}:x=\'{sx}\':y=(ih-oh)/2,setsar=1'
    amb = s.get('ambience')
    ain = (['-stream_loop', '-1', '-i', os.path.join(base, amb)] if amb else ['-f', 'lavfi', '-i', 'anoisesrc=c=brown:r=48000:a=0.004'])
    return vin, vf, ain, ('volume=0.25' if amb else 'anull')

def render_seg(C, base, tmp, sg, k, hook, badge, out):
    idx, a, b, label = seg(C, sg); s = C['shots'][idx]
    if s.get('image'): return render_still(C, base, tmp, s, a, b, label, k, hook, badge, out)
    src = os.path.join(base, s['clip'])
    dur, _, has_a = probe(src); b = min(b, dur)
    ovs = [png_badge(os.path.join(tmp, f'b{k}.png'), badge) or (os.path.join(tmp, f'b{k}.png'), 0, b - a)]
    if hook: png_text(os.path.join(tmp, f'h{k}.png'), hook, 78, 330, box=(0, 0, 0, 170)); ovs.append((os.path.join(tmp, f'h{k}.png'), 0, min(2.6, b - a)))
    if label: png_text(os.path.join(tmp, f'l{k}.png'), label, 64, 860, fill=(255, 214, 60)); ovs.append((os.path.join(tmp, f'l{k}.png'), 0, min(1.6, b - a)))
    for j, (t0, t1, g) in enumerate(chunks(s, src)):
        t0, t1 = max(t0, a) - a, min(t1, b) - a
        if t1 - t0 < 0.15: continue
        p = os.path.join(tmp, f'c{k}_{j}.png'); png_text(p, g.upper() if C.get('caption_upper', True) else g, 76, 1380); ovs.append((p, t0, t1))
    cmd = ['ffmpeg', '-y', '-ss', f'{a:.3f}', '-t', f'{b - a:.3f}', '-i', src]
    for p, _, _ in ovs: cmd += ['-i', p]
    if not has_a: cmd += ['-f', 'lavfi', '-t', f'{b - a:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
    fc = f'[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[v0]'
    for i, (_, t0, t1) in enumerate(ovs):
        fc += f';[v{i}][{i + 1}:v]overlay=0:0:enable=\'between(t,{t0:.2f},{t1:.2f})\'[v{i + 1}]'
    ai = '0:a' if has_a else f'{len(ovs) + 1}:a'
    fc += f';[{ai}]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{b - a:.3f}[a]'
    cmd += ['-filter_complex', fc, '-map', f'[v{len(ovs)}]', '-map', '[a]', '-t', f'{b - a:.3f}',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', out]
    sh(cmd)

def overlays(C, tmp, s, src, a, b, label, k, hook, badge):
    ovs = [png_badge(os.path.join(tmp, f'b{k}.png'), badge) or (os.path.join(tmp, f'b{k}.png'), 0, b - a)]
    if hook: png_text(os.path.join(tmp, f'h{k}.png'), hook, 78, 330, box=(0, 0, 0, 170)); ovs.append((os.path.join(tmp, f'h{k}.png'), 0, min(2.6, b - a)))
    if label: png_text(os.path.join(tmp, f'l{k}.png'), label, 64, 860, fill=(255, 214, 60)); ovs.append((os.path.join(tmp, f'l{k}.png'), 0, min(1.6, b - a)))
    for j, (t0, t1, g) in enumerate(chunks(s, src)):
        t0, t1 = max(t0, a) - a, min(t1, b) - a
        if t1 - t0 < 0.15: continue
        p = os.path.join(tmp, f'c{k}_{j}.png'); png_text(p, g.upper() if C.get('caption_upper', True) else g, 76, 1380); ovs.append((p, t0, t1))
    return ovs

def render_still(C, base, tmp, s, a, b, label, k, hook, badge, out):
    vin, vf, ain, af = still_inputs(s, base, a, b); ovs = overlays(C, tmp, s, None, a, b, label, k, hook, badge)
    cmd = ['ffmpeg', '-y'] + vin
    for p, _, _ in ovs: cmd += ['-i', p]
    cmd += ain
    fc = f'[0:v]{vf}[v0]'
    for i, (_, t0, t1) in enumerate(ovs):
        fc += f';[v{i}][{i + 1}:v]overlay=0:0:enable=\'between(t,{t0:.2f},{t1:.2f})\'[v{i + 1}]'
    fc += f';[{len(ovs) + 1}:a]aresample=48000,aformat=channel_layouts=stereo,{af},atrim=0:{b - a:.3f}[a]'
    sh(cmd + ['-filter_complex', fc, '-map', f'[v{len(ovs)}]', '-map', '[a]', '-t', f'{b - a:.3f}',
              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', out])

def render_end(C, base, tmp, out):
    ec = C['endcard']; p = os.path.join(tmp, 'end.png'); png_endcard(p, ec, base); sec = ec.get('seconds', 2.0)
    sting = 'aevalsrc=0.18*sin(2*PI*523*t)*exp(-3*t)+0.14*sin(2*PI*659*t)*exp(-3*t)+0.12*sin(2*PI*784*t)*exp(-3*t):s=48000:d=' + str(sec)
    sh(['ffmpeg', '-y', '-loop', '1', '-t', str(sec), '-i', p, '-f', 'lavfi', '-i', sting, '-filter_complex',
        f'[0:v]fps={FPS},scale={W}:{H},setsar=1,fade=in:0:8[v];[1:a]aformat=channel_layouts=stereo[a]', '-map', '[v]', '-map', '[a]',
        '-t', str(sec), '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', out])

def lufs(p):
    e = subprocess.run(['ffmpeg', '-hide_banner', '-i', p, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', e); return float(m[-1]) if m else None

def assemble(parts, out, tmp):
    lst = os.path.join(tmp, os.path.basename(out) + '.txt')
    open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
    raw = os.path.join(tmp, 'raw_' + os.path.basename(out))
    sh(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', raw])
    sh(['ffmpeg', '-y', '-i', raw, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', out])
    L = lufs(out)
    for _ in range(3):  # trim to -14 ±0.5 LUFS (checks.py accepts -16..-12)
        if L is None or abs(L + 14) <= 0.5: break
        fix = out + '.fix.mp4'
        sh(['ffmpeg', '-y', '-i', out, '-af', f'volume={-14 - L:.2f}dB', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', fix])
        os.replace(fix, out); L = lufs(out)
    return L

def main():
    cj = sys.argv[1]; C = json.load(open(cj)); base = os.path.dirname(os.path.abspath(cj))
    bad = check(C, base)
    if bad: print('FAIL\n- ' + '\n- '.join(bad)); sys.exit(1)
    if '--check' in sys.argv: print('CHECK PASS'); return
    tmp = tempfile.mkdtemp(prefix='cin_'); ep = C['episode']; badge = C['badge']
    end = os.path.join(tmp, 'end.mp4'); render_end(C, base, tmp, end)
    report = []
    for v, segs in C['variants'].items():
        parts = []
        for k, sg in enumerate(segs):
            p = os.path.join(tmp, f'{v}_{k}.mp4')
            render_seg(C, base, tmp, sg, f'{v}{k}', C['hooks'][v] if k == 0 else None, badge, p); parts.append(p)
        out = os.path.join(base, f'{ep}_{v}_Video.mp4'); L = assemble(parts + [end], out, tmp)
        d, _, _ = probe(out); report.append(f'{v}: {d:.1f}s {L} LUFS')
        sh(['ffmpeg', '-y', '-ss', '0.8', '-i', out, '-frames:v', '1', '-q:v', '2', os.path.join(base, f'{ep}_{v}_Video_cover.jpg')])
        if v == 'A' and C.get('gbp'):  # optional Google Business cut (off: /cinema is TikTok-only): A's order, drop short:false shots, <=29.5s with end card
            budget = 29.5 - C['endcard'].get('seconds', 2.0); gparts = []; k2 = 0
            for sg in segs:
                idx, a, b, label = seg(C, sg)
                if C['shots'][idx].get('short') is False or budget <= 1.0: continue
                b = min(b, a + budget); budget -= b - a
                p = os.path.join(tmp, f'g_{k2}.mp4'); render_seg(C, base, tmp, [idx, a, b] + ([label] if label else []), f'g{k2}', C['hooks']['A'] if k2 == 0 else None, badge, p)
                gparts.append(p); k2 += 1
            g = os.path.join(base, f'{ep}_A_Video_GBP30.mp4'); L = assemble(gparts + [end], g, tmp)
            d, _, _ = probe(g); report.append(f'GBP30: {d:.1f}s {L} LUFS')
    shutil.rmtree(tmp, ignore_errors=True)
    print('RENDER OK  ' + ' · '.join(report))

if __name__ == '__main__': main()
