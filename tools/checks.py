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
        r'infertil\w*', r'mandul', r'impoten\w*']
CLAIMS = [r'\bcures?\b', r'\bcured\b', r'\btreats?\b(?!ment plan)', r'\bprevents?\b', r'\bheals (?:your|you|the)\b', r'\bguarantee\w*', r'\bmiracle\b', r'\b100% safe\b']
corpus = {
  'video lines': ' '.join(sc.get('line', '') for sc in S.get('scenes', [])) + ' ' + S.get('hook_text', ''),
  'video cards': json.dumps([sc.get('elements', []) for sc in S.get('scenes', [])], ensure_ascii=False),
  'blog': BLOG,
  'youtube': ' '.join([K['youtube']['title'], K['youtube']['description'], K['youtube']['tags']]),
  'tiktok': K['tiktok']['caption'] + ' ' + ' '.join(K['tiktok'].get('alt_hooks', [])),
  'facebook/instagram': K['meta']['caption'] + ' ' + K['meta']['first_comment'],
  'google business': K['gbp']['text'], 'whatsapp': K['whatsapp'],
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
# 1b. Implied conditions: 2+ classic signs of ONE scheduled condition in the same channel = MASA risk even if never named
SIGNS = {
  'diabetes': [r'thirst\w*', r'frequent (?:toilet|urinat\w*|pee\w*)|(?:running|run|rush\w*|go\w*|trips?) to the (?:toilet|loo|bathroom)|(?:toilet|bathroom|pee\w*) (?:trips|a lot|often|again|many times)', r'slow(?:ly)? heal\w*|wounds? (?:not|won.t|don.t) heal', r'blurr?y (?:eyes|vision)', r'tingl\w*|numb (?:feet|toes|hands)', r'(?:sudden|unexplained) weight loss'],
  'hypertension': [r'headaches?', r'dizz\w*', r'nose ?bleeds?', r'pounding (?:head|heart)'],
  'heart disease': [r'chest (?:pain|tight\w*|pressure)', r'short(?:ness)? of breath|breathless\w*', r'left arm', r'cold sweat\w*'],
  'asthma': [r'wheez\w*', r'tight chest', r'cough\w* at night|night cough\w*', r'short(?:ness)? of breath|breathless\w*'],
  'kidney disease': [r'foamy (?:urine|pee)', r'swollen (?:ankles|feet|legs)', r'puffy eyes', r'(?:less|little) (?:urine|pee)'],
}
for where, txt in list(corpus.items()) + [('blog text', BLOG_TEXT)]:
    if where == 'blog': continue
    low = txt.lower()
    for cond, pats in SIGNS.items():
        hit = [m.group(0) for p in pats for m in [re.search(p, low)] if m]
        if len(hit) >= 2: bad.append(f'MASA: {where} lists {len(hit)} classic signs of {cond} {hit} (implies the condition; use habits, not a symptom list)')

# 1c. Numeric health readings: never (no BP, sugar, cholesterol or similar values)
READ = [r'\b(?:9\d|1\d\d|2[0-4]\d)\s*/\s*(?:[5-9]\d|1[0-3]\d)\b', r'\d+(?:\.\d+)?\s*(?:mmol|mg\s*/\s*dl|mmhg)', r'\bhba1c\b|\ba1c\b',
        r'(?:sugar|glucose|pressure|cholesterol|bp)\s+(?:level|reading|of|is|was|at|=|:)?\s*(?:only\s+|around\s+|about\s+)?\d+(?:\.\d+)?\b(?!\s*(?:g\b|grams?|teaspoons?|tsp|%|kcal|calories|minutes|min|times|cups?|ml))']
for where, txt in list(corpus.items()) + [('blog text', BLOG_TEXT)]:
    if where == 'blog': continue
    for p in READ:
        m = re.search(p, txt.lower())
        if m: bad.append(f'Numeric reading "{m.group(0)}" in {where} (never show readings; say "a quick check")')

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
    for path, lo, hi in ((v, 15, 60), (base + '_GBP30.mp4', 5, 30.0)):
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
hooks_now = [h for h in [(S.get('scenes') or [{}])[0].get('line', ''), S.get('hook_text', '')] + K['tiktok'].get('alt_hooks', []) if h]
checklist_now = ' / '.join(it['text'] for sc in S.get('scenes', []) for e in sc.get('elements', []) if e.get('type') == 'checklist' for it in e['items'])
for row in LOG:
    if row.get('Episode') == K['episode']: continue
    ep = row.get('Episode', '?')
    for h in hooks_now:
        if row.get('Hook line') and sim(h, row['Hook line']) > 0.75: bad.append(f'Repeat: hook "{h}" too close to {ep}')
    if checklist_now and sim(checklist_now, row.get('Checklist items', '')) > 0.7: bad.append(f'Repeat: checklist items too close to {ep}')
    if row.get('GBP text') and sim(g, row['GBP text']) > 0.6: bad.append(f'Repeat: Google Business text too close to {ep}')
    if sim(K['blog']['title'], row.get('Blog title', '')) > 0.8: bad.append(f'Repeat: blog title too close to {ep}')

if bad:
    print('FAIL\n- ' + '\n- '.join(dict.fromkeys(bad))); sys.exit(1)
print(f'PASS  blog {words} words · GBP {len(g)} chars · WhatsApp {len(K["whatsapp"].split())} words · YT title {len(y["title"])} chars')
