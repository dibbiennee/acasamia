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
import json
import urllib.parse
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
VESTITO = os.path.join(ROOT, "source", "vestito.html")  # nuovo vestito grafico (le immagini arrivano comunque dalla sorgente base64)

# unico punto da cambiare al go-live del dominio finale: sostituisce
# __SITE_URL__ in canonical/og:url/og:image. Quando acasamiacivitavecchia.it
# serve il sito, portalo a "https://acasamiacivitavecchia.it" e aggiungi il
# redirect 301 da acasamia.satoshiweb.it verso il nuovo dominio.
SITE_URL = "https://acasamiacivitavecchia.it"

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
    "Il bancone in travertino e i tavoli del locale": "The travertine counter and the tables",
    "Crostini con mozzarella e acciughe": "Crostini with mozzarella and anchovies",
    "Espresso martini": "Espresso martini",
    "Un cavolo romanesco tenuto tra le mani": "A romanesco broccoli held in both hands",
    "Scaffale con i prodotti in vendita": "Shelf with the products for sale",
    "Spritz con pizzette e olive": "Spritz with little pizzas and olives",
}
ALT_EN.update({
    "Cappuccino e cornetto sul tovagliolo con il logo di A casa mia": "Cappuccino and cornetto on the placemat with the A casa mia logo",
    "Cornetto con crema al pistacchio": "Cornetto with pistachio cream",
    "Tramezzino e succo d'arancia": "Tramezzino sandwich and orange juice",
    "Pasta servita sul tovagliolo a righe": "Pasta served on the striped placemat",
    "Brindisi con due calici di vino e tagliere di salumi e formaggi": "A toast with two glasses of wine and a board of cured meats and cheese",
    "Pasta artigianale Martelli sullo scaffale": "Martelli artisan pasta on the shelf",
    "La facciata di A casa mia con insegna e tenda": "The A casa mia front with its sign and awning",
    "Cinnamon roll con crema versata a cucchiaio": "Cinnamon roll with cream poured from a spoon",
    "Grembiule di A casa mia con un piatto di polpette": "An A casa mia apron beside a plate of meatballs",
})
ALT_EN["Mappa: A casa mia in Via XVI Settembre, vicino al porto di Civitavecchia"] = "Map: A casa mia on Via XVI Settembre, near the port of Civitavecchia"
ARIA_EN = {
    "Apri la mappa in Google Maps": "Open the map in Google Maps",
    "Recensione precedente": "Previous review",
    "Recensione successiva": "Next review",
    "Recensioni di Google": "Google reviews",
    "Colazioni dolci, brunch, pranzo, aperitivo": "Sweet breakfasts, brunch, lunch, aperitivo",
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
    # testi: ogni elemento con data-en riceve il testo inglese (anche con <b> dentro)
    TAG = re.compile(r'<(\w+)((?:\s+[\w-]+(?:="[^"]*")?)*)\s*>')
    pieces, pos = [], 0
    for m in TAG.finditer(page):
        if m.start() < pos:
            continue
        attrs = m.group(2)
        en = re.search(r' data-en="([^"]*)"', attrs)
        if not en or 'data-orig="it"' in attrs:
            continue
        close = page.index("</%s>" % m.group(1), m.end())
        pieces.append(page[pos:m.end()] + en.group(1))
        pos = close
    page = "".join(pieces) + page[pos:]
    # le recensioni originali: lingua dichiarata
    page = page.replace('<p data-orig="it"', '<p lang="it" data-orig="it"')
    # hero claim con markup
    page = re.sub(r'(<(\w+)[^>]*?)data-it-html="[^"]*"([^>]*?)data-en-html="([^"]*)"([^>]*>)(.*?)(</\2>)',
                  lambda m: m.group(1) + m.group(3) + m.group(5) + _html.unescape(m.group(4)) + m.group(7), page, count=1, flags=re.S)
    # aria-label
    page = re.sub(r'aria-label="[^"]*"([^>]*?)data-aria-en="([^"]*)"', r'aria-label="\2"\1data-aria-en="\2"', page)
    page = re.sub(r'(<[^>]*?)aria-label="[^"]*"([^>]*?)data-aria-it="[^"]*"([^>]*?)data-aria-en="([^"]*)"',
                  r'\1aria-label="\4"\2\3', page)
    for it_a, en_a in ARIA_EN.items():
        page = page.replace('aria-label="%s"' % it_a, 'aria-label="%s"' % en_a)
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
    page = page.replace('<a id="l-it" href="/" hreflang="it" lang="it" aria-current="page">IT</a>',
                        '<a id="l-it" href="/" hreflang="it" lang="it">IT</a>')
    page = page.replace('<a id="l-en" href="/en/" hreflang="en" lang="en">EN</a>',
                        '<a id="l-en" href="/en/" hreflang="en" lang="en" aria-current="page">EN</a>')
    _d = json.load(open(os.path.join(ROOT, 'source', 'dati.json'), encoding='utf-8'))['whatsapp_festa']
    page = page.replace(urllib.parse.quote(_d['it'], safe=''), urllib.parse.quote(_d['en'], safe=''))
    page = page.replace("var LANG = 'it';", "var LANG = 'en';").replace("var lang='it';", "var lang='en';")
    page = page.replace('<a href="/privacy/"', '<a href="/en/privacy/"')
    page = seed_orari(page, GIORNI_EN)
    # percorsi assoluti: la pagina vive in /en/
    page = re.sub(r'(?<=["(, ])public/', '/public/', page)
    page = page.replace('src="a-capo.js"', 'src="/a-capo.js"')
    return strip_lang_attrs(page, "en")


SRC_IMG = os.path.join(ROOT, "source", "img")


def build_vestito():
    """nuovo vestito: foto jpg in source/img -> webp 1280 e 640 in public/img, poi pagine IT e EN dal template"""
    os.makedirs(OUT_IMG, exist_ok=True)
    for f in os.listdir(OUT_IMG):
        os.remove(os.path.join(OUT_IMG, f))
    for f in sorted(os.listdir(SRC_IMG)):
        name, ext = os.path.splitext(f)
        if ext.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        im = Image.open(os.path.join(SRC_IMG, f)).convert("RGB")
        # la hero e' la foto che determina il primo schermo: compressione piu' spinta (misurata: -12% di LCP, PSNR 41 dB)
        q_full = 70 if name == "hero" else 80
        q_small = 70 if name == "hero" else 78
        im.save(os.path.join(OUT_IMG, name + ".webp"), "WEBP", quality=q_full, method=6)
        for w in (640, 960):
            if w >= im.width:
                continue
            small = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            small.save(os.path.join(OUT_IMG, "%s-%d.webp" % (name, w)), "WEBP", quality=q_small, method=6)
        print(f"  {name}: {im.width}x{im.height}")
    build_og_image(os.path.join(OUT_IMG, "hero.webp"), os.path.join(OUT_IMG, "og-image.jpg"))
    page = open(VESTITO, encoding="utf-8").read().replace("__SITE_URL__", SITE_URL)
    en_page = make_en(page)
    os.makedirs(os.path.dirname(OUT_EN), exist_ok=True)
    open(OUT_EN, "w", encoding="utf-8").write(en_page)
    open(OUT_HTML, "w", encoding="utf-8").write(strip_lang_attrs(page))
    print(f"scritto {OUT_HTML} e {OUT_EN}")
    build_privacy(page)
    build_pannello()
    build_sitemap()


def build_privacy(page):
    """/privacy/ e /en/privacy/: stessa testata e stesso footer del sito, contenuto da source/privacy_*.html"""
    def pagina(base, lingua):
        it = lingua == "it"
        main = open(os.path.join(ROOT, "source", "privacy_%s.html" % lingua), encoding="utf-8").read().strip()
        pre = "" if it else "/en"
        p = re.sub(r"<main id=\"top\">.*?</main>", lambda m: main, base, count=1, flags=re.S)
        p = re.sub(r'<script type="application/ld\+json">.*?</script>\n?', "", p, count=1, flags=re.S)
        p = re.sub(r'<link rel="preload" as="image"[^>]*>\n?', "", p, count=1)
        p = re.sub(r"<script>\n\(function\(\)\{\n  var lang=.*?</script>\n", "", p, count=1, flags=re.S)
        titolo = "Informativa privacy · A casa mia" if it else "Privacy policy · A casa mia"
        desc = ("Quali dati tratta il sito di A casa mia, Civitavecchia: nessun cookie, statistiche solo aggregate, fornitori e diritti."
                if it else "What data the A casa mia (Civitavecchia) website processes: no cookies, aggregated statistics only, providers and rights.")
        p = re.sub(r"<title>.*?</title>", "<title>%s</title>" % titolo, p, count=1)
        p = re.sub(r'(<meta (?:name|property)="(?:description|og:description|twitter:description)" content=")[^"]*"', lambda m: m.group(1) + desc + '"', p)
        p = re.sub(r'(<meta (?:property="og:title"|name="twitter:title") content=")[^"]*"', lambda m: m.group(1) + titolo + '"', p)
        p = re.sub(r'<link rel="canonical" href="[^"]*">', '<link rel="canonical" href="%s%s/privacy/">' % (SITE_URL, pre), p, count=1)
        p = re.sub(r'<meta property="og:url" content="[^"]*">', '<meta property="og:url" content="%s%s/privacy/">' % (SITE_URL, pre), p, count=1)
        p = re.sub(r'<link rel="alternate" hreflang="it-IT" href="[^"]*">', '<link rel="alternate" hreflang="it-IT" href="%s/privacy/">' % SITE_URL, p)
        p = re.sub(r'<link rel="alternate" hreflang="en" href="[^"]*">', '<link rel="alternate" hreflang="en" href="%s/en/privacy/">' % SITE_URL, p)
        p = re.sub(r'<link rel="alternate" hreflang="x-default" href="[^"]*">', '<link rel="alternate" hreflang="x-default" href="%s/privacy/">' % SITE_URL, p)
        # menu e logo tornano alla pagina principale
        p = p.replace('<a class="brand" href="#top"', '<a class="brand" href="%s/"' % pre, 1)
        for ancora in ("giornata", "recensioni", "dove"):
            p = p.replace('<a href="#%s"' % ancora, '<a href="%s/#%s"' % (pre, ancora))
        p = re.sub(r'<a id="l-it" href="/" hreflang="it" lang="it"( aria-current="page")?', '<a id="l-it" href="/privacy/" hreflang="it" lang="it"%s' % (' aria-current="page"' if it else ""), p)
        p = re.sub(r'<a id="l-en" href="/en/" hreflang="en" lang="en"( aria-current="page")?', '<a id="l-en" href="/en/privacy/" hreflang="en" lang="en"%s' % ("" if it else ' aria-current="page"'), p)
        p = re.sub(r'(?<=["(, ])public/', '/public/', p)
        p = p.replace('src="a-capo.js"', 'src="/a-capo.js"')
        return p
    base_it = pagina(page, "it")
    en_src = make_en(page)
    base_en = pagina(en_src, "en")
    # make_en ha gia' tradotto e tolto gli attributi: ripristina href della pagina inglese
    for pre, html in (("privacy", base_it), ("en/privacy", base_en)):
        os.makedirs(os.path.join(ROOT, pre), exist_ok=True)
    open(os.path.join(ROOT, "privacy", "index.html"), "w", encoding="utf-8").write(strip_lang_attrs(base_it))
    open(os.path.join(ROOT, "en", "privacy", "index.html"), "w", encoding="utf-8").write(strip_lang_attrs(base_en))
    print("scritto privacy/index.html e en/privacy/index.html")


def build_sitemap():
    """sitemap.xml e robots.txt con l'indirizzo definitivo (SITE_URL), pagine IT ed EN con hreflang reciproci"""
    import datetime
    oggi = datetime.date.today().isoformat()
    voci = []
    for loc, it_u, en_u in ((SITE_URL + "/", "/", "/en/"), (SITE_URL + "/en/", "/", "/en/"), (SITE_URL + "/privacy/", "/privacy/", "/en/privacy/"), (SITE_URL + "/en/privacy/", "/privacy/", "/en/privacy/")):
        voci.append(
            "  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n"
            '    <xhtml:link rel="alternate" hreflang="it-IT" href="%s%s"/>\n'
            '    <xhtml:link rel="alternate" hreflang="en" href="%s%s"/>\n'
            '    <xhtml:link rel="alternate" hreflang="x-default" href="%s%s"/>\n  </url>' % (loc, oggi, SITE_URL, it_u, SITE_URL, en_u, SITE_URL, it_u))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
           + "\n".join(voci) + "\n</urlset>\n")
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(xml)
    open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8").write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)
    print("scritto sitemap.xml e robots.txt (%s)" % SITE_URL)


