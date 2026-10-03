#!/usr/bin/env python3
"""marketer.py v3 — storyboard JSON -> narrated 9:16 story video (RM0, offline).
usage: python3 marketer.py story.json <Episode>_Video.mp4
also writes <Episode>_Video_cover.jpg, <Episode>_Video_GBP30.mp4 (<=30s for Google Business)
scenes with "clip" (PixVerse/Kling mp4) play the motion clip, time-stretched to the scene
needs: kokoro.onnx + voices.bin beside this file, ffmpeg, pip kokoro-onnx soundfile pillow numpy"""
import json, sys, os, subprocess, numpy as np, soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SS = 1080, 1920, 30, 1.15
CW, CH = int(W*SS), int(H*SS)
FONT = next((f for f in ['/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf',
             '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if os.path.exists(f)), None)
def font(sz, t=''): return ImageFont.truetype(FONT, int(sz*SS))
def S(v): return int(v*SS)
def C(c): return tuple(c) if isinstance(c, list) else c

INK=(40,34,38); SKIN=(214,160,120); SKIN2=(190,138,100)
SKINS={'tan':((214,160,120),(190,138,100)),'light':((240,200,170),(220,175,145)),'dark':((150,100,70),(125,82,58))}
HAIR={'grey':(200,200,205),'black':(30,28,32),'brown':(90,60,40),'white':(240,240,240)}

# ---------- primitives ----------
def E(d,b,**k): d.ellipse([S(v) for v in b],**k)
def R(d,b,r=0,**k): d.rounded_rectangle([S(v) for v in b],radius=S(r),**k)
def L(d,p,w,**k): d.line([(S(x),S(y)) for x,y in p],width=max(1,S(w)),**k)
def A(d,b,s,e,w,**k): d.arc([S(v) for v in b],s,e,width=max(1,S(w)),**k)
def P(d,p,**k): d.polygon([(S(x),S(y)) for x,y in p],**k)

def face(d,x,y,f,mood,squint,glasses,brow):
    ey=y+f(10)
    for sx in (-1,1):
        cx=x+sx*f(46)
        if squint: L(d,[(cx-f(18),ey),(cx+f(18),ey)],f(7),fill=INK)
        else: E(d,(cx-f(11),ey-f(13),cx+f(11),ey+f(13)),fill=INK)
        if glasses: E(d,(cx-f(36),ey-f(30),cx+f(36),ey+f(30)),outline=INK,width=S(f(6)))
        if brow: L(d,[(cx-f(26),ey-f(44)),(cx+f(24),ey-f(48))],f(8),fill=brow)
    if glasses: L(d,[(x-f(12),ey),(x+f(12),ey)],f(6),fill=INK)
    my=y+f(70)
    if mood=='smile': A(d,(x-f(34),my-f(15),x+f(34),my+f(40)),20,160,f(7),fill=INK)
    elif mood=='happy': d.chord([S(x-f(34)),S(my-f(10)),S(x+f(34)),S(my+f(45))],0,180,fill=INK)
    elif mood=='worry': A(d,(x-f(26),my+f(22),x+f(26),my+f(60)),200,340,f(7),fill=INK)
    elif mood=='shock': E(d,(x-f(16),my+f(10),x+f(16),my+f(50)),fill=INK)
    else: L(d,[(x-f(24),my+f(30)),(x+f(24),my+f(30))],f(7),fill=INK)

def character(d,e):
    """Reusable cast. Same args every scene = same character."""
    x,y=e['x'],e['y']; sc=e.get('scale',1.0); f=lambda v:v*sc
    kind=e.get('kind','uncle'); mood=e.get('mood','smile'); sq=e.get('squint',False)
    sk,sk2=SKINS[e.get('skin','tan')]; shirt=C(e.get('shirt',[46,98,160])); hair=HAIR.get(e.get('hair'),None)
    g=e.get('glasses', kind in ('uncle','auntie'))
    if kind=='pharmacist':
        hij=C(e.get('hijab',[20,140,140]))
        R(d,(x-f(140),y+f(150),x+f(140),y+f(560)),r=f(70),fill=(248,248,250),outline=(210,210,215),width=S(f(4)))
        P(d,[(x-f(40),y+f(150)),(x,y+f(260)),(x+f(40),y+f(150))],fill=hij)
        R(d,(x+f(55),y+f(280),x+f(110),y+f(310)),r=f(6),fill=hij)
        if e.get('hijab',True) is not False: E(d,(x-f(130),y-f(135),x+f(130),y+f(200)),fill=hij)
        E(d,(x-f(85),y-f(80),x+f(85),y+f(120)),fill=sk)
        face(d,x,y-f(10),lambda v:f(v*0.78),mood,sq,g,None); return
    body_w={'uncle':150,'auntie':140,'woman':130,'man':140,'child':95}[kind]
    head={'uncle':120,'auntie':112,'woman':100,'man':108,'child':95}[kind]
    hair=hair or {'uncle':HAIR['grey'],'auntie':HAIR['grey'],'woman':HAIR['black'],'man':HAIR['black'],'child':HAIR['black']}[kind]
    if kind in ('woman','auntie'): R(d,(x-f(head+15),y-f(60),x+f(head+15),y+f(kind=='woman' and 330 or 120)),r=f(60),fill=hair)
    R(d,(x-f(body_w),y+f(head+30),x+f(body_w),y+f(head+30+390*(0.7 if kind=='child' else 1))),r=f(70),fill=shirt)
    if e.get('pattern',kind=='uncle'):
        lt=tuple(min(255,c+30) for c in shirt)
        for i in range(6):
            for j in range(4): E(d,(x-f(body_w-30)+i*f(body_w/3.1),y+f(head+80)+j*f(85),x-f(body_w-46)+i*f(body_w/3.1),y+f(head+96)+j*f(85)),fill=lt)
    R(d,(x-f(40),y+f(head-10),x+f(40),y+f(head+50)),r=f(10),fill=sk2)
    E(d,(x-f(head),y-f(head+10),x+f(head),y+f(head+30)),fill=sk)
    if kind=='uncle': A(d,(x-f(125),y-f(140),x+f(125),y+f(60)),190,350,f(34),fill=hair)
    else: A(d,(x-f(head+8),y-f(head+25),x+f(head+8),y+f(70)),180,360,f(46),fill=hair)
    if kind in ('woman','child','auntie'):
        E(d,(x-f(75),y+f(40),x-f(45),y+f(62)),fill=(240,150,150)); E(d,(x+f(45),y+f(40),x+f(75),y+f(62)),fill=(240,150,150))
    face(d,x,y,lambda v:f(v*(head/120)),mood,sq,g,hair if kind=='uncle' else None)
    if kind=='uncle': R(d,(x-f(42),y+f(62),x+f(42),y+f(78)),r=f(8),fill=hair)

def text(im,d,e):
    fn=font(e.get('size',80),e['text']); fill=C(e.get('color',[40,34,38]))
    kw=dict(font=fn,fill=fill,anchor=e.get('anchor','mm'))
    if e.get('stroke'): kw.update(stroke_width=S(e['stroke']),stroke_fill=C(e.get('stroke_color',[20,20,20])))
    d.text((S(e['x']),S(e['y'])),e['text'],**kw)

def draw_el(im,d,e):
    t=e['type']; fill=C(e.get('fill',[255,255,255])) if 'fill' in e else None
    out=C(e['outline']) if 'outline' in e else None; w=S(e.get('width',4))
    if t=='rect': R(d,e['box'],r=e.get('r',0),fill=fill,outline=out,width=w)
    elif t=='circle': E(d,e['box'],fill=fill,outline=out,width=w)
    elif t=='poly': P(d,e['pts'],fill=fill)
    elif t=='line': L(d,e['pts'],e.get('width',6),fill=fill)
    elif t=='text': text(im,d,e)
    elif t=='char': character(d,e)
    elif t=='bottle':
        x,y=e['x'],e['y']; c=C(e.get('fill',[140,200,240]))
        R(d,(x,y,x+80,y+200),r=24,fill=c,outline=tuple(max(0,v-50) for v in c),width=S(5)); R(d,(x+22,y-30,x+58,y+5),r=8,fill=tuple(max(0,v-80) for v in c))
    elif t=='shelf':
        cols=[(240,120,110),(110,170,230),(250,200,90),(130,200,140)]
        for r_ in range(e.get('rows',3)):
            y=e.get('y',130)+r_*170; R(d,(40,y+90,1040,y+120),fill=(180,200,200))
            for i in range(9): R(d,(70+i*108,y,150+i*108,y+90),r=10,fill=cols[(i+r_)%4])
    elif t=='checklist':
        y0=e.get('y',420)
        for i,it in enumerate(e['items']):
            c=C(it.get('color',[20,140,140])); y=y0+i*e.get('gap',270)
            R(d,(90,y,990,y+220),r=40,fill=(255,255,255),outline=c,width=S(8)); E(d,(130,y+40,270,y+180),fill=c)
            d.text((S(200),S(y+110)),str(i+1),font=font(80),fill='white',anchor='mm')
            d.text((S(310),S(y+110)),it['text'],font=font(it.get('size',72),it['text']),fill=INK,anchor='lm')
    elif t=='blurcard':
        x,y,w_,h_=e['box']; card=Image.new('RGB',(S(w_),S(h_)),(250,248,240)); cd=ImageDraw.Draw(card)
        cd.text((S(40),S(30)),e.get('title','NEWS'),font=font(80),fill=INK)
        for i in range(int((h_-170)/45)): cd.rounded_rectangle([S(40),S(170+i*45),S(w_-40-(i%3)*80),S(190+i*45)],radius=S(8),fill=(120,120,120))
        im.paste(card.filter(ImageFilter.GaussianBlur(S(e.get('blur',9)))),(S(x),S(y)))
    elif t=='cross':
        x,y,s=e['x'],e['y'],e.get('size',300); E(d,(x-s/2,y-s/2,x+s/2,y+s/2),fill=C(e.get('bg',[255,255,255])))
        c=C(e.get('fill',[220,50,60])); R(d,(x-s/12,y-s*.37,x+s/12,y+s*.37),r=8,fill=c); R(d,(x-s*.37,y-s/12,x+s*.37,y+s/12),r=8,fill=c)
    elif t=='logo':
        # real Alpro logo (brand/alpro_logo_1200_white.png): x,y = centre, size = width px, radius = tile corner
        src=e.get('src','alpro_logo_1200_white.png')
        if not os.path.exists(src): src=os.path.join(HERE,os.path.basename(src))
        lg=Image.open(src).convert('RGBA'); sz=S(e.get('size',560)); lg=lg.resize((sz,int(sz*lg.height/lg.width)),Image.LANCZOS)
        if e.get('radius',36):
            mk=Image.new('L',lg.size,0); ImageDraw.Draw(mk).rounded_rectangle([0,0,lg.width-1,lg.height-1],radius=S(e.get('radius',36)),fill=255)
            lg.putalpha(Image.composite(lg.getchannel('A'),Image.new('L',lg.size,0),mk))
        im.paste(lg,(S(e['x'])-lg.width//2,S(e['y'])-lg.height//2),lg)

def render_scene(sc):
    top,bot=C(sc.get('bg',[[250,240,225],[235,225,210]])[0]),C(sc.get('bg',[[250,240,225],[235,225,210]])[1])
    a=np.linspace(0,1,CH)[:,None,None]
    im=Image.fromarray(np.repeat((np.array(top)*(1-a)+np.array(bot)*a).astype(np.uint8),CW,axis=1))
    if sc.get('image'):
        src=Image.open(sc['image']).convert('RGB'); r=max(CW/src.width,CH/src.height)
        src=src.resize((int(src.width*r+1),int(src.height*r+1)),Image.LANCZOS).filter(ImageFilter.UnsharpMask(2,60,2))
        ox=int((src.width-CW)*sc.get('focus_x',0.5)); oy=int((src.height-CH)*sc.get('focus_y',0.5))
        im=src.crop((ox,oy,ox+CW,oy+CH))
        if sc.get('shade',True):
            g=np.linspace(0,1,CH)[:,None]; a=(np.clip((g-0.62)/0.38,0,1)**1.5*150).astype(np.uint8)
            im=Image.composite(Image.new('RGB',(CW,CH),(0,0,0)),im,Image.fromarray(np.repeat(a,CW,axis=1),'L'))
    d=ImageDraw.Draw(im)
    for e in sc.get('elements',[]): draw_el(im,d,e)
    return im

def capfont(t, sz): return ImageFont.truetype(FONT, sz)

# ---------- audio ----------
def tts(sb, lines):
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(HERE, 'kokoro.onnx'), os.path.join(HERE, 'voices.bin'))
    voice = sb.get('voice', 'af_heart')
    out = []
    for ln, v in lines:
        a, sr = k.create(ln, voice=v or voice, speed=sb.get('speed', 1.0), lang='en-us')
        out.append(a.astype(np.float32))
    return out, sr

def synth_music(total, sr, mood):
    """Generated lo-fi bed: soft chords + kick + hat, 84 BPM. mood: warm|hopeful|tense."""
    tt = np.arange(int(total * sr)) / sr; m = np.zeros_like(tt, dtype=np.float32)
    prog = {'warm': [[261.6,329.6,392.0],[220.0,261.6,329.6],[174.6,220.0,261.6],[196.0,246.9,293.7]],
            'hopeful': [[261.6,329.6,392.0],[196.0,246.9,293.7],[220.0,261.6,329.6],[174.6,220.0,261.6]],
            'tense': [[220.0,261.6,329.6],[207.7,261.6,311.1],[196.0,246.9,293.7],[174.6,220.0,261.6]]}[mood]
    bar = 60 / 84 * 4
    for n in range(int(total / bar) + 1):
        ch = prog[n % 4]; s0 = int(n * bar * sr); s1 = min(len(m), int((n + 1) * bar * sr + sr))
        if s0 >= len(m): break
        tl = tt[s0:s1] - n * bar; env = np.clip(tl / 0.6, 0, 1) * np.clip((bar + 1 - tl) / 1.0, 0, 1)
        for fq in ch: m[s0:s1] += 0.022 * env * (np.sin(2*np.pi*fq*tt[s0:s1]) + 0.25*np.sin(4*np.pi*fq*tt[s0:s1]))
    beat = 60 / 84; rng = np.random.default_rng(7)
    for b in range(int(total / beat) + 1):
        i = int(b * beat * sr)
        if i >= len(m): break
        if b % 2 == 0:  # kick
            L_ = min(int(0.25 * sr), len(m) - i); t_ = np.arange(L_) / sr
            m[i:i+L_] += 0.10 * np.sin(2*np.pi*(55 + 70*np.exp(-t_*25))*t_) * np.exp(-t_*12)
        j = int((b + 0.5) * beat * sr)  # off-beat hat
        if j < len(m):
            L_ = min(int(0.05 * sr), len(m) - j)
            m[j:j+L_] += 0.012 * rng.standard_normal(L_) * np.exp(-np.arange(L_) / sr * 90)
    m *= np.clip(tt / 1.5, 0, 1) * np.clip((total - tt) / 1.5, 0, 1)
    return m

def whoosh(sr, dur=0.45):
    n = int(dur * sr); t_ = np.arange(n) / sr
    x = np.random.default_rng(3).standard_normal(n).astype(np.float32)
    x = np.convolve(x, np.ones(24) / 24, 'same')  # soften
    return 0.05 * x * np.sin(np.pi * t_ / dur) ** 2

def build_audio(sb, scenes, work, tag):
    lines = [(sc['line'], sc.get('voice')) for sc in scenes]
    clips, sr = tts(sb, lines)
    gap = sb.get('gap', 0.45); t = 0.4; timing = []
    for a in clips: timing.append((t, len(a) / sr)); t += len(a) / sr + gap
    total = t + 0.8
    v = np.zeros(int(total * sr), dtype=np.float32)
    for (st, _), a in zip(timing, clips): v[int(st*sr):int(st*sr)+len(a)] += a
    v = v / (np.max(np.abs(v)) + 1e-9) * 0.9
    mix = v.copy()
    if sb.get('music', True):
        m = synth_music(total, sr, sb.get('music_mood', 'warm'))
        # duck music under the voice
        env = np.convolve(np.abs(v), np.ones(int(0.25 * sr)) / int(0.25 * sr), 'same')
        duck = 1 - 0.65 * np.clip(env / 0.08, 0, 1)
        mix += m * duck * 1.6
    if sb.get('sfx', True):
        w = whoosh(sr)
        for st, _ in timing[1:]:
            i = max(0, int((st - gap / 2 - 0.22) * sr)); mix[i:i+len(w)] += w[:len(mix) - i]
    raw = os.path.join(work, f'audio_{tag}_raw.wav'); wav = os.path.join(work, f'audio_{tag}.wav')
    sf.write(raw, np.clip(mix, -1, 1), sr)
    # TikTok/Reels loudness: -14 LUFS integrated, -1 dBTP
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af', 'loudnorm=I=-14:TP=-1:LRA=11', '-ar', str(sr), wav], check=True)
    return timing, total, gap, wav

# ---------- captions (word-highlight, proportional timing) ----------
def chunks_for(line, n_words):
    w = line.split(); return [w[i:i+n_words] for i in range(0, len(w), n_words)]

def caption_img(tokens, active, sb):
    sep = ' '
    sz = sb.get('caption_size', 78); text = sep.join(tokens)
    f = capfont(text, sz)
    while f.getlength(text) > W - 120 and sz > 40: sz -= 4; f = capfont(text, sz)
    im = Image.new('RGBA', (W, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = (W - f.getlength(text)) / 2
    base = C(sb.get('caption_color', [255, 255, 255])); hi = C(sb.get('caption_highlight', [255, 214, 60]))
    for i, tok in enumerate(tokens):
        piece = tok + ('' if i == len(tokens) - 1 else sep)
        d.text((x, 150), tok, font=f, fill=hi if i == active else base, anchor='lm', stroke_width=8, stroke_fill=(20, 20, 20))
        x += f.getlength(piece)
    return im

# ---------- overlays ----------
def pill(d, cx, cy, text, f, fill, fg):
    w_ = f.getlength(text) + 44; h_ = f.size + 24
    d.rounded_rectangle([cx - w_/2, cy - h_/2, cx + w_/2, cy + h_/2], radius=h_/2, fill=fill)
    d.text((cx, cy), text, font=f, fill=fg, anchor='mm')

def hook_overlay(text, sb, u):
    """Big hook title for scene 1 (top third, under TikTok's top bar)."""
    im = Image.new('RGBA', (W, 520), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    sz = sb.get('hook_size', 88); f = capfont(text, sz)
    words = text.split(); lines = []; cur = ''
    sep = ' '
    for wd in words:
        trial = (cur + sep + wd) if cur else wd
        if f.getlength(trial) > W - 140 and cur: lines.append(cur); cur = wd
        else: cur = trial
    lines.append(cur)
    y = 60
    for ln in lines[:3]:
        tw = f.getlength(ln)
        d.rounded_rectangle([(W - tw)/2 - 26, y - 14, (W + tw)/2 + 26, y + sz + 18], radius=22, fill=(10, 10, 10, 200))
        d.text((W/2, y + sz/2 + 2), ln, font=f, fill=(255, 255, 255), anchor='mm'); y += sz + 44
    a = min(1, u / 0.12)  # pop-in
    if a < 1: im = im.resize((int(W*(0.9+0.1*a)), int(520*(0.9+0.1*a))))
    return im

def badge_overlay(text):
    im = Image.new('RGBA', (W, 120), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    pill(d, W/2, 60, text, capfont(text, 34), (27, 69, 131, 230), (255, 255, 255)); return im

# ---------- v3: motion clips (PixVerse/Kling image-to-video) ----------
def load_clip(path):
    """decode an mp4 to native-res RGB frames (kept small; upscaled per output frame)"""
    pr = json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height',
                                    '-of','json',path],capture_output=True,text=True).stdout)['streams'][0]
    w, h = pr['width'], pr['height']
    raw = subprocess.run(['ffmpeg','-loglevel','error','-i',path,'-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
    n = len(raw)//(w*h*3)
    return [np.frombuffer(raw, np.uint8, w*h*3, k*w*h*3).reshape(h, w, 3) for k in range(n)]

SHADE = None
def clip_frame(frames, u, sc):
    """pick frame by progress u (time-stretched to the scene span), cover-crop to 9:16, shade bottom for captions"""
    global SHADE
    a = frames[min(len(frames)-1, int(u*(len(frames)-1)+0.5))]
    im = Image.fromarray(a); r = max(W/im.width, H/im.height)
    im = im.resize((int(im.width*r+1), int(im.height*r+1)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 70, 2))
    ox = int((im.width-W)*sc.get('focus_x',0.5)); oy = int((im.height-H)*sc.get('focus_y',0.5)); im = im.crop((ox, oy, ox+W, oy+H))
    if sc.get('shade', True):
        if SHADE is None:
            g = np.linspace(0,1,H)[:,None]; SHADE = Image.fromarray(np.repeat((np.clip((g-0.62)/0.38,0,1)**1.5*150).astype(np.uint8), W, axis=1), 'L')
        im = Image.composite(Image.new('RGB', (W, H), (0,0,0)), im, SHADE)
    return im

# ---------- render ----------
MOVES = [(1,0),(-1,0),(0,1),(1,-1),(-1,0),(0,1),(1,0),(0,0),(0,0)]
def render(sb, scenes, out, tag, max_total=None):
    work = os.path.dirname(os.path.abspath(out)) or '.'
    timing, total, GAP, wav = build_audio(sb, scenes, work, tag)
    tries = 0
    while max_total and total > max_total and tries < 3:  # fit by speeding narration (cap 1.3x)
        sb = dict(sb); sb['speed'] = min(1.3, sb.get('speed', 1.0) * (total - 1.2) / (max_total - 1.4))
        timing, total, GAP, wav = build_audio(sb, scenes, work, tag); tries += 1
    imgs = [render_scene(s) for s in scenes]  # stills; scenes with a 'clip' use the motion clip instead (image = fallback)
    caps = []; nw = sb.get('caption_words', 4)
    for (st, du), s in zip(timing, scenes):
        chs = chunks_for(s['line'], nw); tot = sum(len(''.join(c)) for c in chs); c0 = st
        for ch in chs:
            dd = du * len(''.join(ch)) / tot; caps.append((c0, c0 + dd, ch)); c0 += dd
    CAPY = sb.get('caption_y', 1540); cache = {}
    spans = [(0 if i == 0 else st - GAP/2, total if i == len(timing) - 1 else timing[i+1][0] - GAP/2) for i, (st, _) in enumerate(timing)]
    hook = sb.get('hook_text'); badge = sb.get('badge'); bimg = badge_overlay(badge) if badge else None
    clips = {i: load_clip(s['clip']) for i, s in enumerate(scenes) if s.get('clip') and os.path.exists(s['clip'])}
    def fr(i, u):
        if i in clips: return clip_frame(clips[i], u, scenes[i])
        z = 1.0 + 0.13*u; cw = CW/z; ch = CH/z; dx, dy = MOVES[i % len(MOVES)]
        cx = (CW-cw)/2 + dx*(CW-cw)/2*(u-0.5); cy = (CH-ch)/2 + dy*(CH-ch)/2*(u-0.5)
        return imgs[i].resize((W, H), Image.BICUBIC, box=(cx, cy, cx+cw, cy+ch))
    p = subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
        '-i', wav,'-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',
        '-shortest','-movflags','+faststart', out], stdin=subprocess.PIPE)
    cover = None
    for n in range(int(total * FPS)):
        t = n / FPS; i = next(j for j, (a, b) in enumerate(spans) if t < b or j == len(spans) - 1); a, b = spans[i]
        f_ = fr(i, min(max((t - a) / (b - a), 0), 1))
        if i > 0 and t - a < 0.35: f_ = Image.blend(fr(i - 1, 1.0), f_, (t - a) / 0.35)
        if hook and i == 0:
            ho = hook_overlay(hook, sb, t); f_.paste(ho, ((W - ho.width)//2, 230), ho)
        elif bimg is not None and (scenes[i].get('image') or scenes[i].get('clip')) and scenes[i].get('badge', True):
            f_.paste(bimg, (0, 230), bimg)
        for c0, c1, ch in caps:
            if c0 <= t < c1:
                k = min(len(ch) - 1, int((t - c0) / (c1 - c0) * len(ch)))
                key = (tuple(ch), k)
                if key not in cache: cache[key] = caption_img(list(ch), k, sb)
                ci = cache[key]; pop = min(1, (t - c0) / 0.12)
                if pop < 1: ci = ci.resize((int(W*(0.85+0.15*pop)), int(300*(0.85+0.15*pop))))
                f_.paste(ci, ((W - ci.width)//2, CAPY - ci.height//2), ci); break
        if cover is None and t >= min(1.2, spans[0][1] * 0.5): cover = f_.copy()
        p.stdin.write(f_.tobytes())
    p.stdin.close(); p.wait()
    if cover is not None: cover.convert('RGB').save(os.path.splitext(out)[0] + '_cover.jpg', quality=90)
    return total

# ---------- main ----------
if __name__ == '__main__':
    sb = json.load(open(sys.argv[1])); out = sys.argv[2] if len(sys.argv) > 2 else sb.get('out', 'story.mp4')
    WORK = os.path.dirname(os.path.abspath(out)) or '.'
    total = render(sb, sb['scenes'], out, 'main')
    print(f'OK {out} {total:.1f}s {len(sb["scenes"])} scenes')
    base = os.path.splitext(out)[0]
    # Google Business video: <=30s cut (drops scenes flagged "short": false, then speeds up if still long)
    if sb.get('gbp_cut', True):
        sc30 = [s for s in sb['scenes'] if s.get('short', True)]
        t30 = render(dict(sb), sc30, base + '_GBP30.mp4', 'gbp', max_total=29.5)
        print(f'OK {base}_GBP30.mp4 {t30:.1f}s' + ('  (still over 30s: mark more scenes "short": false)' if t30 > 30 else ''))
