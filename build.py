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
OUT_EN = os.path.join(ROOT, "en", "index.html")

# unico punto da cambiare al go-live del dominio finale: sostituisce
# __SITE_URL__ in canonical/og:url/og:image. Quando acasamiacivitavecchia.it
# serve il sito, portalo a "https://acasamiacivitavecchia.it" e aggiungi il
# redirect 301 da acasamia.satoshiweb.it verso il nuovo dominio.
SITE_URL = "https://acasamia.satoshiweb.it"

# (alt text che identifica univocamente il tag, nome file, eager?, sizes per
# il srcset — None per l'hero, che ha la sua gestione a parte)
NAMED_IMAGES = [
    ("Cappuccino e cornetto sulla tovaglietta di A casa mia", "hero", True, None),
    ("Cornetto e cappuccino da A casa mia", "colazione", False, "(min-width:1000px) 580px, (min-width:760px) 45vw, 92vw"),
    ("Tramezzino e succo d'arancia da A casa mia", "brunch", False, "(min-width:1000px) 580px, (min-width:760px) 45vw, 92vw"),
    ("Brindisi con vino bianco e tagliere da A casa mia", "aperitivo", False, "(min-width:1000px) 580px, (min-width:760px) 45vw, 92vw"),
    ("Spaghetti del menu del giorno da A casa mia", "pranzo", False, "(min-width:1000px) 580px, (min-width:760px) 45vw, 92vw"),
    ("Pasta artigianale dei nostri piccoli produttori", "partner", False, "260px"),
    ("L'insegna di A casa mia in Via XVI Settembre", "dove", False, "(min-width:900px) 1032px, 100vw"),
]

# le due immagini banner non hanno alt (decorative, il testo è nel markup
# sopra): le individuo per ordine di apparizione dentro <a class="banner">
BANNER_NAMES = ["banner-glovo", "banner-evento"]

# le 10 miniature di galleria: <button data-full="BASE64"><img src="BASE64">
GALLERY_NAMES = ["hero", "bruschetta", "cocktail", "lettura", "romanesco",
                  "prodotti", "vino", "aperitivo", "brunch", "pranzo"]


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


# ---------------------------------------------------------------------------
# versione inglese: /en/index.html generata dalla stessa sorgente.
# i testi inglesi stanno negli attributi data-en della sorgente (unica fonte).
# ---------------------------------------------------------------------------
import html as _html

# alt delle immagini con alt descrittivo (italiano -> inglese)
ALT_EN = {
    "Cappuccino e cornetto sulla tovaglietta di A casa mia": "Cappuccino and cornetto on the A casa mia placemat",
    "Cornetto e cappuccino da A casa mia": "Cornetto and cappuccino at A casa mia",
    "Tramezzino e succo d'arancia da A casa mia": "Tramezzino sandwich and orange juice at A casa mia",
    "Brindisi con vino bianco e tagliere da A casa mia": "A toast with white wine and a sharing board at A casa mia",
    "Spaghetti del menu del giorno da A casa mia": "Spaghetti from the daily menu at A casa mia",
    "Pasta artigianale dei nostri piccoli produttori": "Artisan pasta from our small producers",
    "L'insegna di A casa mia in Via XVI Settembre": "The A casa mia sign on Via XVI Settembre",
}
EN_TITLE = "A casa mia · Café, brunch and aperitivo in Civitavecchia"
EN_DESC = ("A bistrot in the heart of Civitavecchia, a few steps from the port. "
           "Breakfast from 7:00, brunch, lunch and aperitivo at Via XVI Settembre 4.")
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
GIORNI_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ORE_RIGHE = ["7:00 – 17:00"] * 5 + ["8:00 – 15:00"] * 2


def seed_orari(page, nomi):
    """scrive nel sorgente l'elenco orari (prima lo generava solo il JS)"""
    righe = "".join(f"<li><span>{n}</span><span>{o}</span></li>" for n, o in zip(nomi, ORE_RIGHE))
    return page.replace('<ul class="orari" id="orari"></ul>', f'<ul class="orari" id="orari">{righe}</ul>', 1)


def strip_lang_attrs(page, keep=None):
    """toglie dalle pagine finali tutti gli attributi di traduzione: il testo giusto e' gia' nel markup"""
    for pat in (r' data-it="[^"]*"', r' data-en="[^"]*"', r' data-it-html="[^"]*"', r' data-en-html="[^"]*"',
                r' data-aria-it="[^"]*"', r' data-aria-en="[^"]*"'):
        page = re.sub(pat, "", page)
    return page


