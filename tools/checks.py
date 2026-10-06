#!/usr/bin/env python3
"""checks.py: block delivery if any AlproPost / MASA / Google Business / platform rule is broken.
usage: python3 checks.py kit.json story.json [--log log.json] [--video <Episode>_Video.mp4]
  log.json = Marketer Log rows as a list of dicts (header -> value), fetched from the sheet before the run.
  -> exit 1 with a list of violations, else prints PASS"""
import json, sys, os, re, html, difflib, subprocess

args = sys.argv[1:]; opt = {}
for flag in ('--log', '--video'):
    if flag in args: i = args.index(flag); opt[flag] = args[i + 1]; del args[i:i + 2]
K = json.load(open(args[0])); D = os.path.dirname(os.path.abspath(args[0]))
S = json.load(open(args[1])) if len(args) > 1 else {'scenes': []}
LOG = json.load(open(opt['--log'])) if '--log' in opt else []
BLOG = open(os.path.join(D, K['blog']['html_file'])).read()
BLOG_TEXT = html.unescape(re.sub(r'<[^>]+>', ' ', re.sub(r'<(style|script)[^>]*>.*?</\1>', ' ', BLOG, flags=re.S)))
bad = []

# 1. MASA scheduled conditions: never named anywhere (video lines, captions, hashtags, blog, schema, alt text)
MASA = [r'diabet\w*', r'kencing manis', r'hypertensi\w*', r'darah tinggi', r'high blood pressure', r'heart disease', r'penyakit jantung',
        r'kidney disease', r'penyakit buah pinggang', r'epileps\w*', r'penyakit sawan', r'asthma\w*', r'penyakit lelah', r'cancer\w*', r'kanser',
        r'infertil\w*', r'mandul', r'impoten\w*',
        '糖尿病', '高血压', '心脏病', '肾病', '肾脏病', '癫痫', '哮喘', '癌', '不孕', '阳痿']
CLAIMS = [r'\bcures?\b', r'\bcured\b', r'\btreats?\b(?!ment plan)', r'\bprevents?\b', r'\bheals (?:your|you|the)\b', r'\bguarantee\w*', r'\bmiracle\b', r'\b100% safe\b']
corpus = {
  'video lines': ' '.join(sc.get('line', '') + ' ' + ' '.join(l.get('text', '') for l in sc.get('lines', [])) for sc in S.get('scenes', [])) + ' ' + S.get('hook_text', ''),
  'Mandarin lines': ' '.join(sc.get('line_zh', '') for sc in S.get('scenes', [])) + ' ' + S.get('hook_text_zh', '') +
                    ' ' + json.dumps([sc.get('elements_zh', []) for sc in S.get('scenes', [])], ensure_ascii=False),
  'video cards': json.dumps([sc.get('elements', []) for sc in S.get('scenes', [])], ensure_ascii=False),
  'blog': BLOG,
  'youtube': ' '.join([K['youtube']['title'], K['youtube']['description'], K['youtube']['tags']]),
  'tiktok': K['tiktok']['caption'] + ' ' + K['tiktok'].get('caption_zh', '') + ' ' + ' '.join(K['tiktok'].get('alt_hooks', [])),
  'facebook/instagram': K['meta']['caption'] + ' ' + K['meta']['first_comment'] + ' ' + K['meta'].get('caption_zh', ''),
  'google business': K['gbp']['text'], 'whatsapp': K['whatsapp'],
  'xiaohongshu': ' '.join(str(K.get('xiaohongshu', {}).get(k, '')) for k in ('title', 'body', 'topics')),
  'blog meta': ' '.join([K['blog']['title'], K['blog']['search_description'], K['blog']['labels'], K['blog']['lsi']]),
}
for where, txt in corpus.items():
    low = txt.lower()
    for p in MASA:
        m = re.search(p, low)
        if m: bad.append(f'MASA: "{m.group(0)}" named in {where}')
    if where != 'blog':  # blog may say "does not replace advice from your doctor"; claims checked on visible text below
        for p in CLAIMS:
            m = re.search(p, low)
            if m: bad.append(f'Claim word "{m.group(0)}" in {where}')
