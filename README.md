# fadx-wallpapers

Rotating background images for the **FADX Desktop** (Farmasi Alpro Dashboard, Reference Panel).

## How it works
- The desktop reads every image in the `wallpapers/` folder through the jsDelivr CDN:
  `https://cdn.jsdelivr.net/gh/atexpharmacy-byte/fadx-wallpapers@main/wallpapers/<file>`
- Images crossfade on a timer (default every 10 minutes; admins can change it in
  Desktop → Start → Wallpaper settings).
- This repo must stay **public** — the CDN cannot read private repos.

## Adding a wallpaper
1. Open the `wallpapers/` folder on GitHub → **Add file → Upload files**.
2. Drop in `.jpg`, `.png` or `.webp` images (about 1920px wide, under ~500 KB is ideal).
3. Commit. New images appear on the desktop within ~12 hours (CDN cache).
   To show them immediately, open
   `https://purge.jsdelivr.net/gh/atexpharmacy-byte/fadx-wallpapers@main/` in a browser.

Darker, softer images keep the white icon labels readable.

## App icons (`icons/`)
Links on the desktop use a custom icon when a file here matches the link's **title**:
lower-case, spaces and symbols become `-`. Examples:

| Link title in REF sheet | Icon file |
|---|---|
| Atex CashLens | `icons/atex-cashlens.png` |
| Grab Panda (AGP) | `icons/grab-panda-agp.png` |
| JJBKCF Pharmacist | `icons/jjbkcf-pharmacist.png` |

Use square PNGs (256×256). Admins can see the exact filename for any link in
Desktop → Arrange mode → tap the link. Without a custom icon, Google-hosted apps
show a coloured monogram and other sites show their own favicon.
Removing a file removes it from the rotation.
