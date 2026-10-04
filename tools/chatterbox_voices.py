#!/usr/bin/env python3
"""chatterbox_voices.py: voice every line of an Uncle Lim episode with Chatterbox (MIT licence, free).
Runs on Yeoh's PC (CPU is fine: uses Chatterbox-Nano) or Google Colab (GPU: uses Chatterbox-Turbo).
Each character is cloned from voice_refs/<Name>.wav (our own Kokoro-made reference voices, so we own them).

setup once:   pip install chatterbox-tts
usage:        python chatterbox_voices.py story.json
output:       voices_out/*.wav + story_cb.json (same story, every line has "wav") -> render with marketer.py v4:
              python3 marketer.py story_cb.json <Episode>_Video.mp4
Paralinguistic tags allowed inside a line: [laugh] [chuckle] [cough]  (stripped from captions automatically)."""
import json, os, re, sys
import torch, torchaudio as ta
from chatterbox.tts_turbo import ChatterboxTurboTTS

story_path = sys.argv[1] if len(sys.argv) > 1 else 'story.json'
HERE = os.path.dirname(os.path.abspath(story_path))
REFS = os.path.join(HERE, 'voice_refs'); OUT = os.path.join(HERE, 'voices_out'); os.makedirs(OUT, exist_ok=True)
NARRATOR = 'Mei'

dev = 'cuda' if torch.cuda.is_available() else 'cpu'
model = ChatterboxTurboTTS.from_pretrained(device=dev, nano=(dev == 'cpu'))
print('Chatterbox', 'Turbo (GPU)' if dev == 'cuda' else 'Nano (CPU)')

def ref(who):
    p = os.path.join(REFS, re.sub(r'\W+', '_', who).strip('_') + '.wav')
    if not os.path.exists(p): sys.exit(f'missing reference voice: {p}')
    return p

story = json.load(open(story_path, encoding='utf-8'))
for i, sc in enumerate(story['scenes']):
    lines = sc.get('lines') or [{'who': sc.get('who', NARRATOR), 'text': sc['line']}]
    for j, ln in enumerate(lines):
        f = os.path.join(OUT, f's{i+1:02d}_{j+1}.wav')
        if not os.path.exists(f):
            wav = model.generate(ln['text'], audio_prompt_path=ref(ln.get('who') or NARRATOR))
            ta.save(f, wav, model.sr)
        ln['wav'] = os.path.relpath(f, HERE).replace('\\', '/')
        print(f'scene {i+1} line {j+1} {ln.get("who") or NARRATOR}: {ln["text"]}')
    if sc.get('lines'): sc['lines'] = lines
    else: sc['wav'] = lines[0]['wav']

json.dump(story, open(os.path.join(HERE, 'story_cb.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('OK story_cb.json  ->  python3 marketer.py story_cb.json <Episode>_Video.mp4')