def build_pannello():
    """pannello statistiche: template + tracciati del logo ufficiale (stessi del sito)"""
    src = os.path.join(ROOT, "source", "pannello.html")
    if not os.path.exists(src):
        return
    logo = json.load(open(os.path.join(ROOT, "source", "logo-marchio.json"), encoding="utf-8"))
    html = open(src, encoding="utf-8").read()
    html = html.replace("__MARK__", logo["mark"]).replace("__WORD__", logo["word"]).replace("__DOT__", logo["dot"])
    # in produzione i dati di prova non esistono: via la funzione demo e il suo interruttore
    html = re.sub(r"/\*DEMO-INIZIO\*/.*?/\*DEMO-FINE\*/\n", "", html, flags=re.S)
    html = re.sub(r"var DEMO=[^;]*;", "var DEMO=false;", html, count=1)
    os.makedirs(os.path.join(ROOT, "pannello"), exist_ok=True)
    open(os.path.join(ROOT, "pannello", "index.html"), "w", encoding="utf-8").write(html)
    print(f"scritto pannello/index.html ({len(html.encode()) // 1024} KB)")


def main():
    if os.path.exists(VESTITO) and os.path.isdir(SRC_IMG):
        return build_vestito()
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

    # nuovo vestito: la pagina vera e' il template, le immagini sono quelle appena estratte
    if os.path.exists(VESTITO):
        out = open(VESTITO, encoding="utf-8").read().replace("__SITE_URL__", SITE_URL)

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
