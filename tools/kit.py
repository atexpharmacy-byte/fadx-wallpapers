#!/usr/bin/env python3
"""kit.py: kit.json (+ blog.html + images) -> <episode>_Posting_Kit.html, standalone (opens offline in Edge).
usage: python3 kit.py kit.json [out.html]"""
import json, sys, os, base64, html
CSS = r'''/* Layout: one reading column; sticky checklist rail on wide screens; every copyable block = label + box + copy button */
:root{
  --paper:#F4F1E8; --card:#FFFFFF; --ink:#1E2A25; --muted:#5C6B64; --line:#DAD5C6;
  --brand:#1B4583; --deep:#1B4583; --deep2:#12305E; --mint:#5B8FD6; --gold:#B8862B; --red:#B23A2E;
  --codebg:#FBFAF5; --chip:#E7EEF8;
  --f-display:"Fraunces",Georgia,serif; --f-body:"Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif; --f-mono:"JetBrains Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#111815; --card:#18221E; --ink:#E7EEE9; --muted:#9DB0A6; --line:#2B3833;
  --brand:#8DB4EA; --deep:#1B4583; --deep2:#12305E; --mint:#5B8FD6; --gold:#D9A94B; --red:#E0695C;
  --codebg:#131C18; --chip:#1E2C44; color-scheme:dark}}
:root[data-theme="dark"]{
  --paper:#111815; --card:#18221E; --ink:#E7EEE9; --muted:#9DB0A6; --line:#2B3833;
  --brand:#8DB4EA; --deep:#1B4583; --deep2:#12305E; --mint:#5B8FD6; --gold:#D9A94B; --red:#E0695C;
  --codebg:#131C18; --chip:#1E2C44; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font-family:var(--f-body);font-size:16px;line-height:1.55}
.wrap{max-width:1120px;margin:0 auto;padding-inline:16px;padding-block:0 64px}
header.top{background:linear-gradient(135deg,#1B4583,#12305E);color:#F4F1E8;padding-block:28px 26px}
header.top .wrap{padding-block:0}
.brandlogo{float:right;width:96px;height:96px;border-radius:14px;background:#fff;margin-left:16px}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#BFD3F2;font-weight:700}
header.top h1{font-family:var(--f-display);font-weight:600;font-size:clamp(28px,4.5vw,42px);line-height:1.1;margin:6px 0 10px;text-wrap:balance}
header.top p{margin:0;max-width:62ch;color:#D6E2F5}
.meta-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.meta-row span{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:3px 12px;font-size:13px}
.grid{display:grid;grid-template-columns:260px minmax(0,1fr);gap:32px;margin-top:28px;align-items:start}
@media (max-width:860px){.grid{grid-template-columns:minmax(0,1fr)}}
nav.rail{position:sticky;top:calc(env(safe-area-inset-top,0px) + 16px);background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
@media (max-width:860px){nav.rail{position:static}}
nav.rail h2{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
nav.rail ol{margin:0;padding:0;list-style:none;display:grid;gap:6px;counter-reset:s}
nav.rail li{display:flex;gap:10px;align-items:flex-start}
nav.rail input{margin-top:4px;accent-color:var(--brand)}
nav.rail a{color:var(--ink);text-decoration:none;font-weight:600;font-size:14.5px}
nav.rail a:hover{color:var(--brand)}
nav.rail small{display:block;color:var(--muted);font-weight:400;font-size:12.5px}
main{min-width:0;display:grid;gap:36px}
section.part{min-width:0}
.part-h{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;border-bottom:2px solid var(--line);padding-bottom:8px;margin-bottom:16px}
.badge{background:var(--deep);color:#F4F1E8;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.08em;padding:3px 11px;text-transform:uppercase}
.part-h h2{font-family:var(--f-display);font-size:26px;font-weight:600;margin:0}
.where{color:var(--muted);font-size:14px;margin:-6px 0 14px}
.field{display:grid;gap:6px;margin-bottom:16px}
.field-top{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.label{font-weight:700;font-size:14px}
.label em{font-style:normal;color:var(--muted);font-weight:400;margin-left:6px;font-variant-numeric:tabular-nums}
.box{background:var(--codebg);border:1px solid var(--line);border-radius:8px;padding:12px 14px;white-space:pre-wrap;word-break:break-word;font-size:15px;min-width:0}
.box.mono{font-family:var(--f-mono);font-size:13px;max-height:320px;overflow:auto}
textarea.box{width:100%;min-height:260px;font-family:var(--f-mono);font-size:12.5px;color:var(--ink);resize:vertical}
button.copy{font:inherit;font-size:13px;font-weight:700;border:1px solid var(--brand);background:transparent;color:var(--brand);border-radius:999px;padding:4px 14px;cursor:pointer}
button.copy:hover{background:var(--chip)}
button.copy:focus-visible,nav.rail a:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
button.copy.done{background:var(--brand);color:var(--card)}
.note{border-left:4px solid var(--gold);background:var(--card);padding:12px 16px;border-radius:0 8px 8px 0;font-size:15px}
.note.red{border-color:var(--red)}
.note strong{display:block;margin-bottom:2px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.kv{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;font-size:15px}
.kv dt{color:var(--muted)}
.kv dd{margin:0;font-weight:600}
figure.asset{margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;display:grid;gap:8px}
figure.asset img{border-radius:6px;width:100%;height:auto}
figure.asset figcaption{font-size:13px;color:var(--muted)}
figure.asset b{color:var(--ink)}
.preview{background:#fff;color:#1E2A25;border:1px solid var(--line);border-radius:10px;padding:clamp(14px,3vw,32px);max-height:640px;overflow:auto}
details.pv summary{cursor:pointer;font-weight:700;margin-bottom:10px;color:var(--brand)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
'''
JS = r'''(function(){
  var tpl=document.getElementById('blog-src');
  var html=tpl.innerHTML.trim();
  var ta=document.getElementById('t-blog'); ta.value=html;
  var pv=document.getElementById('blog-preview');
  var node=tpl.content.cloneNode(true);
  node.querySelectorAll('img').forEach(function(i){var s=i.getAttribute('src'); if(s&&IMG[s]) i.setAttribute('src',IMG[s]);});
  pv.appendChild(node);
  var words=(pv.querySelector('article')||pv).innerText.trim().split(/\s+/).length;
  document.getElementById('blog-words').textContent='~'+words+' words';
  document.querySelectorAll('[data-count]').forEach(function(el){
    var t=document.getElementById(el.getAttribute('data-count')); if(!t) return;
    var s=t.textContent.trim();
    el.textContent=el.hasAttribute('data-words')? s.split(/\s+/).length+' words' : s.length+' chars';
  });
  document.querySelectorAll('button.copy').forEach(function(b){
    b.addEventListener('click',function(){
      var t=document.getElementById(b.getAttribute('data-target'));
      var text=t.tagName==='TEXTAREA'?t.value:t.textContent.trim();
      var label=b.textContent;
      function ok(){b.textContent='Copied';b.classList.add('done');setTimeout(function(){b.textContent=label;b.classList.remove('done');},1600);}
      function fallback(){
        if(t.tagName==='TEXTAREA'){t.focus();t.select();}
        else{var r=document.createRange();r.selectNodeContents(t);var sel=getSelection();sel.removeAllRanges();sel.addRange(r);}
        b.textContent='Selected, press Ctrl+C';
        setTimeout(function(){b.textContent=label;},2200);
      }
      try{navigator.clipboard.writeText(text).then(ok,fallback);}catch(e){fallback();}
    });
  });
  document.querySelectorAll('nav.rail input[type=checkbox]').forEach(function(c){
    try{c.checked=localStorage.getItem('kit-'+c.id)==='1';}catch(e){}
    c.addEventListener('change',function(){try{localStorage.setItem('kit-'+c.id,c.checked?'1':'0');}catch(e){}});
  });
})();
'''
K = json.load(open(sys.argv[1])); D = os.path.dirname(os.path.abspath(sys.argv[1]))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, K['episode'] + '_Posting_Kit.html')
e = lambda t: html.escape(str(t), quote=True)
IMG = {n: 'data:image/jpeg;base64,' + base64.b64encode(open(os.path.join(D, p), 'rb').read()).decode() for n, p in K['images'].items()}
BLOG = open(os.path.join(D, K['blog']['html_file'])).read().strip()