for p in CLAIMS:
    m = re.search(p, BLOG_TEXT.lower())
    if m: bad.append(f'Claim word "{m.group(0)}" in blog text (rephrase: "supports", "part of a routine")')
sc0 = (S.get('scenes') or [{}])[0]; hook_now = sc0.get('line') or ' '.join(l.get('text', '') for l in sc0.get('lines', []))
# 1b. implied conditions: 2+ classic signs of one scheduled condition, or numeric readings
CLUSTERS = {'blood sugar signs': [r'thirst', r'frequent (?:toilet|urinat|pee)', r'slow[- ]heal', r'blurr?y (?:vision|eyes?)', r'numb (?:feet|toes)'],
            'blood pressure / heart signs': [r'pounding head', r'nose ?bleed', r'chest (?:pain|tight)', r'palpitation'],
            'breathing signs': [r'wheez', r'short(?:ness)? of breath', r'chest tight', r'night(?:time)? cough']}
ALL = ' '.join(corpus.values()).lower()
for name, pats in CLUSTERS.items():
    hit = [p for p in pats if re.search(p, ALL)]
    if len(hit) >= 2: bad.append(f'MASA: {len(hit)} classic {name} together ({", ".join(hit)}) implies a scheduled condition; tell it through habits')
m = re.search(r'\b\d+(?:\.\d+)?\s*(?:mmol|mg/dl|mmhg)\b|\b\d{2,3}\s*/\s*\d{2,3}\b', ALL)
if m: bad.append(f'MASA: numeric reading "{m.group(0)}"')
if 'aisyah' in (ALL + ' ' + json.dumps(S).lower()): bad.append('Aisyah has left the series (Yeoh, 4 Oct 2026): never write, voice, draw or mention her')
if 'medicpak' in ALL: bad.append('MedicPak is discontinued: use Pilcube')
if 'pilcube' in K['gbp']['text'].lower(): bad.append('GBP: Pilcube is medicine delivery, keep it out of Google Business posts')
if '286 2923' in ALL or '2862923' in ALL: bad.append('Pilcube support number in copy')
if re.search(r'oncohelp|stand against prediabet|respiratory teleconsult', ALL): bad.append('Service name holds a scheduled condition (OncoHelp / ASAP / Respiratory Teleconsult): never feature by name')

# 1c. story craft (future episodes)
BANNED = r'^\s*(remember to|it\'?s important|make sure|don\'?t forget|you should|always|never)\b'
for sc in S.get('scenes', []):
    if sc.get('line') and re.search(BANNED, sc['line'], re.I): bad.append(f'Lecture narration (banned opener): "{sc["line"]}"')
    for ln in sc.get('lines', []):
        t = ln.get('text', '')
        if re.search(BANNED, t, re.I): bad.append(f'Lecture line (banned opener): "{t}"')
        if len(t.split()) > 12: bad.append(f'Line over 12 words: "{t}"')
        if len(re.findall(r'\b(lah|leh|lor|meh|kan)\b', t, re.I)) > 1: bad.append(f'More than one Manglish particle: "{t}"')
