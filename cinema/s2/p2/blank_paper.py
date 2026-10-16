# blank_paper.py: remove Kling's fake text from white paper props in the first N seconds of a clip.
# usage: python3 blank_paper.py in.mp4 out.mp4 seconds
import sys, subprocess, os, tempfile, glob
import numpy as np
from PIL import Image
from scipy import ndimage
src, out, secs = sys.argv[1], sys.argv[2], float(sys.argv[3])
tmp = tempfile.mkdtemp()
subprocess.run(['ffmpeg','-v','error','-y','-i',src,'-t',str(secs),os.path.join(tmp,'f%04d.png')],check=True)
for p in sorted(glob.glob(os.path.join(tmp,'f*.png'))):
    a = np.asarray(Image.open(p).convert('RGB')).astype(np.int16)
    mx, mn = a.max(2), a.min(2)
    white = (mn > 150) & (mx - mn < 45)
    white = ndimage.binary_opening(white, iterations=2)
    lab, n = ndimage.label(white)
    if n:
        sizes = ndimage.sum(white, lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s > 15000])
        filled = ndimage.binary_closing(keep, iterations=9)
        filled = ndimage.binary_fill_holes(filled) & ~ndimage.binary_erosion(np.ones_like(keep), iterations=0) | filled
        filled = ndimage.binary_fill_holes(filled)
        text = ndimage.binary_erosion(filled, iterations=3)
        if text.any():
            # replace text pixels with a blur of the paper itself
            b = a.copy().astype(np.float32)
            paper = np.where(keep[..., None], a, 0).astype(np.float32)
            w = ndimage.gaussian_filter(keep.astype(np.float32), 30)
            for c in range(3):
                b[..., c] = np.where(text, ndimage.gaussian_filter(paper[..., c], 30) / np.maximum(w, 1e-3), a[..., c])
            a = np.clip(b, 0, 255)
    Image.fromarray(a.astype(np.uint8)).save(p)
head = os.path.join(tmp, 'head.mp4'); tail = os.path.join(tmp, 'tail.mp4')
subprocess.run(['ffmpeg','-v','error','-y','-framerate','24','-i',os.path.join(tmp,'f%04d.png'),'-c:v','libx264','-crf','14','-pix_fmt','yuv420p','-r','24',head],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-ss',str(secs),'-i',src,'-an','-c:v','libx264','-crf','14','-pix_fmt','yuv420p','-r','24',tail],check=True)
lst = os.path.join(tmp,'l.txt'); open(lst,'w').write(f"file '{head}'\nfile '{tail}'\n")
vid = os.path.join(tmp,'v.mp4')
subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',lst,'-c','copy',vid],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',vid,'-i',src,'-map','0:v','-map','1:a','-c:v','copy','-c:a','copy','-shortest',out],check=True)
print('ok', out)
