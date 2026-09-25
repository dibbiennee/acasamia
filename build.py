#!/usr/bin/env python3
"""
build.py — genera index.html a partire da source/demo.html.

Legge la sorgente (unico file che si modifica a mano), estrae ogni immagine
base64 in public/img/*.webp e scrive index.html con i percorsi al posto dei
data URI. Non tocca nient'altro: CSS, layout, animazioni e copy restano
esattamente quelli della sorgente.

Le immagini nella sorgente sono già dimensionate in fase di preparazione
(1280px per le foto di contenuto, 400px per le miniature di galleria), quindi
qui non si ridimensiona più nulla: si estrae e basta. L'unica eccezione è
l'hero, che riceve anche una variante leggera a 640px per lo srcset (è la
prima immagine che il browser scarica, l'unica dove vale la pena).

Rieseguibile: si rilancia da zero ogni volta che arriva una sorgente nuova.

Uso:
    python3 build.py
"""
import re
import base64
import subprocess
import os
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(ROOT, "source", "demo.html")
OUT_HTML = os.path.join(ROOT, "index.html")
OUT_IMG = os.path.join(ROOT, "public", "img")
OFFLINE = os.path.join(ROOT, "demo-offline.html")

# unico punto da cambiare al go-live del dominio finale: sostituisce
# __SITE_URL__ in canonical/og:url/og:image. Quando acasamiacivitavecchia.it
# serve il sito, portalo a "https://acasamiacivitavecchia.it" e aggiungi il
# redirect 301 da acasamia.satoshiweb.it verso il nuovo dominio.
SITE_URL = "https://acasamia.satoshiweb.it"

# (alt text che identifica univocamente il tag, nome file, eager?, sizes per
# il srcset — None per l'hero, che ha la sua gestione a parte)
NAMED_IMAGES = [
    ("Il bancone di A casa mia", "hero", True, None),
    ("Il nostro barman prepara un cocktail da A casa mia", "sala", False, "(min-width:900px) 1032px, 100vw"),
    ("Colazione dolce e salata", "colazione", False, "(min-width:760px) 340px, 46vw"),
    ("Brunch da A casa mia", "brunch", False, "(min-width:760px) 340px, 46vw"),
    ("Aperitivo da A casa mia", "aperitivo", False, "(min-width:760px) 340px, 46vw"),
    ("Pranzo da A casa mia", "pranzo", False, "(min-width:760px) 340px, 46vw"),
    ("Yogurt e frutta fresca per la merenda da A casa mia", "merende", False, "(min-width:760px) 340px, 46vw"),
    ("Il nostro staff serve un piatto per i gruppi da A casa mia", "gruppi", False, "(min-width:760px) 340px, 46vw"),
    ("Pasta artigianale dei nostri piccoli produttori", "partner", False, "260px"),
    ("L'insegna di A casa mia in Via XVI Settembre", "dove", False, "(min-width:900px) 1032px, 100vw"),
]

# le due immagini banner non hanno alt (decorative, il testo è nel markup
# sopra): le individuo per ordine di apparizione dentro <a class="banner">
BANNER_NAMES = ["banner-glovo", "banner-evento"]