scs = S.get('scenes', [])
if scs:
    if re.match(r'\s*previously', hook_now, re.I) or re.match(r'\s*previously', S.get('hook_text', ''), re.I): bad.append('Hook: scene 1 must open mid-conflict, not with "Previously…"')
    nlines = sum(len(sc.get('lines', [])) for sc in scs)
    dlg = sum(1 for sc in scs if sc.get('lines')); img = [sc for sc in scs if sc.get('image') or sc.get('clip')]
    if nlines > 3: bad.append(f'Story: {nlines} dialogue lines (max 3; narrator-led ~90/10, keep dialogue for the key moments)')
    if dlg > 2: bad.append(f'Story: {dlg} dialogue scenes (max 2; Mei narrates the rest)')
    narr = sum(1 for sc in scs if sc.get('line') and not sc.get('lines') and (sc.get('image') or sc.get('clip')))
    if narr < len(img) - 2: bad.append(f'Story: only {narr} narrated image scenes (narrate all but at most 2)')
    cards = len(scs) - len(img)
    if cards > 1: bad.append(f'Story: {cards} static cards (max 1 end card; put the lesson as chips on the payoff scene)')
    clips = sum(1 for sc in scs if sc.get('clip') and os.path.exists(os.path.join(os.path.dirname(os.path.abspath(args[1])), sc['clip'])))
    for sc in scs:
        cp = os.path.join(os.path.dirname(os.path.abspath(args[1])), sc.get('clip') or '')
        if sc.get('clip') and os.path.isfile(cp):
            pr = subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','csv=p=0',cp],capture_output=True,text=True).stdout.strip().split(',')
            if len(pr) == 2 and pr[0].isdigit() and int(pr[0]) > int(pr[1]): bad.append(f'Motion: {sc["clip"]} is landscape {pr[0]}x{pr[1]} (regenerate in Portrait 9:16 or drop it)')
    if clips < 3 and not K.get('clips_exhausted'): bad.append(f'Motion: {clips} clips (target 3: PixVerse first, then max 1 Google video; set "clips_exhausted": true when PixVerse is out and the Google slot is spent)')

if re.search(r'\bfree\b(?! sugars?)(?!-)', ' '.join(corpus.values()).lower()) and not K.get('free_confirmed'):
    bad.append('"free" used but Yeoh has not confirmed the promo (set "free_confirmed": true only after he does)')

# 2. Google Business Profile post rules
g = K['gbp']['text']
if re.search(r'(\+?6?0\d{1,2}[\s-]?\d{3,4}[\s-]?\d{3,4})|(\b\d{3}[\s-]\d{3,4}[\s-]?\d{3,4}\b)', g): bad.append('GBP: phone number in post text (use the Call now button)')
if re.search(r'https?://|www\.|\.com\b|\.my\b|wa\.me|bit\.ly', g, re.I): bad.append('GBP: link or URL in post text (use the Learn more button)')
if re.search(r'[\w.+-]+@[\w-]+\.\w+', g): bad.append('GBP: email address in post text')
if re.search(r'#\w', g): bad.append('GBP: hashtags in post text (no value on Google, can trigger spam filter)')
if re.search(r'[!?]{2,}', g): bad.append('GBP: repeated punctuation (!! / ?!)')
caps = [w for w in re.findall(r'\b[A-Z]{4,}\b', g) if w not in ('KSL', 'ALPRO', 'MBJB')]
if caps: bad.append(f'GBP: ALL-CAPS words {caps}')
if len(g) > 1500: bad.append(f'GBP: {len(g)} chars (max 1,500)')
if len(g.split('\n')[0]) > 120: bad.append('GBP: first line over 120 chars (key message must sit in the first 80–100 chars)')
if re.search(r'\b(buy|order now|% off|discount|promo code|offer)\b', g, re.I): bad.append('GBP: sales/offer wording (no offers or calls to buy regulated pharmacy goods)')
if 'medic' in g.lower() and re.search(r'\b(buy|order|deliver)\b', g, re.I): bad.append('GBP: call to purchase medicine')
if K['gbp'].get('type', 'Update').lower().startswith('offer'): bad.append('GBP: post type must be Update, not Offer')
if 'mvp' not in K: bad.append('kit.json "mvp" missing (shopper MVP this episode answers, or null when none fits)')
elif K['mvp']:
    kw = [w.lower() for w in K['mvp'].get('keywords', []) if w.strip()]
    if not kw: bad.append('kit.json mvp.keywords empty (2–4 key words from the shopper prompt)')
    else:
        need = min(2, len(kw))
        if sum(w in g[:200].lower() for w in kw) < need: bad.append(f'GBP: shopper MVP "{K["mvp"].get("prompt","")}" not answered up front (need {need} of {kw} in the first 200 chars)')
        if sum(w in BLOG_TEXT.lower() for w in kw) < need: bad.append(f'Blog: shopper MVP keywords {kw} missing (MVP H2 + FAQ 4)')