def field(label, id_, text, count=None, btn='Copy'):
    c = {'chars': '<em data-count="%s"></em>' % id_, 'words': '<em data-count="%s" data-words="1"></em>' % id_}.get(count, '')
    return ('<div class="field"><div class="field-top"><span class="label">%s %s</span><button class="copy" data-target="%s">%s</button></div>'
            '<div class="box" id="%s">%s</div></div>') % (e(label), c, id_, btn, id_, e(text))
def kv(d): return '<dl class="kv">' + ''.join('<dt>%s</dt><dd>%s</dd>' % (e(k), e(v)) for k, v in d.items()) + '</dl>'
def fig(n, cap, alt=''): return '<figure class="asset"><img src="%s" alt="%s"><figcaption><b>%s</b> · %s</figcaption></figure>' % (IMG[n], e(alt or n), e(n), e(cap))
def part(id_, badge, title, where, body):
    return '<section class="part" id="%s"><div class="part-h"><span class="badge">%s</span><h2>%s</h2></div><p class="where">%s</p>%s</section>' % (id_, badge, e(title), where, body)

b, y, t, m, g = K['blog'], K['youtube'], K['tiktok'], K['meta'], K['gbp']
steps = [('blog', 'Blog post', 'Publish first to get the link'), ('youtube', 'YouTube Shorts', 'Add blog link in description'),
         ('tiktok', 'TikTok', 'Turn on AI-generated label'), ('meta', 'Facebook + Instagram Reels', 'One caption for both'),
         ('gbp', 'Google Business post', 'Image + text + button'), ('whatsapp', 'WhatsApp broadcast', 'Last, with all links')]