# le 10 miniature di galleria: <button data-full="BASE64"><img src="BASE64">
GALLERY_NAMES = ["lettura", "hero", "bruschetta", "prodotti", "aperitivo",
                  "cocktail", "romanesco", "pranzo", "vino", "brunch"]


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def decode_dims(path):
    r = subprocess.run(["dwebp", path, "-o", "/dev/null"], capture_output=True, text=True)
    m = re.search(r"Dimensions:\s*(\d+)\s*x\s*(\d+)", r.stdout + r.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def build_og_image(hero_webp_path, out_path):
    """og-image.jpg (1200x630) ritagliata dall'hero, stesso punto di fuoco
    della CSS (object-position: center 42%). JPEG a parte perché i social
    leggono JPEG molto più affidabilmente di un WebP."""
    im = Image.open(hero_webp_path).convert("RGB")
    w, h = im.size
    target_ratio = 1200 / 630
    crop_w = w
    crop_h = round(crop_w / target_ratio)
    if crop_h > h:
        crop_h = h
        crop_w = round(crop_h * target_ratio)
    cy = int(h * 0.42)
    top = max(0, min(h - crop_h, cy - crop_h // 2))
    left = max(0, (w - crop_w) // 2)
    crop = im.crop((left, top, left + crop_w, top + crop_h))
    crop.resize((1200, 630), Image.LANCZOS).save(out_path, "JPEG", quality=85, optimize=True)


def save_webp(raw_bytes, out_path):
    with open(out_path, "wb") as f:
        f.write(raw_bytes)


def build_small_variant(full_webp_path, small_webp_path, width=640):
    """Variante più leggera per i telefoni: stessa immagine a metà risoluzione."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        full_png = os.path.join(tmp, "full.png")
        run(["dwebp", full_webp_path, "-o", full_png])
        small_png = os.path.join(tmp, "small.png")
        run(["sips", "-Z", str(width), full_png, "--out", small_png])
        run(["cwebp", "-q", "82", "-m", "6", small_png, "-o", small_webp_path])


def main():
    data = open(SOURCE, encoding="utf-8").read()
    os.makedirs(OUT_IMG, exist_ok=True)
    for f in os.listdir(OUT_IMG):
        os.remove(os.path.join(OUT_IMG, f))

    out = data.replace("__SITE_URL__", SITE_URL)

    # ---------- 1. le foto con alt riconoscibile ----------
    for alt, name, eager, sizes in NAMED_IMAGES:
        pattern = re.compile(
            r'<img([^>]*?)src="data:image/webp;base64,([A-Za-z0-9+/=]+)"([^>]*?)alt="' + re.escape(alt) + r'"([^>]*)>'
        )
        m = pattern.search(out)
        if not m:
            raise SystemExit(f"immagine non trovata nella sorgente: alt=\"{alt}\"")
        raw = base64.b64decode(m.group(2))
        fname = f"{name}.webp"
        save_webp(raw, os.path.join(OUT_IMG, fname))
        w, h = decode_dims(os.path.join(OUT_IMG, fname))

        # gli attributi scritti a mano prima di src (es. class="chi-foto") vanno
        # riportati sul tag nuovo, altrimenti si perde lo stile dell'immagine
        attrs_before = m.group(1)

        if name == "hero":
            build_small_variant(os.path.join(OUT_IMG, fname), os.path.join(OUT_IMG, "hero-640.webp"))
            build_og_image(os.path.join(OUT_IMG, fname), os.path.join(OUT_IMG, "og-image.jpg"))
            new_tag = (f'<img{attrs_before}src="public/img/{fname}" srcset="public/img/hero-640.webp 640w, public/img/{fname} {w}w" '
                       f'sizes="100vw" width="{w}" height="{h}" alt="{alt}" loading="eager" fetchpriority="high">')
            print(f"  {name}: {w}x{h} (+ variante 640px + og-image.jpg)")
        else:
            # variante più leggera per telefoni e tablet, in aggiunta alla foto piena
            small_name = f"{name}-640.webp"
            build_small_variant(os.path.join(OUT_IMG, fname), os.path.join(OUT_IMG, small_name))
            loading = "eager" if eager else "lazy"
            new_tag = (f'<img{attrs_before}src="public/img/{fname}" srcset="public/img/{small_name} 640w, public/img/{fname} {w}w" '
                       f'sizes="{sizes}" width="{w}" height="{h}" alt="{alt}" loading="{loading}">')
            print(f"  {name}: {w}x{h} (+ variante 640px)")

        out = out[:m.start()] + new_tag + out[m.end():]

    # ---------- 2. la galleria: <button data-full="B64"><img src="B64" ...></button> ----------
    # va prima dei banner: il tag <img> qui dentro ha la stessa forma esatta di
    # quello dei banner (src data-uri, alt="", loading="lazy"), e il pattern dei
    # banner non ha modo di escluderlo. Estraendo prima la galleria, quei tag
    # smettono di essere data URI e il pattern dei banner più sotto non li vede più.
    gal_pattern = re.compile(
        r'<button type="button"([^>]*?)data-full="([A-Za-z0-9+/=]+)"><img src="data:image/webp;base64,([A-Za-z0-9+/=]+)" alt="" loading="lazy"></button>'
    )
    gal_matches = list(gal_pattern.finditer(out))
    if len(gal_matches) != len(GALLERY_NAMES):
        raise SystemExit(f"attese {len(GALLERY_NAMES)} foto in galleria, trovate {len(gal_matches)}")
    for m, name in list(zip(gal_matches, GALLERY_NAMES))[::-1]:
        cls_attr, full_b64, thumb_b64 = m.group(1), m.group(2), m.group(3)
        full_fname = f"gal-{name}-full.webp"
        thumb_fname = f"gal-{name}-thumb.webp"
        save_webp(base64.b64decode(full_b64), os.path.join(OUT_IMG, full_fname))
        save_webp(base64.b64decode(thumb_b64), os.path.join(OUT_IMG, thumb_fname))
        tw, th = decode_dims(os.path.join(OUT_IMG, thumb_fname))
        new_tag = (f'<button type="button"{cls_attr}data-full="public/img/{full_fname}">'
                   f'<img src="public/img/{thumb_fname}" alt="" width="{tw}" height="{th}" loading="lazy"></button>')
        out = out[:m.start()] + new_tag + out[m.end():]
        print(f"  galleria {name}")

    # ---------- 3. i due banner (senza alt, dentro <a class="banner">) ----------
    banner_pattern = re.compile(r'<img src="data:image/webp;base64,([A-Za-z0-9+/=]+)" alt="" loading="lazy">')
    matches = list(banner_pattern.finditer(out))
    if len(matches) != len(BANNER_NAMES):
        raise SystemExit(f"attesi {len(BANNER_NAMES)} banner, trovati {len(matches)}")
    for m, name in list(zip(matches, BANNER_NAMES))[::-1]:
        raw = base64.b64decode(m.group(1))
        fname = f"{name}.webp"
        save_webp(raw, os.path.join(OUT_IMG, fname))
        bw, bh = decode_dims(os.path.join(OUT_IMG, fname))
        new_tag = f'<img src="public/img/{fname}" alt="" width="{bw}" height="{bh}" loading="lazy">'
        out = out[:m.start()] + new_tag + out[m.end():]
        print(f"  {name}")

    # il lightbox in JS anteponeva 'data:image/webp;base64,' al valore di data-full:
    # ora data-full è già un percorso, quindi quel prefisso va tolto
    old_js = "lbImg.src = 'data:image/webp;base64,' + b.getAttribute('data-full');"
    new_js = "lbImg.src = b.getAttribute('data-full');"
    if old_js not in out:
        raise SystemExit("riga JS della lightbox non trovata, controllare a mano")
    out = out.replace(old_js, new_js)

    if "data:image/webp;base64," in out:
        raise SystemExit("sono rimasti dei data URI non sostituiti, controllare a mano")

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"scritto {OUT_HTML} ({len(out)} byte, era {len(data)})")

    import shutil
    shutil.copyfile(SOURCE, OFFLINE)
    print(f"copiato {OFFLINE} (copia offline, invariata)")


if __name__ == "__main__":
    main()