try:
    from PIL import Image
    im = Image.open(os.path.join(D, K['images'][K['gbp']['image']]))
    if im.width != im.height: bad.append(f'GBP image must be 1:1 square (is {im.width}x{im.height})')
    if min(im.size) < 720: bad.append('GBP image smaller than 720x720')
    sz = os.path.getsize(os.path.join(D, K['images'][K['gbp']['image']]))
    if not (10_000 <= sz <= 5_000_000): bad.append(f'GBP image file size {sz} outside 10KB–5MB')
except Exception as e:
    bad.append(f'GBP image check failed: {e}')

# 3. Platform limits
b, y = K['blog'], K['youtube']
if len(b['search_description']) > 155: bad.append(f"Blog search description {len(b['search_description'])} chars (max 155)")
if 'johor bahru' not in b['search_description'].lower(): bad.append('Blog search description must contain "Johor Bahru"')
if not re.search(r'johor bahru|\bjb\b', b['title'], re.I) or 'alpro pharmacy' not in b['title'].lower(): bad.append('Blog title needs JB/Johor Bahru + Alpro Pharmacy')
pl = b.get('permalink', '').strip().lower()
if not pl or pl.startswith('blog-post') or len(pl.split('-')) < 4: bad.append('Blog permalink must be a descriptive slug (topic + johor-bahru + epN), not empty/"blog-post"')
bl = BLOG_TEXT.lower()
if not re.search(r'lot g-?001|jalan dedap 13', bl): bad.append('Blog visit block: outlet address missing (shopper feedback: agents need where)')
if not re.search(r'10\s?am|10:00|8:30\s?am|8\.30', bl): bad.append('Blog visit block: opening hours missing (shopper feedback: agents need when)')
if 'wa.me/' not in BLOG: bad.append('Blog visit block: WhatsApp link missing')
if re.search(r'07[- ]?288[- ]?8560|2888560|07[- ]?352[- ]?0338|3520338', BLOG + json.dumps(K, ensure_ascii=False)): bad.append('Landline found: no landline is ever used (KSL 013-209 6002 primary / 014-280 6002 secondary; Johor Jaya 019-230 0923)')
if not re.search(r'id=["\']ringkasan', BLOG) or not re.search(r'[\u4e00-\u9fff]', BLOG_TEXT) or not re.search(r'\b(farmasi|buka|setiap hari)\b', bl): bad.append('Blog needs the BM + Chinese summary block (id="ringkasan") (shopper feedback: 0/9 BM/ZH prompts covered)')
if len(y['title']) > 100: bad.append(f"YouTube title {len(y['title'])} chars (max 100)")
if len(y['description']) > 5000: bad.append('YouTube description over 5,000 chars')
if len(y['tags']) > 500: bad.append('YouTube tags over 500 chars')
if len(K['tiktok']['caption']) > 2200: bad.append('TikTok caption over 2,200 chars')
if len(K['whatsapp'].split()) > 300: bad.append(f"WhatsApp {len(K['whatsapp'].split())} words (max 300)")
words = len(BLOG_TEXT.split())
if not 1500 <= words <= 2100: bad.append(f'Blog body {words} words (target 1,500–2,000)')
mentions = len(re.findall(r'johor bahru|\bjb\b|ksl city mall|alpro pharmacy', BLOG_TEXT, re.I))
if mentions < 6: bad.append(f'Blog local mentions {mentions} (min 6)')
for need in ('application/ld+json', '"FAQPage"', '"Pharmacy"', '"BreadcrumbList"', 'id="key-takeaways"', 'id="faq"'):
    if need not in BLOG: bad.append(f'Blog missing {need}')
ext = len(re.findall(r'href="https?://(?:www\.)?(?:who\.int|[\w.]*moh\.gov\.my|pubmed\.ncbi\.nlm\.nih\.gov)', BLOG))
if ext < 2: bad.append(f'Blog has {ext} WHO/MOH/PubMed links (min 2)')