rail = ('<nav class="rail" aria-label="Posting checklist"><h2>Post in this order</h2><ol>' +
        ''.join('<li><input type="checkbox" id="c%d" aria-label="%s done"><a href="#%s">%s<small>%s</small></a></li>' % (i + 1, e(s[1]), s[0], e(s[1]), e(s[2])) for i, s in enumerate(steps)) +
        '</ol></nav>')
parts = [
 part('blog', 'Step 1', 'Blog post (Blogger)', 'Blogger → New post → switch to <b>HTML view</b> → paste. Fill the post settings from the fields below.',
   field('Post title', 't-title', b['title'], 'chars') + field('Search description (Blogger "Search Description")', 't-meta', b['search_description'], 'chars') +
   '<div class="two">' + field('Custom permalink', 't-slug', b['permalink']) + field('Labels', 't-labels', b['labels']) + '</div>' + field('Focus keywords (LSI)', 't-lsi', b['lsi']) +
   '<div class="note"><strong>Images: upload before publishing</strong>Upload each blog image in Blogger (Insert image → Upload), then in HTML view replace <code>src="blog_…jpg"</code> with the link Blogger gives you. The images are in the <a href="#files">Image files</a> section (right-click → Save image as).</div>' +
   '<div class="field" style="margin-top:16px"><div class="field-top"><span class="label">Full post HTML (with JSON-LD schema) <em id="blog-words"></em></span><button class="copy" data-target="t-blog">Copy all HTML</button></div>'
   '<textarea class="box" id="t-blog" spellcheck="false" aria-label="Blog post HTML" readonly></textarea></div>'
   '<details class="pv"><summary>Preview the post</summary><div class="preview" id="blog-preview"></div></details>'),
 part('youtube', 'Step 2', 'YouTube Shorts', 'YouTube Studio → Create → Upload → %s. Vertical and under 60s, so it posts as a Short.' % e(K['video_file']),
   field('Title', 'y-title', y['title'], 'chars') + field('Description', 'y-desc', y['description']) + field('Tags (paste into "Tags")', 'y-tags', y['tags']) +
   '<div class="two">' + kv(dict([('Thumbnail', y['thumbnail'])] + list(y['settings'].items()))) + '</div>'),
 part('tiktok', 'Step 3', 'TikTok', 'Upload the same MP4 and pick <b>%s</b> as the cover. Under More options, turn on <b>AI-generated content</b>.' % e(K.get('cover', 'the frame with the hook title')),
   field('Caption', 'tt-cap', t['caption'], 'chars') +
   (field('A/B hooks: reuse as on-screen text or caption opener on a repost', 'tt-alt', '\n'.join(t['alt_hooks'])) if t.get('alt_hooks') else '') +
   (field('中文 caption (for the Mandarin video: %s)' % K.get('video_zh', ''), 'tt-zh', t['caption_zh'], 'chars') if t.get('caption_zh') else '') + kv(t['settings'])),
 part('meta', 'Step 4', 'Facebook + Instagram Reels', 'Meta Business Suite → Create Reel → tick both Facebook and Instagram. Turn on the AI label if prompted.',
   field('Caption', 'm-cap', m['caption']) + field('First comment (Facebook, pin it)', 'm-com', m['first_comment']) +
   (field('中文 caption', 'm-zh', m['caption_zh']) if m.get('caption_zh') else '')),
 part('gbp', 'Step 5', 'Google Business Profile post', 'Google Search your outlet name → Add update → upload the image → paste the text → add a button. Never type phone numbers, links or hashtags in the text: Google removes those posts.',
   '<div class="two">' + fig(g['image'], '1:1 square, 1200×1200 (min 720×720), little text', 'Google Business post image') + '<div>' + field('Post text', 'g-text', g['text'], 'chars') + kv(dict([('Post type', g.get('type','Update')), ('Button', g['button'])] + ([('Video option', g['video'] + ' (≤30s, upload instead of or after the photo)')] if g.get('video') else []))) + '</div></div>'),
 part('whatsapp', 'Step 6', 'WhatsApp broadcast', 'Send the MP4 first, then this message. Paste the link where marked.', field('Message', 'w-msg', K['whatsapp'], 'words')),
 part('files', 'Assets', 'Image files', 'Right-click an image → Save image as.',
   '<div class="two">' + ''.join(fig(n, 'YouTube thumbnail' if 'youtube' in n else 'blog image') for n in K['images'] if n != g['image']) + '</div>'),
]
head = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>%s Posting Kit</title>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono&display=swap">'
        '<style>\n' % e(K['episode'].replace('_', ' ')))