def make_en(it_page):
    page = it_page
    # testi semplici (le recensioni reali restano nell'originale)
    page = re.sub(r'(<(\w+)[^>]*?data-en="([^"]*)"[^>]*>)(.*?)(</\2>)',
                  lambda m: (m.group(1) + m.group(3) + m.group(5)) if 'data-orig="it"' not in m.group(1) and "<" not in m.group(4) else m.group(0),
                  page, flags=re.S)
    # le recensioni originali: lingua dichiarata
    page = page.replace('<p data-orig="it"', '<p lang="it" data-orig="it"')
    # hero claim con markup
    page = re.sub(r'(<(\w+)[^>]*?)data-it-html="[^"]*"([^>]*?)data-en-html="([^"]*)"([^>]*>)(.*?)(</\2>)',
                  lambda m: m.group(1) + m.group(3) + m.group(5) + _html.unescape(m.group(4)) + m.group(7), page, count=1, flags=re.S)
    # aria-label
    page = re.sub(r'aria-label="[^"]*"([^>]*?)data-aria-en="([^"]*)"', r'aria-label="\2"\1data-aria-en="\2"', page)
    page = re.sub(r'(<[^>]*?)aria-label="[^"]*"([^>]*?)data-aria-it="[^"]*"([^>]*?)data-aria-en="([^"]*)"',
                  r'\1aria-label="\4"\2\3', page)
    for it_alt, en_alt in ALT_EN.items():
        page = page.replace('alt="%s"' % it_alt, 'alt="%s"' % en_alt)
    # head
    page = page.replace('<html lang="it">', '<html lang="en">', 1)
    page = re.sub(r"<title>.*?</title>", "<title>%s</title>" % EN_TITLE, page, count=1)
    desc_it = re.search(r'<meta name="description" content="([^"]*)"', page).group(1)
    page = page.replace(desc_it, EN_DESC)  # description, og:description, twitter:description
    page = page.replace("A casa mia · caffè · brunch · aperitivo · Civitavecchia", EN_TITLE)  # og:title, twitter:title
    page = page.replace('<link rel="canonical" href="%s/">' % SITE_URL, '<link rel="canonical" href="%s/en/">' % SITE_URL)
    page = page.replace('<meta property="og:url" content="%s/">' % SITE_URL, '<meta property="og:url" content="%s/en/">' % SITE_URL)
    page = page.replace('<meta property="og:locale" content="it_IT">',
                        '<meta property="og:locale" content="en_GB">\n<meta property="og:locale:alternate" content="it_IT">')
    # json-ld
    page = page.replace('"description": "Bistrot nel cuore di Civitavecchia, a pochi passi dal porto."',
                        '"description": "A bistrot in the heart of Civitavecchia, a few steps from the port."')
    page = page.replace('"servesCuisine": ["Italiana", "Brunch", "Caffetteria"]', '"servesCuisine": ["Italian", "Brunch", "Coffee"]')
    page = page.replace('"url": "%s/"' % SITE_URL, '"url": "%s/en/"' % SITE_URL)
    # toggle: l'inglese e' la pagina corrente
    page = page.replace('<a id="l-it" class="on" href="/" hreflang="it" lang="it" aria-current="page">IT</a>',
                        '<a id="l-it" href="/" hreflang="it" lang="it">IT</a>')
    page = page.replace('<a id="l-en" href="/en/" hreflang="en" lang="en">EN</a>',
                        '<a id="l-en" class="on" href="/en/" hreflang="en" lang="en" aria-current="page">EN</a>')
    page = page.replace("var LANG = 'it';", "var LANG = 'en';")
    page = seed_orari(page, GIORNI_EN)
    # percorsi assoluti: la pagina vive in /en/
    page = re.sub(r'(?<=["(, ])public/', '/public/', page)
    page = page.replace('src="a-capo.js"', 'src="/a-capo.js"')
    return strip_lang_attrs(page, "en")


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

    en_page = make_en(out)
    out = strip_lang_attrs(seed_orari(out, GIORNI), "it")
    os.makedirs(os.path.dirname(OUT_EN), exist_ok=True)
    with open(OUT_EN, "w", encoding="utf-8") as f:
        f.write(en_page)
    print(f"scritto {OUT_EN}")
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"scritto {OUT_HTML} ({len(out)} byte, era {len(data)})")

    import shutil
    shutil.copyfile(SOURCE, OFFLINE)
    print(f"copiato {OFFLINE} (copia offline, invariata)")


if __name__ == "__main__":
    main()