# 4. Video files
def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height', '-of', 'json', path], capture_output=True, text=True).stdout
    j = json.loads(out or '{}'); st = [x for x in j.get('streams', []) if x.get('width')]
    return float(j.get('format', {}).get('duration', 0)), (st[0]['width'], st[0]['height']) if st else (0, 0)
def lufs(path):
    out = subprocess.run(['ffmpeg', '-hide_banner', '-i', path, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = re.findall(r'I:\s+(-?[\d.]+) LUFS', out); return float(m[-1]) if m else None
if '--video' in opt:
    v = opt['--video']; base = os.path.splitext(v)[0]
    for path, lo, hi in ((v, 15, 60), (base + '_GBP30.mp4', 5, 30.0), (base + '_ZH.mp4', 15, 60)):
        if not os.path.exists(path):
            if path == v: bad.append(f'Video missing: {path}')
            continue
        dur, wh = probe(path)
        if not lo <= dur <= hi: bad.append(f'{os.path.basename(path)}: {dur:.1f}s (allowed {lo}–{hi}s)')
        if wh != (1080, 1920): bad.append(f'{os.path.basename(path)}: {wh[0]}x{wh[1]} (must be 1080x1920)')
        L = lufs(path)
        if L is None or not -16 <= L <= -12: bad.append(f'{os.path.basename(path)}: loudness {L} LUFS (target -14)')

# 5. No repeats vs Marketer Log
def sim(a, b): return difflib.SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()
sc0 = (S.get('scenes') or [{}])[0]; hook_now = sc0.get('line') or ' '.join(l.get('text', '') for l in sc0.get('lines', []))
checklist_now = ' / '.join(it['text'] for sc in S.get('scenes', []) for e in sc.get('elements', []) if e.get('type') == 'checklist' for it in e['items'])
for row in LOG:
    if row.get('Episode') == K['episode']: continue
    ep = row.get('Episode', '?')
    if hook_now and sim(hook_now, row.get('Hook line', '')) > 0.75: bad.append(f'Repeat: hook line too close to {ep}')
    if checklist_now and sim(checklist_now, row.get('Checklist items', '')) > 0.7: bad.append(f'Repeat: checklist items too close to {ep}')
    if row.get('GBP text') and sim(g, row['GBP text']) > 0.6: bad.append(f'Repeat: Google Business text too close to {ep}')
    if sim(K['blog']['title'], row.get('Blog title', '')) > 0.8: bad.append(f'Repeat: blog title too close to {ep}')

X = K.get('xiaohongshu')
if not X: bad.append('Xiaohongshu note missing (kit.json "xiaohongshu")')
else:
    if len(X.get('title', '')) > 20: bad.append(f'Xiaohongshu title {len(X["title"])} characters (max 20)')
    if not 300 <= len(X.get('body', '')) <= 1000: bad.append(f'Xiaohongshu body {len(X.get("body", ""))} characters (300–1000)')
    if not re.search(r'[\u4e00-\u9fff]', X.get('title', '') + X.get('body', '')): bad.append('Xiaohongshu note is not in Chinese')
    if re.search(r'https?://|www\.|wa\.me|whatsapp|微信|wechat|\b0\d{1,2}[- ]?\d{3,4}[- ]?\d{3,4}\b|\+?60\d{8,10}', ' '.join([X.get('title', ''), X.get('body', ''), X.get('topics', '')]), re.I):
        bad.append('Xiaohongshu: no phone, WhatsApp, WeChat or links in the note (platform limits off-platform contact)')
    if X.get('topics', '').count('#') < 5: bad.append('Xiaohongshu: add 5–8 #topics')
    if not X.get('image') or X['image'] not in K.get('images', {}): bad.append('Xiaohongshu image missing from kit images')

if bad:
    print('FAIL\n- ' + '\n- '.join(dict.fromkeys(bad))); sys.exit(1)
print(f'PASS  blog {words} words · GBP {len(g)} chars · WhatsApp {len(K["whatsapp"].split())} words · YT title {len(y["title"])} chars')