LOGO = ('<img class="brandlogo" alt="Alpro Pharmacy" src="data:image/png;base64,%s">' % base64.b64encode(open(os.path.join(D, K['logo']), 'rb').read()).decode()) if K.get('logo') else ''
top = ('<header class="top"><div class="wrap">' + LOGO + '<div class="eyebrow">AlproPost · Posting kit · %s</div><h1>%s</h1>'
       '<p>Everything you need to post this episode: blog, search meta, YouTube, TikTok, Facebook and Instagram, Google Business and WhatsApp. Work down the checklist in order.</p>'
       '<div class="meta-row"><span>Video: %s · %s</span>%s<span>Theme: %s</span><span>Outlet: %s</span></div></div></header>') % (
       e(K['date']), e(K['title_h1']), e(K['video_file']), e(K['video_meta']),
       ''.join('<span>%s</span>' % e(x) for x in (K.get('video_zh'), K['gbp'].get('video')) if x), e(K['theme']), e(K['outlet']))
page = (head + CSS + '\n</style></head><body style="margin:0">' + top +
        '<div class="wrap"><div class="grid">' + rail + '<main><div class="note red"><strong>Compliance check before posting</strong>' + e(K['compliance']) + '</div>' +
        ''.join(parts) + '</main></div></div><template id="blog-src">' + BLOG + '</template>\n<script>\nvar IMG=' +
        json.dumps({n: v for n, v in IMG.items() if n.startswith('blog_')}) + ';\n' + JS + '</script></body></html>')
open(OUT, 'w').write(page); print('OK', OUT, len(page) // 1024, 'KB')
